"""Every blog profile loads and validates, and the registry is consistent."""

from __future__ import annotations

from blogkit.core.styles import STYLE_PRESETS
from blogkit.profiles.registry import all_profiles, by_group, get_profile


def test_all_profiles_load():
    profs = all_profiles()
    assert profs, "no profiles discovered"
    slugs = [p.slug for p in profs]
    assert len(slugs) == len(set(slugs)), "duplicate slug"


def test_profiles_are_well_formed():
    for p in all_profiles():
        assert p.blog_id and not p.blog_id.startswith("["), p.slug
        assert p.rss_queries, f"{p.slug} has no rss_queries"
        assert p.persona, f"{p.slug} has no persona"
        # image_styles must reference the known catalog
        for s in p.image_styles:
            assert s in STYLE_PRESETS, f"{p.slug}: unknown style {s!r}"


def test_style_pool_resolves_to_prompts():
    p = all_profiles()[0]
    pool = p.style_pool()
    assert pool and all(isinstance(s, str) and s for s in pool)


def test_get_and_group_lookup():
    p = all_profiles()[0]
    assert get_profile(p.slug) is p
    assert p in by_group(p.run_group)


def test_unknown_slug_raises():
    import pytest

    with pytest.raises(KeyError):
        get_profile("does_not_exist")
