"""Google Tasks integration — "Talk to <Owner Name>" reminders.

Phase 2 Slice 5. Mirrors the structure of `app/services/sheets.py`:
- caller supplies the access_token (+ optional refresh_token);
- the service has no HTTP / ORM concerns;
- Google quirks are translated into typed exceptions the dispatcher
  (and ultimately the chat endpoint) can act on cleanly.

Public surface:
  create_talk_to_task(owner_name, task_title, notes, access_token,
                      refresh_token=None) -> CreatedTask
  -> get-or-create the per-user task list named "DIN: Talk to <Owner>",
     then insert a single task into it. Idempotent at the list level
     (same name on a second call reuses the existing list).
"""

from __future__ import annotations

from dataclasses import dataclass

from google.auth.exceptions import RefreshError
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.config import get_settings

GOOGLE_TOKEN_URI = "https://oauth2.googleapis.com/token"
TASK_LIST_TITLE_PREFIX = "DIN: Talk to "
# Phase 2 Slice 6.10 — single per-user list that holds every next-step
# the user owns, across all contacts. Task titles include the contact
# name as a prefix so the list reads naturally without one-list-per-
# contact explosion.
NEXT_STEPS_LIST_TITLE = "DIN: Next Steps"


class GoogleTasksError(Exception):
    """Base for anything this service might raise."""


class GoogleTasksScopeError(GoogleTasksError):
    """User hasn't granted the tasks scope (or revoked it). The chat
    handler maps this to a re-consent prompt for the end user."""


class GoogleTasksQuotaError(GoogleTasksError):
    """Google Tasks API 429 — surface a 'try again later' to the user."""


@dataclass
class CreatedTask:
    task_id: str
    task_list_id: str
    task_list_title: str
    self_link: str | None


def list_url(task_list_id: str) -> str:
    """User-facing URL for the Google Tasks web app.

    Returns the tasks.google.com root rather than a per-list deep link
    because Google Tasks has no public way to deep-link to a specific
    list. The API returns one ID format (e.g. `MTQwMzg3MTQyMjU2Njk3...`)
    while the tasks.google.com URL slug is a DIFFERENT encoding
    (e.g. `UHdaWjVXc3FEQWFFSEdENQ`) — both refer to the same list but
    Google's web app rejects the API format with a 404. The mapping
    between the two is undocumented and reverse-engineering it is
    brittle. Until Google ships a public deep-link, root URL it is —
    one extra click for the user, but no broken links.

    The `/u/0/` segment selects the user's default Google account; if
    the user has multiple Google accounts in the browser, they'll see
    Tasks for whichever account is in slot 0. The link target works
    regardless of which list they're viewing — the DIN: Next Steps
    list shows up in the sidebar.

    task_list_id is kept on the function signature for API stability
    and so callers don't have to remember the change; the value is
    intentionally ignored.
    """
    del task_list_id  # see docstring — Google has no usable deep link
    return "https://tasks.google.com/u/0/"


def _credentials(access_token: str, refresh_token: str | None) -> Credentials:
    """Build google-auth Credentials — same pattern as sheets._credentials.
    With a refresh_token, google-auth auto-refreshes when the access
    token is rejected. Without, any auth failure raises RefreshError
    inside googleapiclient and we translate to GoogleTasksScopeError."""
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


def _talk_to_list_title(owner_name: str) -> str:
    return f"{TASK_LIST_TITLE_PREFIX}{owner_name}"


def _find_list_id(tasks_service, title: str) -> str | None:
    """Page through tasklists, return the id whose title matches exactly.
    Three teammates each with a handful of lists fits in one page, but
    the loop costs nothing and protects against future growth."""
    page_token: str | None = None
    while True:
        kwargs = {"maxResults": 100}
        if page_token:
            kwargs["pageToken"] = page_token
        resp = tasks_service.tasklists().list(**kwargs).execute()
        for item in resp.get("items", []) or []:
            if item.get("title") == title:
                return str(item["id"])
        page_token = resp.get("nextPageToken")
        if not page_token:
            return None


