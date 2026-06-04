"""Network-wide craft laws — the non-negotiable rules baked into every voice.

The style muses (core/personas.py) and author archetypes (core/archetypes.py)
give each blog a distinct *voice*. This module adds the rules that apply to ALL
of them at once: the structural and substantive discipline that turns a competent
outsider's report into gritty, opinionated analysis by an industry practitioner.

Two things live here so the prompt and the post-publish quality gate enforce the
SAME contract:

* ``CRAFT_LAWS`` — a prompt block injected after every persona/archetype directive.
* ``BANNED_BUZZWORDS`` — corporate filler that's forbidden in the prompt AND
  used as a backstop check in core/quality.py.

Keeping them in one place means a phrase added to the ban list is enforced both
ways without drift.
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Buzzword tax (Law 2). Plain, specific corporate filler that signals a
# consultant padding a word count rather than an operator describing reality.
# These are banned in the prompt and counted by the quality gate as a backstop.
# ---------------------------------------------------------------------------
BANNED_BUZZWORDS: tuple[str, ...] = (
    "strategic asset management tool",
    "core financial underwriting requirement",
    "capital stack",
    "institutional-grade software",
    "smart capital",
    "landscape optimization",
)


def buzzword_hits(text: str) -> dict[str, int]:
    """Count occurrences of each banned buzzword in ``text`` (case-insensitive).

    Returns only phrases that actually appear (count >= 1). Used by the quality
    gate as a backstop behind the prompt-level ban.
    """
    low = text.lower()
    hits: dict[str, int] = {}
    for phrase in BANNED_BUZZWORDS:
        n = len(re.findall(re.escape(phrase), low))
        if n:
            hits[phrase] = n
    return hits


# ---------------------------------------------------------------------------
# The six structural laws (injected into every persona/archetype directive).
# Worded as direct instructions to the model. The FAQ / References carve-out in
# Law 1 is load-bearing: core/seo.extract_faqs needs the verbatim
# "Frequently Asked Questions" heading to emit FAQPage schema.
# ---------------------------------------------------------------------------
_BUZZWORDS_INLINE = ", ".join(f'"{w}"' for w in BANNED_BUZZWORDS)

CRAFT_LAWS = "\n".join([
    "NON-NEGOTIABLE CRAFT LAWS (these override any conflicting structural habit):",
    "",
    "1. STRIP THE AI SCAFFOLDING. Never use predictable, templated section "
    "labels — no \"The Setup\", \"The Stakes\", \"The Watch\", \"The Move\", "
    "\"Myth 1 / Myth 2 / Myth 3\", \"Risks & Bottlenecks\", \"Key Takeaways\", or "
    "any generic boilerplate heading. Write natural, magazine-style editorial "
    "subheadings that advance the story and name the specific thing — e.g. instead "
    "of \"Risks & Bottlenecks\" write something like \"The Broken Pipes in the "
    "Utility Data Layer\". (The single \"Frequently Asked Questions\" heading and "
    "the closing references heading are the ONLY fixed labels — keep those exactly "
    "as given; invent every other heading yourself.)",
    "",
    "2. PAY THE BUZZWORD TAX. Write like an operator who works in plain English, "
    "not a McKinsey consultant trying to hit a word count. Trade high-level jargon "
    f"for hard operational reality. Never use these phrases: {_BUZZWORDS_INLINE}.",
    "",
    "3. NAME REAL VENDORS AND RULES. Never make a generalized claim in a vacuum. "
    "When you mention a concept or a category of software, ground it by explicitly "
    "naming and briefly contrasting the real, relevant vendors, products, "
    "standards, or regulations in that niche — e.g. don't say \"sustainability "
    "software\", say \"Persefoni and Watershed handle enterprise carbon "
    "accounting, whereas Measurabl is built for real-estate portfolio data\". Only "
    "cite real, accurate players; never invent a product, a figure, or a fact "
    "about a named company.",
    "",
    "4. LEAD WITH INFORMATION GAIN AND A CONTRARIAN ANGLE. Avoid safe, forgettable "
    "industry consensus. Open with a distinct, slightly cynical or contrarian take "
    "and challenge the niche's mainstream assumptions — e.g. not \"software creates "
    "value\" but \"most deployments here fail before a line of code ships, because "
    "it's a data-collection bottleneck, not a software problem\".",
    "",
    "5. USE TEXTURED CASE VIGNETTES, NOT CLEAN HYPOTHETICALS. Never use suspiciously "
    "round, perfectly tidy numbers (\"a 200,000 sq ft building saving $0.40 per sq "
    "ft\"). Instead write gritty, specific, slightly messy vignettes that read like "
    "real operational history — e.g. \"a 430,000-sq-ft office portfolio in a "
    "secondary market dragged its feet on an HVAC retrofit until an audit found the "
    "chiller loops were overriding the night-setback schedule, bleeding $18,000 a "
    "month\". Keep such vignettes anonymized/composite — never attribute invented "
    "specifics to a real, named organization.",
    "",
    "6. SELF-CORRECT AND CAVEAT. Challenge your own core thesis inside the body. "
    "Include the real-world operational friction, dependency, or human element "
    "required to actually make the technology work — the professional skepticism a "
    "practitioner would voice, not a vendor.",
])
