"""SMTP email sender for system alerts.

Thin wrapper around stdlib smtplib targeting Gmail SMTP (port 587 STARTTLS)
with an app password. Used by the daily cost-alert job; can be reused for
any future system-to-admin notification.

Design choices:
- Synchronous send. The daily job is hit by Cloud Scheduler once a day and
  alerts <= 1 recipient list of 1-3 admins; no need for async or a queue.
- Caller controls the recipient list. The service does not query the
  database — keeps it testable and reusable for any alert source.
- Returns a SendResult instead of raising on partial failure, so the caller
  can record per-recipient outcome in logs.
- A missing smtp_password short-circuits to a no-op log line. Lets dev /
  test environments skip SMTP without faking it.
"""

from __future__ import annotations

import logging
import smtplib
from dataclasses import dataclass, field
from email.message import EmailMessage

from app.config import get_settings

_logger = logging.getLogger("app.email")


@dataclass
class SendResult:
    attempted: bool
    sent_to: list[str] = field(default_factory=list)
    failed: dict[str, str] = field(default_factory=dict)
    skipped_reason: str | None = None


def send_alert(subject: str, body: str, recipients: list[str]) -> SendResult:
    """Send a plain-text alert email to each recipient.

    Returns a SendResult. Never raises — partial failures are recorded
    in the result so the caller can decide whether to retry or log.
    """
    settings = get_settings()

    if not settings.smtp_password:
        _logger.info(
            "email_skipped",
            extra={
                "event": "email_skipped",
                "reason": "smtp_password_unset",
                "recipient_count": len(recipients),
            },
        )
        return SendResult(attempted=False, skipped_reason="smtp_password_unset")

    if not recipients:
        return SendResult(attempted=False, skipped_reason="no_recipients")

    from_address = settings.smtp_from_address or settings.smtp_username
    from_header = f"{settings.smtp_from_name} <{from_address}>"

    sent_to: list[str] = []
    failed: dict[str, str] = {}

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as smtp:
            smtp.starttls()
            smtp.login(settings.smtp_username, settings.smtp_password)
            for recipient in recipients:
                msg = EmailMessage()
                msg["Subject"] = subject
                msg["From"] = from_header
                msg["To"] = recipient
                msg.set_content(body)
                try:
                    smtp.send_message(msg)
                    sent_to.append(recipient)
                except smtplib.SMTPException as exc:
                    failed[recipient] = str(exc)
    except (smtplib.SMTPException, OSError) as exc:
        _logger.exception(
            "email_send_connection_failed",
            extra={"event": "email_send_failed", "error": str(exc)},
        )
        return SendResult(
            attempted=True,
            sent_to=sent_to,
            failed={r: str(exc) for r in recipients if r not in sent_to},
        )

    _logger.info(
        "email_sent",
        extra={
            "event": "email_sent",
            "subject": subject,
            "sent_count": len(sent_to),
            "failed_count": len(failed),
        },
    )
    return SendResult(attempted=True, sent_to=sent_to, failed=failed)
