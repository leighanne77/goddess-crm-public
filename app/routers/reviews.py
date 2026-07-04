"""Owner-facing review queue HTTP endpoints.

The same change-request data the voice/chat flow exposes through
`request_change` / `resolve_change_request` tools, surfaced as a
dedicated UI at /admin/reviews. Auth is owner-of-target (not admin
role): each row is visible only to the user who owns the contact
the request is filed against.

The resolve endpoint delegates to the same handler as the chat tool
so the side effects (apply the change, write the audit row, flip
status) stay in one place.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session, aliased

from app.database import get_db
from app.dependencies import get_current_user
from app.models import ChangeRequest, Contact, User
from app.services.tool_dispatch import _handle_resolve_change_request
from app.services.tools import ResolveChangeRequestInput

router = APIRouter(prefix="/admin/reviews", tags=["reviews"])


class ReviewRow(BaseModel):
    id: int
    requester_id: int
    requester_email: str | None
    contact_id: int
    contact_name: str
    kind: str
    payload: dict | list | None
    reason: str | None
    status: str
    resolution_note: str | None
    created_at: datetime
    resolved_at: datetime | None
    resolved_by_id: int | None


class ReviewListResponse(BaseModel):
    rows: list[ReviewRow]
    total: int
    page: int
    page_size: int


class ResolveBody(BaseModel):
    decision: Literal["approve", "disapprove"]
    note: str | None = Field(None, max_length=500)


_DEFAULT_PAGE_SIZE = 50
_MAX_PAGE_SIZE = 200


def _base_query(
    user: User, status_filter: str | None, kind_filter: str | None
) -> tuple[Any, Any]:
    """Build (rows_stmt, count_stmt) with owner-of-target gating applied."""
    Requester = aliased(User)
    rows = (
        select(
            ChangeRequest.id,
            ChangeRequest.requester_id,
            Requester.email.label("requester_email"),
            ChangeRequest.contact_id,
            Contact.name.label("contact_name"),
            ChangeRequest.kind,
            ChangeRequest.payload,
            ChangeRequest.reason,
            ChangeRequest.status,
            ChangeRequest.resolution_note,
            ChangeRequest.created_at,
            ChangeRequest.resolved_at,
            ChangeRequest.resolved_by_id,
        )
        .join(Contact, Contact.id == ChangeRequest.contact_id)
        .outerjoin(Requester, Requester.id == ChangeRequest.requester_id)
        .where(Contact.owner_id == user.id)
    )
    count = (
        select(func.count())
        .select_from(ChangeRequest)
        .join(Contact, Contact.id == ChangeRequest.contact_id)
        .where(Contact.owner_id == user.id)
    )
    if status_filter:
        rows = rows.where(ChangeRequest.status == status_filter)
        count = count.where(ChangeRequest.status == status_filter)
    if kind_filter:
        rows = rows.where(ChangeRequest.kind == kind_filter)
        count = count.where(ChangeRequest.kind == kind_filter)

    # Pending first (sort by created_at desc within each status group is
    # the natural reading order for the owner — newest first.
    rows = rows.order_by(ChangeRequest.created_at.desc())
    return rows, count


@router.get("", response_model=ReviewListResponse)
def list_reviews(
    status_filter: str | None = Query(
        "pending",
        alias="status",
        description="Filter by status. Pass empty string to see all.",
    ),
    kind: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(_DEFAULT_PAGE_SIZE, ge=1, le=_MAX_PAGE_SIZE),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReviewListResponse:
    """List change requests targeting contacts the current user owns.

    Default status=pending. Pass status='' to see resolved too. The
    `status='all'` sentinel is also accepted for the same effect.
    """
    effective_status = None if status_filter in (None, "", "all") else status_filter
    rows_stmt, count_stmt = _base_query(current_user, effective_status, kind)
    total = db.scalar(count_stmt) or 0
    offset = (page - 1) * page_size
    raw = db.execute(rows_stmt.limit(page_size).offset(offset)).mappings().all()
    rows = [ReviewRow(**dict(r)) for r in raw]
    return ReviewListResponse(rows=rows, total=total, page=page, page_size=page_size)


@router.post("/{request_id}/resolve", response_model=ReviewRow)
def resolve_review(
    body: ResolveBody,
    request_id: int = Path(..., gt=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReviewRow:
    """Approve (apply change) or disapprove (close) a pending request.

    Reuses the same handler the chat tool calls — keeps the side
    effects (apply patina/fly-status change + audit row + status flip)
    in one place.
    """
    params = ResolveChangeRequestInput(
        request_id=request_id, decision=body.decision, note=body.note
    )
    result = _handle_resolve_change_request(params, current_user, db)
    if "error" in result:
        code = result["error"]
        msg = result["message"]
        if code == "not_found":
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail=msg)
        if code == "forbidden_owner_only":
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail=msg)
        if code == "already_resolved":
            raise HTTPException(status.HTTP_409_CONFLICT, detail=msg)
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=msg)

    # Re-fetch the row with joined fields so the response matches list shape.
    rows_stmt, _ = _base_query(current_user, None, None)
    raw = db.execute(rows_stmt.where(ChangeRequest.id == request_id)).mappings().one()
    return ReviewRow(**dict(raw))
