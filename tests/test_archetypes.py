"""Author-archetype presets: assignment coverage, distinctness, directive."""

from __future__ import annotations

import pytest

from blogkit.core.archetypes import (
    ARCHETYPE_BY_SLUG,
    ARCHETYPES,
    DEFAULT_ARCHETYPE,
    build_archetype_directive,
    get_archetype,
    resolve_archetype_name,
)
from blogkit.core.formats import resolve_format_name
from blogkit.profiles.base import BlogProfile
from blogkit.profiles.registry import all_profiles


def test_default_archetype_exists():
    assert DEFAULT_ARCHETYPE in ARCHETYPES


def test_assignments_reference_real_archetypes():
    for slug, name in ARCHETYPE_BY_SLUG.items():
        assert name in ARCHETYPES, f"{slug} -> unknown archetype {name!r}"


def test_every_profile_resolves_to_a_valid_archetype():
    for p in all_profiles():
        name = resolve_archetype_name(p.slug, p.author_archetype)
        assert name in ARCHETYPES, f"{p.slug} -> {name!r}"


def test_archetypes_distinct_within_each_format_bucket():
    # No two blogs that share a FORMAT may share an ARCHETYPE — that is what
    # keeps every blog's combined identity unique.
    by_format: dict[str, list[str]] = {}
    for p in all_profiles():
        fmt = resolve_format_name(p.slug, p.post_format)
        arch = resolve_archetype_name(p.slug, p.author_archetype)
        by_format.setdefault(fmt, []).append(arch)
    for fmt, archs in by_format.items():
        assert len(archs) == len(set(archs)), f"duplicate archetype in format {fmt!r}: {archs}"


def test_get_archetype_falls_back():
    assert get_archetype("").name == DEFAULT_ARCHETYPE
    assert get_archetype("nope").name == DEFAULT_ARCHETYPE
    assert get_archetype("the_professor").name == "the_professor"


def test_resolve_archetype_override_wins():
    assert resolve_archetype_name("anything", "the_engineer") == "the_engineer"
    assert resolve_archetype_name("unmapped", "") == DEFAULT_ARCHETYPE
    assert resolve_archetype_name("observability_sre", "") == "the_founder"


def test_directive_carries_role_and_humanizing():
    arch = ARCHETYPES["the_reporter"]
    out = build_archetype_directive(arch)
    assert "HUMAN AUTHOR PERSONA" in out
    assert "investigative business reporter" in out
    assert "Open the piece" in out
    # at least one of its signature moves is present
    assert any(sig.split()[0] in out for sig in arch.signatures)


def _profile(**kw):
    base = dict(slug="arch_test", name="x", blog_id="123", persona="p", rss_queries=["q"])
    base.update(kw)
    return BlogProfile(**base)


def test_profile_accepts_empty_and_valid_archetype():
    assert _profile().author_archetype == ""
    assert _profile(author_archetype="the_skeptic").author_archetype == "the_skeptic"


def test_profile_rejects_unknown_archetype():
    with pytest.raises(ValueError):
        _profile(author_archetype="the_robot")
