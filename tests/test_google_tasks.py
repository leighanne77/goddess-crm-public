"""Tests for the Google Tasks service.

Mocks googleapiclient at the `build()` level — same pattern as
test_sheets.py. The Tasks API surface we use is:
  - tasklists().list(maxResults, pageToken).execute()
  - tasklists().insert(body).execute()
  - tasks().insert(tasklist, body).execute()

The `_FakeBuilder` fluent mock records each chained call and pops one
canned return value per `.execute()`.
"""

from unittest.mock import MagicMock, patch

import pytest
from google.auth.exceptions import RefreshError
from googleapiclient.errors import HttpError

from app.services.google_tasks import (
    GoogleTasksError,
    GoogleTasksQuotaError,
    GoogleTasksScopeError,
    create_talk_to_task,
)


class _FakeBuilder:
    """Fluent mock — every attribute/call returns self; `.execute()`
    returns the next canned value. Same pattern as test_sheets._FakeBuilder."""

    def __init__(self, execute_values: list[object]) -> None:
        self._values = list(execute_values)
        self.calls: list[tuple[str, tuple, dict]] = []

    def __getattr__(self, name: str):  # noqa: D401
        def call(*args, **kwargs):
            self.calls.append((name, args, kwargs))
            return self

        return call

    def execute(self):
        self.calls.append(("execute", (), {}))
        return self._values.pop(0) if self._values else {}


def _raise_http(status: int) -> HttpError:
    resp = MagicMock()
    resp.status = status
    return HttpError(resp=resp, content=b"err")


def test_create_talk_to_task_creates_list_when_missing() -> None:
    """No existing list with that title -> insert one, then insert task."""
    builder = _FakeBuilder(
        [
            {"items": []},  # tasklists.list -> empty
            {"id": "list-new"},  # tasklists.insert
            {"id": "task-1", "selfLink": "https://t/task-1"},  # tasks.insert
        ]
    )
    with patch("app.services.google_tasks.build") as mock_build:
        mock_build.return_value = builder
        result = create_talk_to_task(
            owner_name="Alex Rivera",
            task_title="Talk to Alex Rivera about Marcus",
            notes="ask about Maritime deck",
            access_token="tok",
        )
    assert result.task_id == "task-1"
    assert result.task_list_id == "list-new"
    assert result.task_list_title == "DIN: Talk to Alex Rivera"
    assert result.self_link == "https://t/task-1"
    method_names = [c[0] for c in builder.calls]
    assert "insert" in method_names  # both list-insert and task-insert show up


def test_create_talk_to_task_reuses_existing_list() -> None:
    """Existing list with that title -> NO list-insert, just task-insert."""
    builder = _FakeBuilder(
        [
            {
                "items": [
                    {"id": "list-other", "title": "Random other list"},
                    {"id": "list-existing", "title": "DIN: Talk to Alex Rivera"},
                ]
            },
            {"id": "task-2", "selfLink": "https://t/task-2"},
        ]
    )
    with patch("app.services.google_tasks.build") as mock_build:
        mock_build.return_value = builder
        result = create_talk_to_task(
            owner_name="Alex Rivera",
            task_title="t",
            notes=None,
            access_token="tok",
        )
    assert result.task_list_id == "list-existing"
    # Only the `tasks.insert` body should show up as a kwarg dict containing
    # tasklist; tasklists.insert (which would include body={title:...}) must NOT.
    insert_kwargs = [c[2] for c in builder.calls if c[0] == "insert"]
    assert any("tasklist" in kw for kw in insert_kwargs)
    list_insert_bodies = [
        kw.get("body", {}) for kw in insert_kwargs if "tasklist" not in kw
    ]
    assert all("title" not in (b or {}) for b in list_insert_bodies)


