"""Google OAuth login endpoints.

Two-step browser flow:
  GET /auth/google     -> sets oauth_state cookie, 307 to Google
  GET /auth/callback   -> verifies state, exchanges code, sets the
                          session cookie, redirects to the frontend

The frontend reads the session cookie automatically on subsequent
requests via `credentials: "include"`. The CLI harness in
scripts/test_chat.py still works because get_current_user falls back
to the Bearer header when no cookie is present.
"""

import secrets
from datetime import datetime, timezone
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import User
from app.security import create_access_token
from app.services.google_oauth import verify_google_id_token

router = APIRouter(prefix="/auth", tags=["auth"])

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
STATE_COOKIE = "oauth_state"
STATE_TTL_SECONDS = 300


@router.get("/google")
async def start_google_login() -> Response:
    """Plant the state cookie and redirect to Google's account picker."""
    settings = get_settings()
    state = secrets.token_urlsafe(32)
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        # drive.file added Day 5 so the Sheets export can write on behalf
        # of the user. Limited to files this app creates/opens, NOT the
        # user's full Drive. tasks added Phase 2 Slice 5 for the
        # "remind me to talk to <Owner>" flow — forces re-consent for
        # all teammates (prompt=consent below already does that on every
        # login, so the change rolls out cleanly on next sign-in).
        "scope": (
            "openid email profile "
            "https://www.googleapis.com/auth/drive.file "
            "https://www.googleapis.com/auth/tasks"
        ),
        "state": state,
        # access_type=offline + prompt=consent together ask Google to
        # return a refresh_token alongside the access_token. Without
        # offline, no refresh_token. Without prompt=consent, Google
        # only returns refresh_token on the FIRST consent — subsequent
        # logins return nothing, so a user who revoked at Google's end
        # can't recover without admin intervention. consent prompts the
        # consent screen on every sign-in (mildly annoying for three
        # users who sign in monthly) but guarantees we always have a
        # working refresh_token.
        "access_type": "offline",
        "prompt": "consent",
    }
    response = RedirectResponse(
        url=f"{GOOGLE_AUTH_URL}?{urlencode(params)}",
        status_code=status.HTTP_307_TEMPORARY_REDIRECT,
    )
    response.set_cookie(
        key=STATE_COOKIE,
        value=state,
        max_age=STATE_TTL_SECONDS,
        httponly=True,
        samesite="lax",
        secure=settings.enterprise_mode,
    )
    return response


async def _exchange_code_for_tokens(
    code: str,
) -> tuple[str, str | None, str | None]:
    """POST to Google's token endpoint. Returns
    (id_token, access_token, refresh_token).

    access_token is what Sheets/Drive calls use directly (Day 5).
    refresh_token (Day 6) is what google-auth uses to swap an expired/
    revoked access_token for a fresh one without bouncing the user.
    Both can be absent — Google omits refresh_token unless the OAuth
    request was access_type=offline + prompt=consent.
    """
    settings = get_settings()
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "redirect_uri": settings.google_redirect_uri,
                "grant_type": "authorization_code",
            },
        )
        resp.raise_for_status()
        body = resp.json()
        return (
            str(body["id_token"]),
            body.get("access_token"),
            body.get("refresh_token"),
        )


def _get_or_create_user(
    db: Session,
    *,
    email: str,
    google_user_id: str,
    name: str | None,
    google_access_token: str | None = None,
    google_refresh_token: str | None = None,
) -> User:
    """Find by email and update, or create. Either way bump last_login.
    Stores the Google access token so Sheets/Drive calls can act on the
    user's behalf (Day 5). Stores the refresh token so the SAME calls
    can swap an expired/revoked access_token for a fresh one without
    re-auth (Day 6).

    Important: the refresh_token is OVERWRITE-IF-PROVIDED (same as
    access_token) — never wipe an existing one. Google only returns
    refresh_token when prompt=consent forces re-issue, so a user who
    signs in via a different prompt would otherwise lose theirs."""
    user = db.scalars(select(User).where(User.email == email)).first()
    if user is None:
        user = User(email=email, google_user_id=google_user_id, name=name)
        db.add(user)
    else:
        user.google_user_id = google_user_id
        if name:
            user.name = name
    if google_access_token:
        user.google_access_token = google_access_token
    if google_refresh_token:
        user.google_refresh_token = google_refresh_token
    user.last_login = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user)
    return user


@router.get("/callback")
async def google_callback(
    code: str,
    state: str,
    oauth_state: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Verify state, exchange code, set session cookie, redirect to frontend."""
    settings = get_settings()
    if not oauth_state or oauth_state != state:
        raise HTTPException(status_code=400, detail="State mismatch")

    id_token, google_access_token, google_refresh_token = (
        await _exchange_code_for_tokens(code)
    )
    try:
        claims = await verify_google_id_token(id_token)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}") from e

    email = str(claims.get("email", "")).lower()
    if not email or email not in settings.allowed_email_set:
        raise HTTPException(status_code=403, detail="Email not authorized")

    user = _get_or_create_user(
        db,
        email=email,
        google_user_id=str(claims.get("sub", "")),
        name=claims.get("name"),
        google_access_token=google_access_token,
        google_refresh_token=google_refresh_token,
    )
    access_token = create_access_token(user_id=user.id)

    redirect = RedirectResponse(
        url=f"{settings.frontend_url}{settings.frontend_auth_success_path}",
        status_code=status.HTTP_303_SEE_OTHER,
    )
    redirect.delete_cookie(STATE_COOKIE)
    redirect.set_cookie(
        key=settings.session_cookie_name,
        value=access_token,
        max_age=settings.jwt_expiration_days * 24 * 3600,
        httponly=True,
        samesite="lax",
        secure=settings.enterprise_mode,
        path="/",
    )
    return redirect


@router.get("/dev-login")
def dev_login(
    email: str | None = None,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """LOCAL-ONLY sign-in that skips Google. Hard-disabled when
    ENTERPRISE_MODE is on — returns 404 so it cannot exist in production.

    Issues the exact same session cookie as the real OAuth callback for a
    user on the ALLOWED_EMAILS allowlist (the given email, or the first
    allowed email by default), then redirects to the frontend. No Google
    tokens are stored, so Drive/Sheets/Tasks calls won't work under this
    session — fine for local contact/relationship data entry.
    """
    settings = get_settings()
    # The single most important line in this file: dev login never exists
    # in production.
    if settings.enterprise_mode:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    allowed = sorted(settings.allowed_email_set)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No ALLOWED_EMAILS configured for dev login.",
        )
    chosen = email.lower() if email else allowed[0]
    if chosen not in settings.allowed_email_set:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"{chosen} is not on the dev allowlist.",
        )

    user = _get_or_create_user(
        db,
        email=chosen,
        google_user_id=f"dev-local:{chosen}",
        name=chosen.split("@")[0].replace(".", " ").title(),
    )
    access_token = create_access_token(user_id=user.id)
    redirect = RedirectResponse(
        url=f"{settings.frontend_url}{settings.frontend_auth_success_path}",
        status_code=status.HTTP_303_SEE_OTHER,
    )
    redirect.set_cookie(
        key=settings.session_cookie_name,
        value=access_token,
        max_age=settings.jwt_expiration_days * 24 * 3600,
        httponly=True,
        samesite="lax",
        secure=settings.enterprise_mode,
        path="/",
    )
    return redirect


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout() -> Response:
    """Clear the session cookie. Frontend should redirect to /login afterward."""
    settings = get_settings()
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    response.delete_cookie(settings.session_cookie_name, path="/")
    return response
