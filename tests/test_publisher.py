"""Blogger publisher — category-label mapping + payload assembly."""

from __future__ import annotations

import blogkit.core.publisher as publisher
from blogkit.core.publisher import (
    CATEGORY_BY_SLUG,
    _titleize,
    category_for,
    publish_to_blogger,
)
from blogkit.profiles.registry import all_profiles


def test_category_for_known_slug_returns_mapped_label():
    assert category_for("dataops_vector_dbs") == "DataOps"
    assert category_for("programmatic_adtech_privacy") == "AdTech Privacy"


def test_category_for_unknown_slug_titleizes():
    assert category_for("some_new_vertical") == "Some New Vertical"
    assert _titleize("a_b_c") == "A B C"


def test_category_for_blank_slug_is_empty():
    assert category_for("") == ""
    assert category_for("   ") == ""


def test_every_profile_slug_has_a_curated_category():
    # Guard against drift: a new blog must get an explicit, curated label
    # rather than silently riding the title-cased fallback.
    missing = [p.slug for p in all_profiles() if p.slug not in CATEGORY_BY_SLUG]
    assert not missing, f"profiles missing a CATEGORY_BY_SLUG entry: {missing}"


def test_category_labels_are_clean_and_non_empty():
    for slug, label in CATEGORY_BY_SLUG.items():
        assert label and label.strip() == label, slug
        assert "_" not in label, slug   # human-readable, not a raw slug


class _FakeInsert:
    def __init__(self, captured: dict, body: dict, **kw):
        captured["body"] = body
        captured["isDraft"] = kw.get("isDraft")

    def execute(self) -> dict:
        return {"url": "https://blog.example/post", "id": "42"}


class _FakePosts:
    def __init__(self, captured: dict):
        self._captured = captured

    def insert(self, blogId: str, body: dict, isDraft: bool = False):  # noqa: N803
        return _FakeInsert(self._captured, body, isDraft=isDraft)


class _FakeService:
    def __init__(self, captured: dict):
        self._captured = captured

    def posts(self):
        return _FakePosts(self._captured)


def _patch_service(monkeypatch) -> dict:
    captured: dict = {}
    monkeypatch.setattr(publisher, "_build_service", lambda: _FakeService(captured))
    return captured


def test_payload_labels_is_single_mapped_category(monkeypatch):
    captured = _patch_service(monkeypatch)
    url = publish_to_blogger(
        blog_id="123", title="T", html_content="<p>x</p>",
        slug="dataops_vector_dbs",
    )
    assert url == "https://blog.example/post"
    assert captured["body"]["labels"] == ["DataOps"]


def test_slug_labels_override_model_tags(monkeypatch):
    # When a slug is given, caller-supplied (model-invented) tags are ignored.
    captured = _patch_service(monkeypatch)
    publish_to_blogger(
        blog_id="123", title="T", html_content="<p>x</p>",
        tags=["RandomGeminiTag", "AnotherOne"],
        slug="finops_cloud_cost",
    )
    assert captured["body"]["labels"] == ["FinOps"]


def test_unmapped_slug_falls_back_to_titleized_label(monkeypatch):
    captured = _patch_service(monkeypatch)
    publish_to_blogger(
        blog_id="123", title="T", html_content="<p>x</p>",
        slug="brand_new_blog",
    )
    assert captured["body"]["labels"] == ["Brand New Blog"]


def test_no_slug_falls_back_to_caller_tags(monkeypatch):
    # Legacy/direct callers without a slug still get their explicit tags.
    captured = _patch_service(monkeypatch)
    publish_to_blogger(
        blog_id="123", title="T", html_content="<p>x</p>",
        tags=["Manual"],
    )
    assert captured["body"]["labels"] == ["Manual"]
