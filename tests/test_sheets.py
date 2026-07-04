"""Tests for the Sheets export service.

Mocks googleapiclient so these tests never touch the real API. The
Day 5 plan's Slice 9 smoke handles real Sheets against real Drive.

We mock at the `build()` level because both Sheets and Drive clients
come from the same factory and the call chains are deeply fluent
(.spreadsheets().values().update().execute()). Mock once, verify the
recorded calls.
"""

from unittest.mock import MagicMock, patch

import pytest
from google.auth.exceptions import RefreshError
from googleapiclient.errors import HttpError

from app.services.sheets import (
    SheetsExportError,
    SheetsQuotaError,
    SheetsScopeError,
    create_sheet,
)


class _FakeBuilder:
    """Fluent mock for googleapiclient — every attribute/call returns
    self, with `.execute()` returning a canned value set per-test."""

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


def _canned_build(execute_queue: list[object]) -> _FakeBuilder:
    builder = _FakeBuilder(execute_queue)
    return builder


def test_create_sheet_happy_path() -> None:
    """Create → write values → move to folder → share domain. All 4 calls."""
    sheet_created = {
        "spreadsheetId": "sheet-abc",
        "spreadsheetUrl": "https://docs.google.com/spreadsheets/d/sheet-abc",
    }
    sheets_builder = _canned_build([sheet_created, {}])  # create, values.update
    drive_builder = _canned_build([{}, {}])  # files.update, permissions.create

    with patch("app.services.sheets.build") as mock_build:
        mock_build.side_effect = [sheets_builder, drive_builder]
        result = create_sheet(
            title="Maritime Contacts",
            headers=["name", "company"],
            rows=[["Admiral", "Mare Island"]],
            access_token="fake-token",
            drive_folder_id="folder-123",
            share_domain="example.com",
        )

    assert result.id == "sheet-abc"
    assert result.url.startswith("https://docs.google.com/spreadsheets/")


def test_create_sheet_without_folder_skips_move() -> None:
    """If no drive_folder_id, Drive files.update is NOT called."""
    sheets_builder = _canned_build(
        [
            {"spreadsheetId": "s1", "spreadsheetUrl": "https://x"},
            {},
        ]
    )
    drive_builder = _canned_build([{}])  # only permissions.create

    with patch("app.services.sheets.build") as mock_build:
        mock_build.side_effect = [sheets_builder, drive_builder]
        result = create_sheet(
            title="t",
            headers=["h"],
            rows=[["v"]],
            access_token="tok",
            drive_folder_id=None,
            share_domain="example.com",
        )
    assert result.id == "s1"
    # Drive builder was NOT called with files/update chain
    method_names = [c[0] for c in drive_builder.calls]
    assert "files" not in method_names


def test_create_sheet_without_share_domain_skips_share() -> None:
    sheets_builder = _canned_build(
        [
            {"spreadsheetId": "s2", "spreadsheetUrl": "https://x"},
            {},
        ]
    )
    drive_builder = _canned_build([])  # nothing should be called

    with patch("app.services.sheets.build") as mock_build:
        mock_build.side_effect = [sheets_builder, drive_builder]
        result = create_sheet(
            title="t",
            headers=["h"],
            rows=[["v"]],
            access_token="tok",
            drive_folder_id=None,
            share_domain=None,
        )
    assert result.id == "s2"
    assert drive_builder.calls == []


def _raise_http(status: int) -> HttpError:
    resp = MagicMock()
    resp.status = status
    return HttpError(resp=resp, content=b"err")


def test_create_sheet_translates_403_to_scope_error() -> None:
    sheets_builder = _canned_build([])

    def raise_403(*args, **kwargs):
        raise _raise_http(403)

    sheets_builder.execute = raise_403  # type: ignore[method-assign]

    with patch("app.services.sheets.build") as mock_build:
        mock_build.return_value = sheets_builder
        with pytest.raises(SheetsScopeError):
            create_sheet(
                title="t",
                headers=["h"],
                rows=[["v"]],
                access_token="tok",
            )


