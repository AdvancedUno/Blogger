"""Pure-logic tests for the Search Console feedback ranking (no network)."""

from __future__ import annotations

import random

from blogkit.core.analytics import fetch_top_queries, prioritize_queries, score_queries

RSS = [
    "Zero Trust Network Access ZTNA",
    "Quantum error correction",
    "SASE architecture rollout",
    "Vector database latency",
]
GSC = [
    {"query": "zero trust network access guide", "clicks": 40, "impressions": 1000},
    {"query": "sase architecture enterprise", "clicks": 2, "impressions": 300},
]


def test_score_rewards_overlap_and_weight():
    scores = dict(score_queries(RSS, GSC))
    # ZTNA query overlaps the high-click GSC row -> top score
    assert scores["Zero Trust Network Access ZTNA"] > scores["SASE architecture rollout"] > 0
    # no overlap -> zero
    assert scores["Quantum error correction"] == 0.0


def test_prioritize_moves_winners_to_front_deterministic():
    out = prioritize_queries(RSS, GSC, boost=2, rng=random.Random(0))
    assert out[0] == "Zero Trust Network Access ZTNA"   # best performer first
    assert set(out) == set(RSS)                          # no items lost/dupes
    assert "SASE architecture rollout" in out[:2]        # second performer boosted


def test_prioritize_no_signals_is_just_shuffle():
    out = prioritize_queries(RSS, [], rng=random.Random(1))
    assert set(out) == set(RSS) and len(out) == len(RSS)


def test_fetch_returns_empty_without_creds(monkeypatch):
    for v in ("GSC_CLIENT_ID", "GSC_CLIENT_SECRET", "GSC_REFRESH_TOKEN",
              "GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GOOGLE_REFRESH_TOKEN"):
        monkeypatch.delenv(v, raising=False)
    assert fetch_top_queries("https://x.blogspot.com/") == []
    assert fetch_top_queries("") == []
