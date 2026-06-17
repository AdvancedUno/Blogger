"""Tests for setup_pages create / skip / overwrite logic (no network)."""
from __future__ import annotations

import pytest

pytest.importorskip("googleapiclient")  # setup_pages imports HttpError at import time

import setup_pages  # noqa: E402
from blogkit.profiles.base import BlogProfile  # noqa: E402

PROFILE = BlogProfile(
    slug="t_blog", name="T Blog", blog_id="123", run_group=1,
    persona="veteran CISO", rss_queries=["kw one"], featured_image=False,
)


class _Exec:
    def __init__(self, val):
        self._val = val

    def execute(self):
        return self._val


class _Pages:
    def __init__(self, store):
        self.store = store

    def list(self, blogId, maxResults=100, pageToken=None):  # noqa: N803
        return _Exec({"items": self.store["existing"]})

    def insert(self, blogId, body, isDraft=False):  # noqa: N803
        self.store["ops"].append(("insert", body["title"]))
        return _Exec({"url": f"https://b/p/{body['title']}.html", "id": "new"})

    def update(self, blogId, pageId, body):  # noqa: N803
        self.store["ops"].append(("update", pageId, body["title"]))
        return _Exec({"url": f"https://b/p/{body['title']}.html", "id": pageId})


class _Blogs:
    def get(self, blogId):  # noqa: N803
        return _Exec({"name": "T Blog", "url": "https://t.example.com"})


class _Service:
    def __init__(self, store):
        self.store = store

    def blogs(self):
        return _Blogs()

    def pages(self):
        return _Pages(self.store)


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    monkeypatch.setattr(setup_pages.time, "sleep", lambda *a, **k: None)


def _run(existing, *, dry_run=False, overwrite=False):
    store = {"existing": existing, "ops": []}
    result = setup_pages._process_blog(_Service(store), PROFILE, dry_run, overwrite)
    return result, store["ops"]


def test_creates_all_pages_on_empty_blog():
    (created, updated, skipped, failed), ops = _run([])
    assert (created, updated, skipped, failed) == (len(setup_pages.PAGES), 0, 0, 0)
    assert all(op[0] == "insert" for op in ops)
    assert len(ops) == len(setup_pages.PAGES)


def test_skips_existing_without_overwrite():
    existing = [{"title": t, "id": f"id-{t}"} for t, _ in setup_pages.PAGES]
    (created, updated, skipped, failed), ops = _run(existing)
    assert (created, updated, skipped, failed) == (0, 0, len(setup_pages.PAGES), 0)
    assert ops == []  # nothing written


def test_overwrite_updates_existing_in_place():
    existing = [{"title": "About Us", "id": "about-1"}]
    (created, updated, skipped, failed), ops = _run(existing, overwrite=True)
    assert updated == 1
    assert created == len(setup_pages.PAGES) - 1
    assert skipped == 0 and failed == 0
    # The pre-existing page is UPDATED by its id, not re-inserted.
    assert ("update", "about-1", "About Us") in ops
    assert not any(op[0] == "insert" and op[1] == "About Us" for op in ops)


def test_dry_run_writes_nothing():
    (created, updated, skipped, failed), ops = _run([], dry_run=True)
    assert created == len(setup_pages.PAGES)
    assert ops == []  # dry-run never calls insert/update


def test_placeholder_blog_id_is_skipped():
    prof = BlogProfile(
        slug="staged", name="Staged", blog_id="TODO_staged", run_group=1,
        persona="x", rss_queries=["k"], featured_image=False, enabled=False,
    )
    store = {"existing": [], "ops": []}
    assert setup_pages._process_blog(_Service(store), prof, False, False) == (0, 0, 0, 0)
    assert store["ops"] == []
