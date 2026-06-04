"""Per-blog post-format presets: assignment coverage, structure, no TL;DR."""

from __future__ import annotations

import pytest

from blogkit.core.formats import (
    DEFAULT_FORMAT,
    FORMAT_BY_SLUG,
    FORMATS,
    build_user_prompt,
    get_format,
    resolve_format_name,
)
from blogkit.core.generator import _scrub_tldr
from blogkit.profiles.base import BlogProfile
from blogkit.profiles.registry import all_profiles


def test_default_format_exists():
    assert DEFAULT_FORMAT in FORMATS


def test_format_assignments_reference_real_formats():
    for slug, name in FORMAT_BY_SLUG.items():
        assert name in FORMATS, f"{slug} -> unknown format {name!r}"


def test_no_format_body_contains_tldr():
    for name, fmt in FORMATS.items():
        assert "tl;dr" not in fmt.body.lower(), f"{name} body still has TL;DR"
        assert "tl;dr" not in fmt.summary_label.lower()


def test_every_format_has_required_structure():
    # Load-bearing invariants every layout must keep so the parser + SEO
    # (FAQPage extraction, references soft-check, summary callout) keep working.
    # Note: a <table> and the literal "Bottom Line" are intentionally NOT
    # universal — that's part of the structural diversity across formats.
    for name, fmt in FORMATS.items():
        b = fmt.body.lower()
        assert "<h2" in b, name
        assert b.count("<blockquote") >= 2, name          # summary + closing callout
        assert "frequently asked questions" in b, name    # powers FAQPage schema
        assert "references" in b, name                     # references soft-check
        # FAQ Q&A must be <h3>question</h3><p>answer</p> for seo.extract_faqs.
        assert "<h3>" in fmt.body, name


def test_no_two_blogs_share_format_and_archetype():
    # Imported here to keep the format-only tests independent of archetypes.
    from blogkit.core.archetypes import resolve_archetype_name

    seen: dict[tuple[str, str], str] = {}
    for p in all_profiles():
        fmt = resolve_format_name(p.slug, p.post_format)
        arch = resolve_archetype_name(p.slug, p.author_archetype)
        key = (fmt, arch)
        assert key not in seen, (
            f"{p.slug} and {seen[key]} share format+archetype {key}"
        )
        seen[key] = p.slug


def test_every_profile_resolves_to_a_valid_format():
    # Guards that all 40 blogs map to a real format (or carry a valid override).
    for p in all_profiles():
        name = resolve_format_name(p.slug, p.post_format)
        assert name in FORMATS, f"{p.slug} -> {name!r}"


def test_get_format_falls_back_for_empty_or_unknown():
    assert get_format("").name == DEFAULT_FORMAT
    assert get_format("does_not_exist").name == DEFAULT_FORMAT
    assert get_format("playbook").name == "playbook"


def test_resolve_format_name_override_wins():
    assert resolve_format_name("anything", "deep_dive") == "deep_dive"
    assert resolve_format_name("unmapped_slug", "") == DEFAULT_FORMAT
    assert resolve_format_name("observability_sre", "") == "playbook"


def test_build_user_prompt_injects_inputs_and_is_brace_safe():
    fmt = get_format("buyers_guide")
    # news_context with literal braces must not raise (str.replace, not format).
    prompt = build_user_prompt(fmt, keyword="vendor risk", news_context="weird {braces} here")
    assert "vendor risk" in prompt
    assert fmt.summary_label in prompt
    assert "{braces}" in prompt
    assert "[Source Data]:" in prompt
    assert "tl;dr" not in prompt.lower()
    assert "TITLE:" in prompt and "TAGS:" in prompt and "<h1>" in prompt


def test_scrub_tldr_replaces_variants():
    label = "Key Takeaways"
    for variant in ("TL;DR", "TLDR", "TL; DR", "tl;dr"):
        out = _scrub_tldr(f"<strong>{variant} &mdash; brief</strong>", label)
        assert "TL" not in out.upper().replace("TAKEAWAYS", "")  # no residual TL;DR
        assert label in out


def _profile(**kw):
    base = dict(slug="fmt_test", name="x", blog_id="123", persona="p", rss_queries=["q"])
    base.update(kw)
    return BlogProfile(**base)


def test_profile_accepts_empty_and_valid_format():
    assert _profile().post_format == ""
    assert _profile(post_format="playbook").post_format == "playbook"


def test_profile_rejects_unknown_format():
    with pytest.raises(ValueError):
        _profile(post_format="nonsense")
