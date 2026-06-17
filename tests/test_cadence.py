"""Tests for the publishing-cadence jitter (deterministic, re-run safe)."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from blogkit.core import cadence

SLUGS = [
    "ai_infra_insider", "zero_trust_enterprise", "dataops_vector_dbs",
    "b2b_payment_rails", "wealthtech_systems", "clinical_trial_tech",
    "supply_chain_visibility", "legaltech_enterprise", "enterprise_revops",
    "finops_cloud_cost", "observability_sre", "grid_energy_storage",
]


def test_is_rest_day_is_deterministic():
    day = date(2026, 6, 16)
    for slug in SLUGS:
        assert cadence.is_rest_day(slug, day) == cadence.is_rest_day(slug, day)


def test_rest_rate_is_one_in_seven():
    # One rest per ISO week => rate pinned near 1/7. Tight enough to catch an
    # accidental change to the divisor (5 => 0.20, 9 => 0.11 would both fail).
    start = date(2026, 1, 1)
    total = rests = 0
    for slug in SLUGS:
        for d in range(364):  # exactly 52 ISO weeks
            total += 1
            if cadence.is_rest_day(slug, start + timedelta(days=d)):
                rests += 1
    rate = rests / total
    assert 0.12 < rate < 0.17, f"rest rate {rate:.3f} not near 1/7"


def test_exactly_one_rest_per_iso_week():
    # Each blog rests on exactly one day within any single ISO week.
    # Take a 7-day span that falls entirely inside one ISO week (Mon..Sun).
    monday = date(2026, 6, 15)  # ISO Monday
    week = [monday + timedelta(days=i) for i in range(7)]
    for slug in SLUGS:
        assert sum(cadence.is_rest_day(slug, d) for d in week) == 1


def test_no_long_consecutive_rest_gaps():
    # The whole point of ISO-week scheduling: no abandoned-looking multi-day
    # silences. Across a full year, max consecutive rest run is <= 2 (only a
    # week-boundary Sun+Mon pairing can ever be consecutive).
    start = date(2026, 1, 1)
    for slug in SLUGS:
        streak = longest = 0
        for d in range(365):
            if cadence.is_rest_day(slug, start + timedelta(days=d)):
                streak += 1
                longest = max(longest, streak)
            else:
                streak = 0
        assert longest <= 2, f"{slug} had a {longest}-day rest gap"


def test_rest_days_are_desynchronized_across_blogs():
    # On a given day the network should NOT all rest or all run together.
    day = date(2026, 6, 16)
    resting = sum(cadence.is_rest_day(s, day) for s in SLUGS)
    assert resting < len(SLUGS)  # not everyone rests the same day


def test_published_at_is_in_the_past_and_parseable():
    now = datetime(2026, 6, 16, 14, 0, tzinfo=timezone.utc)
    for slug in SLUGS:
        stamp = cadence.published_at(slug, now)
        parsed = datetime.fromisoformat(stamp)
        assert parsed <= now                      # never the future
        assert now - parsed <= timedelta(minutes=cadence.MAX_BACKDATE_MINUTES)
        assert parsed.tzinfo is not None          # carries an offset


def test_published_at_varies_by_slug_and_day():
    now = datetime(2026, 6, 16, 14, 0, tzinfo=timezone.utc)
    stamps = {cadence.published_at(s, now) for s in SLUGS}
    assert len(stamps) > 1                          # different blogs differ
    a = cadence.published_at("ai_infra_insider", now)
    b = cadence.published_at("ai_infra_insider", now + timedelta(days=1))
    assert a != b                                   # same blog differs by day


def test_published_at_handles_naive_datetime():
    naive = datetime(2026, 6, 16, 14, 0)
    stamp = cadence.published_at("ai_infra_insider", naive)
    assert datetime.fromisoformat(stamp).tzinfo is not None
