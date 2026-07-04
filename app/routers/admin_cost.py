"""Admin cost-summary endpoint + daily alert job.

Returns today's total Anthropic spend across all users, derived from
the per-user daily_input_tokens_used / daily_output_tokens_used
counters on the users table.

The response is both machine-readable (JSON for Cloud Scheduler) and
emits a structured log line (`event="cost_summary"`) so a Cloud
Monitoring log-based alert can watch for over-threshold days without
needing a separate metrics pipeline.

Slice 7.1 adds POST /admin/run-daily-cost-job which calls the same
summary and then dispatches an alert email to every admin user when
over_threshold is true. The dry_run=true query param forces the email
path regardless of threshold — used for smoke-testing the wiring
without waiting for actual overspend.

Gated by `require_admin` — alex@ can hit it manually in a browser;
Cloud Scheduler uses a long-lived admin JWT minted via
`scripts/make_cost_scheduler_token.py`.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.dependencies import require_admin
from app.models import User, VoiceUsage
from app.services.email import send_alert

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(require_admin)],
)

# Anthropic Sonnet 4.6 list pricing (USD per 1M tokens). Source:
# https://www.anthropic.com/pricing  (2026-04 Sonnet 4.6 figures).
# Kept as module constants rather than env vars because they change
# rarely enough that a code change is cheap and a visible diff is
# valuable. Update together with chat_model.
_SONNET_4_6_INPUT_USD_PER_MTOK: float = 3.0
_SONNET_4_6_OUTPUT_USD_PER_MTOK: float = 15.0

_MODEL_PRICING: dict[str, tuple[float, float]] = {
    "claude-sonnet-4-6": (
        _SONNET_4_6_INPUT_USD_PER_MTOK,
        _SONNET_4_6_OUTPUT_USD_PER_MTOK,
    ),
}

_logger = logging.getLogger("app.admin_cost")


class CostSummary(BaseModel):
    """Daily-cost rollup. All money values are USD.

    Phase 3 Slice 0: `voice_spend_usd` (Chirp STT + future TTS) sits
    alongside `spend_usd` (Anthropic tokens). The threshold check fires
    on `total_spend_usd` so adding a voice-heavy day can trigger the
    alert even if LLM spend stays low.
    """

    date: date
    model: str
    input_tokens: int
    output_tokens: int
    spend_usd: float
    voice_spend_usd: float = 0.0
    total_spend_usd: float
    threshold_usd: float
    over_threshold: bool
    users_counted: int
    generated_at: datetime


class JobResult(BaseModel):
    """Outcome of the daily cost-alert job run."""

    summary: CostSummary
    email_attempted: bool
    email_sent_to: list[str]
    email_failed: dict[str, str]
    email_skipped_reason: str | None
    dry_run: bool


def _price_tokens(model: str, input_tokens: int, output_tokens: int) -> float:
    """Return USD spend for a token count, given Sonnet 4.6 pricing.

    Unknown models fall back to Sonnet 4.6 rates — the cost number is
    still directionally useful and the log line records the actual
    model string so a human can spot the mismatch.
    """
    input_rate, output_rate = _MODEL_PRICING.get(
        model, (_SONNET_4_6_INPUT_USD_PER_MTOK, _SONNET_4_6_OUTPUT_USD_PER_MTOK)
    )
    return (input_tokens * input_rate + output_tokens * output_rate) / 1_000_000


def compute_cost_summary(db: Session, target_date: date) -> CostSummary:
    """Sum the day's token usage across all users, price it, log it.

    Shared helper for both GET /cost-summary and POST /run-daily-cost-job.
    Per-user daily counters are tied to token_budget_reset_at: a user
    who chatted today has that column set to today and their counter
    values reflect today's usage. Users who didn't chat today are
    excluded — their counters still hold a prior day's total.
    """
    settings = get_settings()

    row = db.execute(
        select(
            func.coalesce(func.sum(User.daily_input_tokens_used), 0).label("input"),
            func.coalesce(func.sum(User.daily_output_tokens_used), 0).label("output"),
            func.count(User.id).label("users"),
        ).where(User.token_budget_reset_at == target_date)
    ).one()

    input_tokens = int(row.input)
    output_tokens = int(row.output)
    users_counted = int(row.users)

    spend = _price_tokens(settings.chat_model, input_tokens, output_tokens)

    # Phase 3 Slice 0 — sum voice spend (Chirp STT now; ElevenLabs TTS
    # added in Slice 4). VoiceUsage.ts is a timestamptz; Postgres
    # date() against it extracts in the session timezone (UTC). The
    # LLM side above keys on the local `token_budget_reset_at` date
    # column, so the two subsystems can legitimately use different
    # "today" definitions. For voice, today_utc is the right window.
    # Backfill via `?date=YYYY-MM-DD` only applies to the LLM side.
    today_utc = datetime.now(timezone.utc).date()
    voice_spend_row = db.execute(
        select(func.coalesce(func.sum(VoiceUsage.cost_usd), 0).label("voice")).where(
            func.date(VoiceUsage.ts) == today_utc
        )
    ).one()
    voice_spend = float(voice_spend_row.voice)

    total_spend = spend + voice_spend
    over = total_spend >= settings.daily_cost_alert_threshold_usd

    _logger.info(
        "cost_summary",
        extra={
            "event": "cost_summary",
            "cost_date": target_date.isoformat(),
            "model": settings.chat_model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "spend_usd": round(spend, 4),
            "voice_spend_usd": round(voice_spend, 4),
            "total_spend_usd": round(total_spend, 4),
            "threshold_usd": settings.daily_cost_alert_threshold_usd,
            "over_threshold": over,
            "users_counted": users_counted,
        },
    )

    return CostSummary(
        date=target_date,
        model=settings.chat_model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        spend_usd=round(spend, 4),
        voice_spend_usd=round(voice_spend, 4),
        total_spend_usd=round(total_spend, 4),
        threshold_usd=settings.daily_cost_alert_threshold_usd,
        over_threshold=over,
        users_counted=users_counted,
        generated_at=datetime.utcnow(),
    )


def _resolve_alert_recipients(db: Session) -> list[str]:
    """Return the email list for cost alerts.

    Override wins if set (smoke-testing into one inbox without granting
    admin role). Otherwise resolves to every active admin user.
    """
    settings = get_settings()
    if settings.cost_alert_recipients_override.strip():
        return [
            e.strip()
            for e in settings.cost_alert_recipients_override.split(",")
            if e.strip()
        ]
    rows = db.execute(select(User.email).where(User.role == "admin")).scalars().all()
    return list(rows)


def _compose_alert(summary: CostSummary) -> tuple[str, str]:
    """Return (subject, body) for the over-threshold alert."""
    subject = (
        f"[DIN] Daily spend over threshold "
        f"— ${summary.total_spend_usd:.2f} on {summary.date.isoformat()}"
    )
    body = (
        f"Total spend on {summary.date.isoformat()} crossed the "
        f"${summary.threshold_usd:.2f} daily threshold.\n\n"
        f"Anthropic (LLM):\n"
        f"  Model: {summary.model}\n"
        f"  Spend: ${summary.spend_usd:.4f}\n"
        f"  Input tokens: {summary.input_tokens:,}\n"
        f"  Output tokens: {summary.output_tokens:,}\n\n"
        f"Voice (STT + TTS):\n"
        f"  Spend: ${summary.voice_spend_usd:.4f}\n\n"
        f"Total: ${summary.total_spend_usd:.4f}\n"
        f"Active users (LLM): {summary.users_counted}\n\n"
        f"Drill-down: https://team.example.com/admin/cost-summary\n"
        f"This is an automated alert from the DIN CRM."
    )
    return subject, body


@router.get("/cost-summary", response_model=CostSummary)
def cost_summary(
    for_date: date | None = Query(
        default=None,
        alias="date",
        description="Date to summarize (defaults to today). YYYY-MM-DD.",
    ),
    db: Session = Depends(get_db),
) -> CostSummary:
    """Return the day's cost rollup as JSON; logs the structured event."""
    return compute_cost_summary(db, for_date or date.today())


@router.post("/run-daily-cost-job", response_model=JobResult)
def run_daily_cost_job(
    dry_run: bool = Query(
        default=False,
        description=(
            "Force the email path regardless of threshold. Used for "
            "smoke-testing SMTP wiring without waiting for overspend."
        ),
    ),
    db: Session = Depends(get_db),
) -> JobResult:
    """Compute today's spend; email admins if over threshold or dry-run."""
    summary = compute_cost_summary(db, date.today())

    should_email = summary.over_threshold or dry_run
    if not should_email:
        return JobResult(
            summary=summary,
            email_attempted=False,
            email_sent_to=[],
            email_failed={},
            email_skipped_reason="under_threshold",
            dry_run=dry_run,
        )

    recipients = _resolve_alert_recipients(db)
    subject, body = _compose_alert(summary)
    if dry_run:
        subject = f"[DRY RUN] {subject}"
    result = send_alert(subject, body, recipients)

    return JobResult(
        summary=summary,
        email_attempted=result.attempted,
        email_sent_to=result.sent_to,
        email_failed=result.failed,
        email_skipped_reason=result.skipped_reason,
        dry_run=dry_run,
    )
