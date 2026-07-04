"""Email-domain heuristics for current-government-employee detection.

Used by create_contact / update_contact to auto-set is_gov_employee=True
when the contact's email lives on a recognized government domain. Owner
can override (set False) for edge cases — contractors with a .gov inbox
who aren't gov employees, dual-hat folks who left gov last week, etc.

Kept conservative: false negative is fine (owner toggles on); false
positive flags a non-gov contact, which over-decorates the card and is
mildly annoying.

The suffix list is mirrored in the Alembic backfill migration
(7b4e2f1a9c83). Update both sites if extending coverage.
"""

from __future__ import annotations

_GOV_DOMAIN_SUFFIXES: tuple[str, ...] = (
    "gov",  # US federal/state (umbrella)
    "mil",  # US military (umbrella)
    "fed.us",  # US federal alternate
    "gc.ca",  # Canada federal
    "gov.uk",  # United Kingdom
    "gov.au",  # Australia
    "gov.sa",  # Saudi Arabia
    "gov.ae",  # United Arab Emirates
    "gov.qa",  # Qatar
    "gov.kw",  # Kuwait
    "gov.sg",  # Singapore
    "gov.in",  # India
    "gov.za",  # South Africa
    "gouv.fr",  # France
    "bund.de",  # Germany federal
)


def looks_like_gov_email(email: str | None) -> bool:
    """Return True if the email's domain is, or ends in a subdomain of,
    a known government suffix.

    Suffixes are stored without a leading dot; the check matches either
    the bare suffix ("diana@fed.us" → domain == "fed.us") or a subdomain
    of it ("lisa@usace.army.mil" → domain endswith ".mil"). Empty/None
    returns False — auto-detect needs a domain to decide.
    """
    if not email or "@" not in email:
        return False
    domain = email.split("@", 1)[1].strip().lower()
    return any(
        domain == suffix or domain.endswith("." + suffix)
        for suffix in _GOV_DOMAIN_SUFFIXES
    )
