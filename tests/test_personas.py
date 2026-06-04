"""Style-muse presets: coverage, distinctness, directive sections, safety."""

from __future__ import annotations

import pytest

from blogkit.core.formats import resolve_format_name
from blogkit.core.personas import (
    PERSONA_BY_SLUG,
    PERSONAS,
    build_persona_directive,
    get_persona,
    resolve_persona_name,
)
from blogkit.profiles.base import BlogProfile
from blogkit.profiles.registry import all_profiles


def test_assignments_reference_real_personas():
    for slug, name in PERSONA_BY_SLUG.items():
        assert name in PERSONAS, f"{slug} -> unknown persona {name!r}"


def test_every_profile_has_a_persona():
    # Every blog should resolve to a real style muse (no archetype fallback).
    for p in all_profiles():
        name = resolve_persona_name(p.slug, p.style_persona)
        assert name in PERSONAS, f"{p.slug} -> {name!r}"


def test_personas_distinct_within_each_format_bucket():
    by_format: dict[str, list[str]] = {}
    for p in all_profiles():
        fmt = resolve_format_name(p.slug, p.post_format)
        muse = resolve_persona_name(p.slug, p.style_persona)
        by_format.setdefault(fmt, []).append(muse)
    for fmt, muses in by_format.items():
        assert len(muses) == len(set(muses)), f"duplicate muse in format {fmt!r}: {muses}"


def test_get_persona_and_resolve():
    assert get_persona("") is None
    assert get_persona("not_a_real_one") is None
    assert get_persona("michael_lewis").name == "Michael Lewis"
    assert resolve_persona_name("anything", "matt_levine") == "matt_levine"
    assert resolve_persona_name("b2b_payment_rails", "") == "matt_levine"
    assert resolve_persona_name("totally_unmapped", "") == ""


def test_directive_has_all_required_sections():
    out = build_persona_directive(PERSONAS["michael_lewis"])
    for section in ("STYLE MUSE", "PERSONA INJECTION", "LINGUISTIC FINGERPRINT",
                    "STRUCTURAL BLUEPRINT", "SIGNATURE QUIRKS",
                    "ANTI-AI GUARDRAILS", "ENTERTAINMENT MANDATE",
                    "SEARCH & MONETIZATION"):
        assert section in out, section
    # The muse-not-mask safety framing must be present with the name filled in.
    assert "STYLE MUSE, NOT A MASK" in out
    assert "Michael Lewis" in out


def test_directive_forbids_ai_cliches_and_keeps_it_brand_safe():
    out = build_persona_directive(PERSONAS["orwell"]).lower()
    for forbidden in ("delve", "tapestry", "navigating the landscape", "in conclusion"):
        assert forbidden in out  # they appear in the negative/ban list
    assert "adsense-safe" in out


def test_persona_fields_are_populated():
    for key, p in PERSONAS.items():
        assert p.persona_injection and p.linguistic_fingerprint and p.structural_blueprint, key
        assert p.quirks, key


def _profile(**kw):
    base = dict(slug="muse_test", name="x", blog_id="123", persona="p", rss_queries=["q"])
    base.update(kw)
    return BlogProfile(**base)


def test_profile_accepts_empty_and_valid_persona():
    assert _profile().style_persona == ""
    assert _profile(style_persona="hemingway").style_persona == "hemingway"


def test_profile_rejects_unknown_persona():
    with pytest.raises(ValueError):
        _profile(style_persona="william_shakespeare")
