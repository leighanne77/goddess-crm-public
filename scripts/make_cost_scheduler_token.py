"""Mint a long-lived admin JWT for the Cloud Scheduler daily cost job.

Cloud Scheduler needs to hit /api/admin/cost-summary once a day. The
app's regular session JWTs expire after 7 days — fine for humans, too
short for a background job. This script produces a JWT with a long
expiration (default: 365 days) that can be pasted into the scheduler's
HTTP-request headers.

Usage:
    .venv/bin/python -m scripts.make_cost_scheduler_token \\
        --user-email alex@example.com \\
        --ttl-days 365

The user must already exist and have role=admin. Output is the raw
JWT — write it to a file or pipe to pbcopy, but don't commit it.

Rotation: re-run this script and update the scheduler config. No
backend change required.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone

from jose import jwt
from sqlalchemy import select

from app.config import get_settings
from app.database import SessionLocal
from app.models import User


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--user-email",
        required=True,
        help="Email of the admin user to mint the token as.",
    )
    p.add_argument(
        "--ttl-days",
        type=int,
        default=365,
        help="Token lifetime in days (default: 365).",
    )
    return p.parse_args()


def main() -> int:
    args = _parse_args()
    settings = get_settings()

    with SessionLocal() as db:
        user = db.scalars(select(User).where(User.email == args.user_email)).first()
        if user is None:
            print(f"No user with email {args.user_email}", file=sys.stderr)
            return 2
        if user.role != "admin":
            print(
                f"User {user.email} has role={user.role!r}, need 'admin'. "
                "Scheduler token must belong to an admin so it can hit "
                "/api/admin/cost-summary.",
                file=sys.stderr,
            )
            return 3

        now = datetime.now(timezone.utc)
        payload = {
            "sub": str(user.id),
            "iat": now,
            "exp": now + timedelta(days=args.ttl_days),
        }
        token = jwt.encode(
            payload, settings.jwt_secret, algorithm=settings.jwt_algorithm
        )

    print(token)
    return 0


if __name__ == "__main__":
    sys.exit(main())