def create_task_on_list(
    *,
    list_title: str,
    task_title: str,
    notes: str | None,
    access_token: str,
    refresh_token: str | None = None,
) -> CreatedTask:
    """Get-or-create a Google Tasks list by exact title, then insert one
    task. Generic primitive used by both the Slice 5 "Talk to <Owner>"
    flow and the Slice 6.10 next-steps flow.

    Exceptions:
      - GoogleTasksScopeError — user hasn't granted (or revoked) the
        tasks scope (HTTP 401/403 OR RefreshError).
      - GoogleTasksQuotaError — Tasks API 429.
      - GoogleTasksError — any other Google failure we couldn't classify.
    """
    creds = _credentials(access_token, refresh_token)

    try:
        tasks = build("tasks", "v1", credentials=creds, cache_discovery=False)

        list_id = _find_list_id(tasks, list_title)
        if list_id is None:
            created_list = (
                tasks.tasklists().insert(body={"title": list_title}).execute()
            )
            list_id = str(created_list["id"])

        body: dict[str, str] = {"title": task_title}
        if notes:
            body["notes"] = notes
        created_task = tasks.tasks().insert(tasklist=list_id, body=body).execute()

    except RefreshError as e:
        raise GoogleTasksScopeError(str(e)) from e
    except HttpError as e:
        http_status = e.resp.status if hasattr(e, "resp") else 0
        if http_status in (401, 403):
            raise GoogleTasksScopeError(str(e)) from e
        if http_status == 429:
            raise GoogleTasksQuotaError(str(e)) from e
        raise GoogleTasksError(str(e)) from e

    return CreatedTask(
        task_id=str(created_task["id"]),
        task_list_id=list_id,
        task_list_title=list_title,
        self_link=created_task.get("selfLink"),
    )


def create_talk_to_task(
    *,
    owner_name: str,
    task_title: str,
    notes: str | None,
    access_token: str,
    refresh_token: str | None = None,
) -> CreatedTask:
    """Slice 5 entry point — drops a task into the "DIN: Talk to
    <owner_name>" list. Thin wrapper around create_task_on_list."""
    return create_task_on_list(
        list_title=_talk_to_list_title(owner_name),
        task_title=task_title,
        notes=notes,
        access_token=access_token,
        refresh_token=refresh_token,
    )


def create_next_step_task(
    *,
    contact_name: str,
    title: str,
    notes: str | None,
    access_token: str,
    refresh_token: str | None = None,
) -> CreatedTask:
    """Slice 6.10 entry point — drops a task into the per-user
    "DIN: Next Steps" list. The contact name is prefixed onto the task
    title so the list reads naturally without one-list-per-contact
    explosion ('Marcus Sterling — call about Maritime deck')."""
    return create_task_on_list(
        list_title=NEXT_STEPS_LIST_TITLE,
        task_title=f"{contact_name} — {title}",
        notes=notes,
        access_token=access_token,
        refresh_token=refresh_token,
    )


def complete_task(
    *,
    task_list_id: str,
    task_id: str,
    access_token: str,
    refresh_token: str | None = None,
) -> None:
    """Mark a Google Tasks task complete. Best-effort — if the task was
    deleted out-of-band on Google's side, swallow 404. Other errors map
    to the standard exceptions."""
    creds = _credentials(access_token, refresh_token)
    try:
        tasks = build("tasks", "v1", credentials=creds, cache_discovery=False)
        tasks.tasks().patch(
            tasklist=task_list_id,
            task=task_id,
            body={"status": "completed"},
        ).execute()
    except RefreshError as e:
        raise GoogleTasksScopeError(str(e)) from e
    except HttpError as e:
        http_status = e.resp.status if hasattr(e, "resp") else 0
        if http_status == 404:
            return  # already gone — fine
        if http_status in (401, 403):
            raise GoogleTasksScopeError(str(e)) from e
        if http_status == 429:
            raise GoogleTasksQuotaError(str(e)) from e
        raise GoogleTasksError(str(e)) from e
