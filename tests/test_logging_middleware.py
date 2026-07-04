"""Tests for JSON logging + RequestIDMiddleware."""

from __future__ import annotations

import json
import logging
import uuid

from fastapi.testclient import TestClient

from app.logging_config import JsonFormatter, request_id_var
from app.main import create_app


def test_json_formatter_emits_valid_json() -> None:
    rec = logging.LogRecord(
        name="test.logger",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="hello %s",
        args=("world",),
        exc_info=None,
    )
    parsed = json.loads(JsonFormatter().format(rec))
    assert parsed["severity"] == "INFO"
    assert parsed["message"] == "hello world"
    assert parsed["logger"] == "test.logger"
    assert "time" in parsed
    assert "request_id" not in parsed  # no contextvar set


def test_json_formatter_includes_request_id_from_contextvar() -> None:
    token = request_id_var.set("req-abc123")
    try:
        rec = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="hi",
            args=(),
            exc_info=None,
        )
        parsed = json.loads(JsonFormatter().format(rec))
    finally:
        request_id_var.reset(token)
    assert parsed["request_id"] == "req-abc123"


def test_json_formatter_merges_extras() -> None:
    rec = logging.LogRecord(
        name="test.logger",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="hit",
        args=(),
        exc_info=None,
    )
    rec.method = "GET"
    rec.path = "/api/health"
    rec.status = 200
    parsed = json.loads(JsonFormatter().format(rec))
    assert parsed["method"] == "GET"
    assert parsed["path"] == "/api/health"
    assert parsed["status"] == 200


def test_middleware_generates_uuid_and_sets_response_header() -> None:
    client = TestClient(create_app())
    resp = client.get("/api/health")
    assert resp.status_code == 200
    rid = resp.headers.get("X-Request-ID")
    assert rid is not None
    uuid.UUID(rid)  # raises if not a UUID


def test_middleware_preserves_caller_supplied_request_id() -> None:
    client = TestClient(create_app())
    resp = client.get("/api/health", headers={"X-Request-ID": "caller-abc-123"})
    assert resp.headers["X-Request-ID"] == "caller-abc-123"


def test_middleware_rejects_oversize_incoming_id_and_generates_fresh() -> None:
    client = TestClient(create_app())
    oversize = "x" * 200
    resp = client.get("/api/health", headers={"X-Request-ID": oversize})
    rid = resp.headers["X-Request-ID"]
    assert rid != oversize
    uuid.UUID(rid)


def test_middleware_emits_request_log_with_fields(caplog) -> None:
    client = TestClient(create_app())
    with caplog.at_level(logging.INFO, logger="app.request"):
        resp = client.get("/api/health")
    assert resp.status_code == 200
    matching = [r for r in caplog.records if r.getMessage() == "request"]
    assert len(matching) == 1
    r = matching[0]
    assert r.method == "GET"
    assert r.path == "/api/health"
    assert r.status == 200
    assert isinstance(r.duration_ms, float)
