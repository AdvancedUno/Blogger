"""Publishing-cadence jitter — break the scaled-content "metronome" signature.

A network that publishes every blog every day at the exact same minute reads as
machine-operated to Google's scaled-content systems, which is a primary AdSense
"low value content" / "scaled content abuse" trigger. This module adds two
deterministic, re-run-safe jitters:

  * ``is_rest_day``  — each blog skips exactly one day per ISO week, on a weekday
    that rotates from week to week and differs across the network. This breaks
    the synchronized daily cadence WITHOUT creating long multi-day silent gaps
    (an abandoned-looking archive would read worse than a steady one).
  * ``published_at`` — each post's *visible* publish timestamp is back-dated by
    a per-(blog, day) offset within a window, so posts no longer all carry the
    same run minute. Back-dating only (never the future) keeps every post live
    immediately rather than turning it into a scheduled draft.

Both are pure functions of (slug, date): deterministic, so a same-day re-run
makes the identical decision (a retried CI job won't double-publish a rested
blog or re-stamp a post), and dependency-free, so they're trivially testable.

Scope note: ``published_at`` only affects the Blogger v3 API transport. The
Mail-to-Blogger email fallback (used on API-quota days) cannot set a publish
timestamp — Blogger stamps those posts on receipt — so timestamp jitter does
not apply on fallback days. The rest-day skip still applies to both transports.
"""
from __future__ import annotations

import hashlib
from datetime import date as _date
from datetime import datetime, timedelta, timezone

# Days in a week: each blog rests on exactly one of them per ISO week, chosen by
# a per-(slug, ISO-week) hash so the rest weekday rotates weekly and is spread
# across the network rather than synchronized. Average rest rate is exactly 1/7.
DAYS_IN_WEEK = 7

# Largest back-date applied to a post's visible timestamp, in minutes. The daily
# job fires at a fixed UTC minute; spreading posts across the preceding window
# de-synchronizes the network's visible publish times. Past-only, so the post
# still goes live the moment it is inserted (a future stamp would schedule it).
MAX_BACKDATE_MINUTES = 9 * 60  # up to 9 hours earlier


def _digest(*parts: str) -> int:
    """Stable 256-bit hash of ``parts`` as a big int.

    Uses SHA-256 rather than the built-in ``hash()`` because the latter is
    salted per process, which would make the decision differ between CI jobs.
    """
    return int(hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest(), 16)


def is_rest_day(slug: str, day: _date) -> bool:
    """True when ``slug`` should skip publishing on ``day``.

    Each (slug, ISO-week) hashes to one rest weekday, so a blog rests exactly
    once every ISO week on a day that rotates week to week and varies across the
    network. This averages 1/7 of days without the long consecutive gaps that an
    independent per-day coin flip would occasionally produce.
    """
    iso_year, iso_week, _iso_weekday = day.isocalendar()
    rest_weekday = _digest(slug, str(iso_year), str(iso_week)) % DAYS_IN_WEEK
    return day.weekday() == rest_weekday


def backdate_minutes(slug: str, day: _date) -> int:
    """Deterministic per-(blog, day) back-date offset in minutes (0 .. MAX-1)."""
    return _digest("ts", slug, day.isoformat()) % MAX_BACKDATE_MINUTES


def published_at(slug: str, now: datetime | None = None) -> str:
    """RFC 3339 timestamp for a post's ``published`` field, back-dated by a
    deterministic per-(blog, day) offset so the network's visible publish times
    are staggered instead of identical.

    ``now`` defaults to the current UTC time; pass an explicit value in tests.
    The result is always in the past, so Blogger publishes the post immediately
    (a future timestamp would hold it as a scheduled draft instead). Applies to
    the API transport only — see the module docstring.
    """
    if now is None:
        now = datetime.now(timezone.utc)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    stamp = now - timedelta(minutes=backdate_minutes(slug, now.date()))
    return stamp.isoformat()
