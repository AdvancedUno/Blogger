"""Pure-logic tests for the de-dup ledger (no network)."""

from __future__ import annotations

import pytest

pytest.importorskip("requests")  # dedup imports imager -> requests

from blogkit.core.dedup import (  # noqa: E402
    Ledger,
    link_hash,
    normalize_title,
    titles_similar,
)


def test_link_hash_normalizes():
    assert link_hash("https://x.com/a/") == link_hash("https://x.com/a")
    assert link_hash("https://x.com/a#frag") == link_hash("https://x.com/a")
    assert link_hash("https://x.com/a") != link_hash("https://x.com/b")


def test_titles_similar():
    assert titles_similar(
        "Why CFOs Must Rethink RTP Integration",
        "Why CFOs Should Rethink RTP Integration Now",
    )
    assert not titles_similar("Zero Trust Maturity", "Quantum Error Correction")


def test_normalize_title():
    assert normalize_title("Hello,  World!!") == "hello world"


def test_fresh_links_excludes_recent():
    led = Ledger()
    led.record(slug="a", keyword="k", title="T", links=["https://x.com/used"])
    fresh = led.fresh_links(["https://x.com/used", "https://x.com/new"])
    assert fresh == ["https://x.com/new"]


def test_title_clash_detection_and_record():
    led = Ledger()
    led.record(slug="a", keyword="k", title="Enterprise LLM Cost Optimization", links=[])
    assert led.title_clashes("Enterprise LLM Cost Optimization Strategies")
    assert led.title_clashes("Totally Unrelated Headline") is None


def test_json_roundtrip_and_prune():
    led = Ledger()
    led.record(slug="a", keyword="k", title="T", links=["https://x.com/1"])
    restored = Ledger.from_json(led.to_json())
    assert len(restored.entries) == 1
    restored.entries[0]["ts"] = "2000-01-01T00:00:00+00:00"  # ancient
    restored.prune()
    assert restored.entries == []


def test_from_json_tolerates_garbage():
    assert Ledger.from_json("not json").entries == []
    assert Ledger.from_json("{}").entries == []
