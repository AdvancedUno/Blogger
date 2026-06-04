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


@pytest.fixture
def patched(monkeypatch):
    """Stub fetch + generate; capture publish calls."""
    monkeypatch.setattr(pipeline, "fetch_top_news", lambda **k: list(NEWS))
    monkeypatch.setattr(
        pipeline, "generate_post",
        lambda **k: GeneratedPost(title="A Sharp B2B Title", html="<h2>Body</h2><p>x</p>",
                                  tags=["TagA"]),
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
