"""Admin-only endpoints. Today: audit log read + CSV export.

Gated by `require_admin` from app.dependencies — non-admins get a flat
403 with "Admin role required." Audit rows are visible to ALL admins
(not user-private the way contacts are), but member-role users have
zero visibility into anyone's writes.
"""

from __future__ import annotations

import csv
from datetime import datetime
from io import StringIO

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_admin
from app.models import AuditLog, User

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(require_admin)],
)


class AuditRow(BaseModel):
    """One audit-log row joined with the actor's email."""

    id: int
    user_id: int
    user_email: str | None
    action: str
    target_type: str | None
    target_id: int | None
    payload_hash: str | None
    created_at: datetime


class AuditListResponse(BaseModel):
    rows: list[AuditRow]
    total: int
    page: int
    page_size: int


_DEFAULT_PAGE_SIZE = 50
_MAX_PAGE_SIZE = 200


def _audit_query(*, user_id: int | None, action: str | None) -> tuple[object, object]:
    """Build (rows_stmt, count_stmt) with the same filters applied."""
    base = select(
        AuditLog.id,
        AuditLog.user_id,
        User.email.label("user_email"),
        AuditLog.action,
        AuditLog.target_type,
        AuditLog.target_id,
        AuditLog.payload_hash,
        AuditLog.created_at,
    ).outerjoin(User, User.id == AuditLog.user_id)

    count = select(func.count()).select_from(AuditLog)

    if user_id is not None:
        base = base.where(AuditLog.user_id == user_id)
        count = count.where(AuditLog.user_id == user_id)
    if action is not None:
        base = base.where(AuditLog.action == action)
        count = count.where(AuditLog.action == action)

    base = base.order_by(AuditLog.id.desc())
    return base, count


@router.get("/audit", response_model=AuditListResponse)
def list_audit(
    page: int = Query(1, ge=1),
    page_size: int = Query(_DEFAULT_PAGE_SIZE, ge=1, le=_MAX_PAGE_SIZE),
    user_id: int | None = Query(None),
    action: str | None = Query(None),
    db: Session = Depends(get_db),
) -> AuditListResponse:
    """Paginated audit-log listing. Newest first."""
    rows_stmt, count_stmt = _audit_query(user_id=user_id, action=action)
    total = db.scalar(count_stmt) or 0
    offset = (page - 1) * page_size
    raw = db.execute(rows_stmt.limit(page_size).offset(offset)).mappings().all()
    rows = [AuditRow(**dict(r)) for r in raw]
    return AuditListResponse(
        rows=rows,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/audit.csv")
def export_audit_csv(
    user_id: int | None = Query(None),
    action: str | None = Query(None),
    db: Session = Depends(get_db),
) -> Response:
    """Stream the entire filtered audit log as a CSV download.

    Useful for compliance audits and offline review — important given
    the dual-use angle. Same filters as the JSON endpoint, but
    no pagination: returns ALL matching rows in one file.
    """
    rows_stmt, _ = _audit_query(user_id=user_id, action=action)
    raw = db.execute(rows_stmt).mappings().all()

    out = StringIO()
    writer = csv.writer(out)
    writer.writerow(
        [
            "id",
            "user_id",
            "user_email",
            "action",
            "target_type",
            "target_id",
            "payload_hash",
            "created_at",
        ]
    )
    for r in raw:
        writer.writerow(
            [
                r["id"],
                r["user_id"],
                r["user_email"] or "",
                r["action"],
                r["target_type"] or "",
                r["target_id"] if r["target_id"] is not None else "",
                r["payload_hash"] or "",
                r["created_at"].isoformat() if r["created_at"] else "",
            ]
        )

    today = datetime.utcnow().strftime("%Y-%m-%d")
    return Response(
        content=out.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="din-audit-{today}.csv"'
        },
    )
