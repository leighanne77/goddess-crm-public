"""Google Sheets export service.

Thin wrapper around `googleapiclient` that creates a sheet in Drive,
populates it, and grants domain-wide read access. The export endpoint
(Slice 2) calls this; the service itself has no HTTP concerns.

Design rules:
- The CALLER supplies the Google access token — never read from a global.
  That way the call happens on the end user's behalf (their Drive, their
  quota) rather than a service account.
- Errors don't leak — we translate Google's quirks (403 scope, 429
  quota) into domain exceptions the endpoint can handle cleanly.
- Nothing in here touches the ORM or the HTTP layer. Pure Google I/O.
"""

from __future__ import annotations

from dataclasses import dataclass

from google.auth.exceptions import RefreshError
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.config import get_settings

GOOGLE_TOKEN_URI = "https://oauth2.googleapis.com/token"


class SheetsExportError(Exception):
    """Base for anything this service might raise."""


class SheetsScopeError(SheetsExportError):
    """Google rejected the call because the user hasn't granted `drive.file`.

    The endpoint maps this to the CSV fallback path (Slice 3).
    """


class SheetsQuotaError(SheetsExportError):
    """Google Sheets/Drive API 429. Rare for this app's call volume but
    worth naming so the endpoint can return a sensible retry message."""


@dataclass
class CreatedSheet:
    id: str
    url: str


def _credentials(access_token: str, refresh_token: str | None = None) -> Credentials:
    """Build google-auth Credentials from a raw access token, optionally
    with the refresh_token + client credentials google-auth needs to
    swap a stale token for a fresh one.

    - With refresh_token: google-auth auto-refreshes when the access
      token is rejected (expired OR revoked at Google's end). The
      refreshed token is used for the in-flight call only; we don't
      currently persist it back to the DB, so every subsequent call
      from the same user does a fresh refresh. Acceptable cost — the
      refresh RPC is ~50ms and only happens on the first call after
      expiry.
    - Without refresh_token: the old Day 5 behavior — one-shot call.
      Any auth failure raises RefreshError inside googleapiclient,
      which create_sheet() catches and routes to SheetsScopeError →
      endpoint falls back to CSV.
    """
    if refresh_token:
        settings = get_settings()
        return Credentials(
            token=access_token,
            refresh_token=refresh_token,
            token_uri=GOOGLE_TOKEN_URI,
            client_id=settings.google_client_id,
            client_secret=settings.google_client_secret,
        )
    return Credentials(token=access_token)


def create_sheet(
    *,
    title: str,
    headers: list[str],
    rows: list[list[str]],
    access_token: str,
    refresh_token: str | None = None,
    drive_folder_id: str | None = None,
    share_domain: str | None = None,
) -> CreatedSheet:
    """Create a new sheet in Drive, populate it, and share domain-wide.

    Returns the sheet's id and web URL.

    Exceptions:
      - SheetsScopeError  — user hasn't granted drive.file (HTTP 403)
        OR previously-granted token was revoked at Google's end
        (manifests as RefreshError because google-auth tries to refresh
        the now-invalid token; we don't store a refresh_token, so the
        refresh fails. Both cases mean "ask the user to re-grant" —
        the endpoint falls back to CSV in either case.)
      - SheetsQuotaError  — Sheets/Drive API rate-limited us (HTTP 429)
      - SheetsExportError — any other Google failure we couldn't classify
    """
    creds = _credentials(access_token, refresh_token)

    try:
        sheets = build("sheets", "v4", credentials=creds, cache_discovery=False)
        drive = build("drive", "v3", credentials=creds, cache_discovery=False)

        # 1. Create the empty spreadsheet. Sheets API creates it in the
        # user's root Drive by default; we move it to the team folder
        # (if configured) in step 3.
        created = (
            sheets.spreadsheets()
            .create(
                body={"properties": {"title": title}},
                fields="spreadsheetId,spreadsheetUrl",
            )
            .execute()
        )
        sheet_id = created["spreadsheetId"]
        sheet_url = created["spreadsheetUrl"]

        # 2. Populate headers + rows in one batch update.
        body = {"values": [headers, *rows]}
        sheets.spreadsheets().values().update(
            spreadsheetId=sheet_id,
            range="A1",
            valueInputOption="RAW",
            body=body,
        ).execute()

        # 3. Move into the team Drive folder if configured.
        if drive_folder_id:
            drive.files().update(
                fileId=sheet_id,
                addParents=drive_folder_id,
                fields="id,parents",
            ).execute()

        # 4. Grant domain-wide read access.
        if share_domain:
            drive.permissions().create(
                fileId=sheet_id,
                body={
                    "type": "domain",
                    "role": "reader",
                    "domain": share_domain,
                },
                sendNotificationEmail=False,
            ).execute()

    except RefreshError as e:
        # User revoked the Drive scope (or the access token expired and
        # we have no refresh_token to swap it for a new one). Real Google
        # returns this as a refresh failure, not an HTTP 403 — Day 5
        # smoke 3c proved the mock-only test missed this path. Treat it
        # the same as scope-not-granted: endpoint falls back to CSV and
        # tells the user to re-auth.
        raise SheetsScopeError(str(e)) from e
    except HttpError as e:
        status = e.resp.status if hasattr(e, "resp") else 0
        if status == 403:
            # Most common cause: user hasn't consented to drive.file.
            # Occasionally means admin hasn't approved the app for the
            # domain. Either way, the endpoint falls back to CSV.
            raise SheetsScopeError(str(e)) from e
        if status == 401:
            # Access token rejected outright. Same user-facing remedy as
            # 403 / RefreshError — re-grant. Endpoint falls back to CSV.
            raise SheetsScopeError(str(e)) from e
        if status == 429:
            raise SheetsQuotaError(str(e)) from e
        raise SheetsExportError(str(e)) from e

    return CreatedSheet(id=sheet_id, url=sheet_url)
