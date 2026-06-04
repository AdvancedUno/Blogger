"""Pure-logic tests for the generator (no Gemini SDK / network needed —
the SDK import is lazy inside generate_post)."""

from __future__ import annotations

from blogkit.core.generator import (
    SYSTEM_INSTRUCTION_EN,
    Voice,
    _compose_system_instruction,
    _parse_response,
)


def test_empty_voice_uses_base_prompt():
    assert _compose_system_instruction(Voice(), "Any Blog", None) == SYSTEM_INSTRUCTION_EN
    assert _compose_system_instruction(None, "Any Blog", None) == SYSTEM_INSTRUCTION_EN


def test_full_override_wins():
    v = Voice(persona="CISO", tone="punchy")
    assert _compose_system_instruction(v, "Blog", "FULL OVERRIDE") == "FULL OVERRIDE"


def test_voice_lock_injects_all_fields():
    v = Voice(
        persona="veteran CISO",
        persona_brief="20 years in the SOC.",
        tone="skeptical, urgent",
        voice_traits=["lead with the breach cost", "name the CVE"],
        flow="open with the risk, close with the fix",
        banned_phrases=["game-changer"],
    )
    out = _compose_system_instruction(v, "Zero Trust Weekly", None)
    assert out.startswith(SYSTEM_INSTRUCTION_EN)
    assert "DOMAIN & SUBSTANCE LOCK" in out
    for fragment in ("Zero Trust Weekly", "veteran CISO", "skeptical, urgent",
                     "lead with the breach cost", "open with the risk",
                     "game-changer", "20 years in the SOC"):
        assert fragment in out, fragment


SAMPLE = """TITLE: Why CFOs Must Rethink RTP Integration
TAGS: PaymentRails, RealTimePayments, TreasuryTech
---
<h1>Why CFOs Must Rethink RTP Integration</h1>
<blockquote><p><strong>TL;DR</strong></p></blockquote>
<h2>Executive Briefing &amp; Macro Shift</h2>
<p>Concrete opening grounded in the data.</p>
"""


def test_parse_response_extracts_title_tags_body():
    post = _parse_response(SAMPLE)
    assert post.title == "Why CFOs Must Rethink RTP Integration"
    assert post.tags == ["PaymentRails", "RealTimePayments", "TreasuryTech"]
    assert "<h2" in post.html
    assert post.html.lstrip().startswith("<h1")


def test_parse_response_strips_code_fence():
    fenced = "```html\n" + SAMPLE + "```"
    post = _parse_response(fenced)
    assert post.title == "Why CFOs Must Rethink RTP Integration"
