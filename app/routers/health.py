"""Health check endpoint."""

from fastapi import APIRouter

from app.config import get_settings

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str | bool]:
    """Return basic liveness info. Used by Cloud Run and uptime monitoring."""
    settings = get_settings()
    return {
        "status": "ok",
        "enterprise_mode": settings.enterprise_mode,
    }