def test_create_talk_to_task_paginates_list_lookup() -> None:
    """First page misses, second page hits — must follow nextPageToken."""
    builder = _FakeBuilder(
        [
            {"items": [{"id": "x", "title": "Other"}], "nextPageToken": "p2"},
            {"items": [{"id": "list-hit", "title": "DIN: Talk to Sam Chen"}]},
            {"id": "task-3"},
        ]
    )
    with patch("app.services.google_tasks.build") as mock_build:
        mock_build.return_value = builder
        result = create_talk_to_task(
            owner_name="Sam Chen",
            task_title="t",
            notes=None,
            access_token="tok",
        )
    assert result.task_list_id == "list-hit"


def test_create_talk_to_task_omits_notes_when_none() -> None:
    builder = _FakeBuilder(
        [
            {"items": [{"id": "L", "title": "DIN: Talk to X"}]},
            {"id": "task-bare"},
        ]
    )
    with patch("app.services.google_tasks.build") as mock_build:
        mock_build.return_value = builder
        create_talk_to_task(
            owner_name="X",
            task_title="Talk to X about Y",
            notes=None,
            access_token="tok",
        )
    # The task.insert body must not contain a notes key when notes is None
    task_insert_calls = [
        c for c in builder.calls if c[0] == "insert" and "tasklist" in c[2]
    ]
    assert task_insert_calls
    body = task_insert_calls[0][2]["body"]
    assert "notes" not in body


def test_403_becomes_scope_error() -> None:
    builder = _FakeBuilder([])

    def boom(*a, **kw):
        raise _raise_http(403)

    builder.execute = boom  # type: ignore[method-assign]
    with patch("app.services.google_tasks.build") as mock_build:
        mock_build.return_value = builder
        with pytest.raises(GoogleTasksScopeError):
            create_talk_to_task(
                owner_name="X",
                task_title="t",
                notes=None,
                access_token="tok",
            )


def test_401_becomes_scope_error() -> None:
    builder = _FakeBuilder([])

    def boom(*a, **kw):
        raise _raise_http(401)

    builder.execute = boom  # type: ignore[method-assign]
    with patch("app.services.google_tasks.build") as mock_build:
        mock_build.return_value = builder
        with pytest.raises(GoogleTasksScopeError):
            create_talk_to_task(
                owner_name="X", task_title="t", notes=None, access_token="tok"
            )


def test_429_becomes_quota_error() -> None:
    builder = _FakeBuilder([])

    def boom(*a, **kw):
        raise _raise_http(429)

    builder.execute = boom  # type: ignore[method-assign]
    with patch("app.services.google_tasks.build") as mock_build:
        mock_build.return_value = builder
        with pytest.raises(GoogleTasksQuotaError):
            create_talk_to_task(
                owner_name="X", task_title="t", notes=None, access_token="tok"
            )


def test_500_falls_through_to_base_error() -> None:
    builder = _FakeBuilder([])

    def boom(*a, **kw):
        raise _raise_http(500)

    builder.execute = boom  # type: ignore[method-assign]
    with patch("app.services.google_tasks.build") as mock_build:
        mock_build.return_value = builder
        with pytest.raises(GoogleTasksError) as exc_info:
            create_talk_to_task(
                owner_name="X", task_title="t", notes=None, access_token="tok"
            )
        assert not isinstance(exc_info.value, GoogleTasksScopeError)
        assert not isinstance(exc_info.value, GoogleTasksQuotaError)


def test_refresh_error_becomes_scope_error() -> None:
    """Token rejected at refresh time (e.g. user revoked grant at Google's
    end) — google-auth raises RefreshError. We map to scope so the
    caller's user-facing remedy is the same as a 403: re-grant."""
    builder = _FakeBuilder([])

    def boom(*a, **kw):
        raise RefreshError("revoked")

    builder.execute = boom  # type: ignore[method-assign]
    with patch("app.services.google_tasks.build") as mock_build:
        mock_build.return_value = builder
        with pytest.raises(GoogleTasksScopeError):
            create_talk_to_task(
                owner_name="X",
                task_title="t",
                notes=None,
                access_token="tok",
                refresh_token="rtok",
            )