def test_create_sheet_translates_429_to_quota_error() -> None:
    sheets_builder = _canned_build([])

    def raise_429(*args, **kwargs):
        raise _raise_http(429)

    sheets_builder.execute = raise_429  # type: ignore[method-assign]

    with patch("app.services.sheets.build") as mock_build:
        mock_build.return_value = sheets_builder
        with pytest.raises(SheetsQuotaError):
            create_sheet(
                title="t",
                headers=["h"],
                rows=[["v"]],
                access_token="tok",
            )


def test_create_sheet_other_errors_become_base_export_error() -> None:
    """500 (and any non-401/403/429 status) falls through to SheetsExportError."""
    sheets_builder = _canned_build([])

    def raise_500(*args, **kwargs):
        raise _raise_http(500)

    sheets_builder.execute = raise_500  # type: ignore[method-assign]

    with patch("app.services.sheets.build") as mock_build:
        mock_build.return_value = sheets_builder
        with pytest.raises(SheetsExportError) as exc_info:
            create_sheet(
                title="t",
                headers=["h"],
                rows=[["v"]],
                access_token="tok",
            )
        # Not the more-specific subclasses
        assert not isinstance(exc_info.value, SheetsScopeError)
        assert not isinstance(exc_info.value, SheetsQuotaError)


def test_create_sheet_401_becomes_scope_error() -> None:
    """A 401 from Google means the access token was rejected outright;
    user-facing remedy is identical to a 403 scope refusal — re-grant.
    Endpoint falls back to CSV in either case."""
    sheets_builder = _canned_build([])

    def raise_401(*args, **kwargs):
        raise _raise_http(401)

    sheets_builder.execute = raise_401  # type: ignore[method-assign]

    with patch("app.services.sheets.build") as mock_build:
        mock_build.return_value = sheets_builder
        with pytest.raises(SheetsScopeError):
            create_sheet(
                title="t",
                headers=["h"],
                rows=[["v"]],
                access_token="tok",
            )


def test_credentials_has_refresh_fields_when_refresh_token_supplied() -> None:
    """Day 6 regression guard. With a refresh_token, _credentials must
    build a full Credentials object that google-auth can use to swap an
    expired/revoked access_token for a fresh one. Without the token_uri
    + client_id + client_secret, the refresh call would fail (the very
    bug that 3c caught with RefreshError). Pinning the shape."""
    from app.services.sheets import _credentials

    creds = _credentials("access-1", "refresh-1")
    assert creds.token == "access-1"
    assert creds.refresh_token == "refresh-1"
    assert creds.token_uri == "https://oauth2.googleapis.com/token"
    assert creds.client_id is not None
    assert creds.client_secret is not None


def test_credentials_omits_refresh_fields_when_no_refresh_token() -> None:
    """Back-compat: a user who signed in before Day 6 has no
    refresh_token stored. _credentials falls back to one-shot behavior
    and RefreshError on failure still routes to SheetsScopeError via
    the except chain."""
    from app.services.sheets import _credentials

    creds = _credentials("access-only")
    assert creds.token == "access-only"
    assert creds.refresh_token is None


def test_create_sheet_refresh_error_becomes_scope_error() -> None:
    """Day 5 smoke 3c regression guard. When the user revokes the Drive
    scope at Google's end, googleapiclient detects the now-invalid token
    and tries to refresh — but we don't store a refresh_token, so refresh
    raises google.auth.exceptions.RefreshError (NOT an HttpError 403).
    The original code only caught HttpError, so the RefreshError
    propagated to FastAPI as a 500 instead of triggering the CSV
    fallback. This test pins the fix: RefreshError → SheetsScopeError →
    endpoint returns CSV."""
    sheets_builder = _canned_build([])

    def raise_refresh(*args, **kwargs):
        raise RefreshError(
            "The credentials do not contain the necessary fields need to "
            "refresh the access token."
        )

    sheets_builder.execute = raise_refresh  # type: ignore[method-assign]

    with patch("app.services.sheets.build") as mock_build:
        mock_build.return_value = sheets_builder
        with pytest.raises(SheetsScopeError):
            create_sheet(
                title="t",
                headers=["h"],
                rows=[["v"]],
                access_token="tok",
            )
