"""Orchestration tests for run_profile with the core steps mocked.

Verifies routing/dedup/dry-run without network or the Gemini/Google SDKs
(generator + publisher imports are lazy, so importing the pipeline is safe)."""

from __future__ import annotations

import pytest

pytest.importorskip("requests")

from blogkit.core import pipeline  # noqa: E402
from blogkit.core.dedup import Ledger  # noqa: E402
from blogkit.core.generator import GeneratedPost  # noqa: E402
from blogkit.profiles.base import BlogProfile  # noqa: E402

PROFILE = BlogProfile(
    slug="t_blog", name="T Blog", blog_id="123", run_group=1,
    persona="veteran CISO", rss_queries=["kw one", "kw two"],
    featured_image=False,
)

NEWS = [{"title": "Story A", "link": "https://ex.com/a", "source": "Reuters", "summary": "s"}]

# A body long + varied enough to clear the 1000-word quality gate.
LONG_BODY = "<h2>Body</h2>\n<p>" + " ".join(f"insight{i % 80}" for i in range(1100)) + "</p>"


@pytest.fixture
def patched(monkeypatch):
    """Stub fetch + enrichment + generate; capture publish calls."""
    monkeypatch.setattr(pipeline, "fetch_top_news", lambda **k: list(NEWS))
    monkeypatch.setattr(pipeline, "enrich_news", lambda items: 0)
    monkeypatch.setattr(
        pipeline, "generate_post",
        lambda **k: GeneratedPost(title="A Sharp B2B Title", html=LONG_BODY, tags=["TagA"]),
    )
    calls: dict = {}

    def fake_api(**k):
        calls["api"] = k
        return "https://blog/post"

    def fake_email(*a, **k):
        calls["email"] = (a, k)
        return "secret@blogger.com"

    monkeypatch.setattr(pipeline, "publish_to_blogger", fake_api)
    monkeypatch.setattr(pipeline, "publish_via_email", fake_email)
    return calls


def test_api_publish_includes_seo_and_records_ledger(patched):
    led = Ledger()
    ok, info = pipeline.run_profile(PROFILE, publish_method="api", ledger=led)
    assert ok and info == "https://blog/post"
    html = patched["api"]["html_content"]
    assert "application/ld+json" in html        # JSON-LD injected
    assert "ex.com/a" in html                    # source citation injected
    assert len(led.entries) == 1                 # recorded
    assert led.entries[0]["title"] == "A Sharp B2B Title"
    # Labels come from the slug-category mapping, NOT the model's tags.
    assert patched["api"]["slug"] == "t_blog"
    assert "tags" not in patched["api"]


def test_dry_run_does_not_publish_or_record(patched):
    led = Ledger()
    ok, info = pipeline.run_profile(PROFILE, ledger=led, dry_run=True)
    assert ok and info.startswith("dry-run")
    assert "api" not in patched and "email" not in patched
    assert led.entries == []


def test_dedup_skips_when_all_sources_used(patched):
    led = Ledger()
    led.record(slug="other", keyword="x", title="prior", links=["https://ex.com/a"])
    ok, info = pipeline.run_profile(PROFILE, ledger=led)
    assert not ok and "no fresh news" in info
    assert "api" not in patched              # never reached publish


def test_email_method_routes_to_email(patched):
    ok, info = pipeline.run_profile(PROFILE, publish_method="email", ledger=Ledger())
    assert ok and info.startswith("emailed:")
    assert "email" in patched and "api" not in patched


def test_quality_gate_blocks_thin_post(monkeypatch):
    monkeypatch.setattr(pipeline, "fetch_top_news", lambda **k: list(NEWS))
    monkeypatch.setattr(pipeline, "enrich_news", lambda items: 0)
    monkeypatch.setattr(
        pipeline, "generate_post",
        lambda **k: GeneratedPost(title="Too Thin", html="<h2>Hi</h2><p>short</p>", tags=[]),
    )
    published = {}
    monkeypatch.setattr(pipeline, "publish_to_blogger",
                        lambda **k: published.setdefault("called", True))
    led = Ledger()
    ok, info = pipeline.run_profile(PROFILE, ledger=led)
    assert not ok and info.startswith("quality-gate:")
    assert "called" not in published        # never reached publish
    assert led.entries == []                # nothing recorded
