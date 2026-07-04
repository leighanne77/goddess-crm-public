"""Auth dependency tests on GET /contacts."""

from datetime import datetime, timedelta, timezone
from typing import Callable

from fastapi.testclient import TestClient
from jose import jwt

from app.config import get_settings
from app.models import User
from app.security import create_access_token


def test_list_contacts_without_token_returns_401(client: TestClient) -> None:
    response = client.get("/api/contacts")
    assert response.status_code == 401


def test_list_contacts_with_valid_token_returns_200(
    client: TestClient, user_factory: Callable[..., User]
) -> None:
    user = user_factory()
    token = create_access_token(user_id=user.id)
    response = client.get("/api/contacts", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_list_contacts_with_expired_token_returns_401(client: TestClient) -> None:
    settings = get_settings()
    expired_payload = {
        "sub": "1",
        "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
    }
    expired_token = jwt.encode(
        expired_payload, settings.jwt_secret, algorithm=settings.jwt_algorithm
    )
    response = client.get(
        "/api/contacts", headers={"Authorization": f"Bearer {expired_token}"}
    )
    assert response.status_code == 401


def test_list_contacts_with_token_for_missing_user_returns_401(
    client: TestClient,
) -> None:
    token = create_access_token(user_id=99999)
    response = client.get("/api/contacts", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
