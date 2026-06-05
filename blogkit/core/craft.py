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

import hashlib
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
    # Vague architecture filler — practitioners name the mechanism instead.
    "infrastructure orchestration",
    "intelligent context routers",
    # High-altitude executive coinages — use the field's real working jargon.
    "structural margin crisis",
    "tollbooth architecture",
)


# ---------------------------------------------------------------------------
# Absolute proclamations (Nuance Tax). Sensationalist, sweeping phrases that
# real operators never use — they live in gray areas and bound their claims
# with real constraints. Banned in the prompt and counted as a gate backstop,
# kept as a SEPARATE list from BANNED_BUZZWORDS so the two are reported
# distinctly. Matched as whole phrases (not bare words like "always") to avoid
# false positives on legitimate prose.
# ---------------------------------------------------------------------------
ABSOLUTE_PROCLAMATIONS: tuple[str, ...] = (
    "the death of",
    "the fatal mistake",
    "always wins",
    "completely failing",
    "broke the thesis",
)


def _phrase_hits(text: str, phrases: tuple[str, ...]) -> dict[str, int]:
    """Count case-insensitive occurrences of each phrase that appears (count>=1)."""
    low = text.lower()
    hits: dict[str, int] = {}
    for phrase in phrases:
        n = len(re.findall(re.escape(phrase), low))
        if n:
            hits[phrase] = n
    return hits


def buzzword_hits(text: str) -> dict[str, int]:
    """Count occurrences of each banned buzzword in ``text`` (case-insensitive).

    Returns only phrases that actually appear (count >= 1). Used by the quality
    gate as a backstop behind the prompt-level ban.
    """
    return _phrase_hits(text, BANNED_BUZZWORDS)


def absolute_hits(text: str) -> dict[str, int]:
    """Count occurrences of each banned absolute proclamation (case-insensitive).

    Backstop behind the Nuance Tax: the prompt forbids sweeping absolutes, this
    catches a slip that survives generation.
    """
    return _phrase_hits(text, ABSOLUTE_PROCLAMATIONS)


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
    "4. LEAD WITH INFORMATION GAIN AND A SPECIFIC POINT OF VIEW. Avoid safe, "
    "forgettable industry consensus — say something a reader can't get from the "
    "first ten search results. But carry that view with operational nuance, NOT a "
    "sweeping \"everyone is wrong, here's the fix\" proclamation; that debunking "
    "template is itself a tired formula. E.g. not \"software creates value\" but "
    "\"most deployments here stall before a line of code ships, because it's a "
    "data-collection bottleneck more than a software problem\".",
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


# ---------------------------------------------------------------------------
# Practitioner laws — the firsthand-production discipline that separates a
# well-researched essay from analysis written by someone who has actually run
# the system. These override the style muse wherever they conflict (e.g. the
# one-analogy cap overrides an analogy-heavy muse like Tim Urban or Feynman).
# Law 1's vocabulary is topic-conditional: the model picks engineering metrics
# for technical topics and financial controls for corporate/B2B topics, judged
# from the keyword + Source Data it's given.
# ---------------------------------------------------------------------------
PRACTITIONER_LAWS = "\n".join([
    "PRACTITIONER LAWS (write from firsthand production experience, not "
    "research — these OVERRIDE the style muse wherever they conflict):",
    "",
    "1. ENGINEERING & FINANCIAL GRANULARITY. Never hide behind vague "
    "architecture buzzwords (e.g. \"infrastructure orchestration\", \"intelligent "
    "context routers\"). For a TECHNICAL topic (cloud, DevOps, RAG, data "
    "engineering, security), ground the argument in hard, measurable realities — "
    "p95/p99 latency, token counts, cache hit rates, QPS, embedding throughput, "
    "retrieval recall (recall@k), GPU utilization, serialization overhead, network "
    "RTT, vector index sizing. For a CORPORATE / B2B FINANCE topic, replace "
    "sweeping drama with concrete structural controls — SOX controls, "
    "exception-handling workflows, audit trails, approval matrices, cash-flow "
    "projections. Use whichever vocabulary the topic actually calls for.",
    "",
    "2. MESSY CASE NUMBERS — NO CLEAN ROUND METRICS. Banned: tidy figures like "
    "\"50,000 queries daily, a 40% reduction, a 26% jump\" — they scream AI. Use "
    "asymmetric, fractured, oddly specific numbers, and break a headline metric "
    "into its components in sequence. Not \"latency dropped 40%\" but: \"peak "
    "traffic pushed p95 to 6.2s; a profiling trace showed vector retrieval ate "
    "2.1s, cross-cluster reranking added 900ms, and token serialization a brutal "
    "400ms.\" Keep such vignettes anonymized/composite, never pinned on a real "
    "named company.",
    "",
    "3. ONE ANALOGY MAXIMUM. At most a SINGLE analogy in the entire piece, two "
    "sentences or fewer, and only if it genuinely clarifies. NO stacked or tiered "
    "metaphors (no submarine bulkheads, bananas-vs-dragonfruit, toll roads, "
    "forgetful executives, filing cabinets, librarians, or riverbank radio "
    "shacks) — that multi-analogy habit is a blatant AI fingerprint. State the "
    "technical or operational friction in the field's own jargon instead — e.g. "
    "\"the retriever becomes the bottleneck when vector search, graph traversal, "
    "and context assembly run sequentially instead of concurrently.\" This cap "
    "overrides any muse whose habit is to explain through analogy.",
    "",
    "4. THE OPERATOR'S CAVEAT — NUANCE OVER CERTAINTY. Avoid absolute claims "
    "(\"always\", \"completely fails\", \"the vendor always wins\"). Signal "
    "real-world testing with measured hedges: \"in our experience\", \"this depends "
    "heavily on\", \"we frequently see\", \"true for relational datasets, but it "
    "breaks under high-cardinality joins\". AND — this applies to EVERY post, not "
    "just the critical ones: include a dedicated section that actively argues "
    "against your own thesis — where it breaks down, or the concrete benefit of "
    "the opposing approach (the high-volume, low-complexity, or standardized "
    "scenarios where it genuinely wins). Give that section its own vivid heading, "
    "e.g. \"Where [X] Actually Holds Up\".",
    "",
    "5. INCIDENT-GRADE FAQ. The Frequently Asked Questions must read like they "
    "came from real production incidents, client escalations, or angry support "
    "tickets — never a polite restatement of the article's themes. Not \"How does "
    "the software reduce emissions?\" but \"What happens to our compliance audit "
    "trail when a utility provider's Green Button API goes dark for three straight "
    "months?\"",
])


# ---------------------------------------------------------------------------
# Narrative laws — kill the predictable single-template article. CRAFT_LAWS and
# PRACTITIONER_LAWS make the prose human and specific; these stop every post in
# the network from marching through the same "industry is wrong -> big risk ->
# executive fix" arc with sensational, absolute language. The per-piece
# NARRATIVE_MODES rotation (below) handles structural variety; this block
# handles tone (no absolutes), honesty (ground or flag every metric), and
# register (operator jargon, not consultant coinage).
# ---------------------------------------------------------------------------
_ABSOLUTES_INLINE = ", ".join(f'"{w}"' for w in ABSOLUTE_PROCLAMATIONS)

NARRATIVE_LAWS = "\n".join([
    "NARRATIVE LAWS (operate in the gray areas a real practitioner lives in):",
    "",
    "1. PAY THE NUANCE TAX — NO ABSOLUTE PROCLAMATIONS. Real operators don't deal "
    "in sweeping certainties. Never use sensational absolutes such as: "
    f"{_ABSOLUTES_INLINE}, \"X is dead\", \"never works\", \"the fatal flaw\". "
    "Replace each with a claim bounded by a real-world constraint. Not \"the death "
    "of screen scraping\" but \"screen scraping is becoming operationally unviable "
    "as banks aggressively migrate to OAuth-based connectivity\". Not \"the "
    "software vendor always wins\" but \"software vendors frequently capture a "
    "disproportionate share of the economic margins\".",
    "",
    "2. GROUND EVERY METRIC, OR FLAG IT AS ILLUSTRATIVE. Any precise figure "
    "(\"8.2s latency\", \"1,142 workstations\", \"a 10% error rate\") must trace "
    "to the Source Data, a named incident report, or a regulatory filing. If it's "
    "only illustrative, say so in the sentence — e.g. \"in a typical high-volume "
    "pipeline, an unoptimized stage often runs a baseline error rate near...\". "
    "Never present an invented number as a measured fact.",
    "",
    "3. OPERATOR JARGON, NOT EXECUTIVE COINAGE. Drop high-altitude inventions like "
    "\"structural margin crisis\" or \"tollbooth architecture\". Reach for the "
    "field's real working vocabulary — for fintech / open banking that means OAuth "
    "token-refresh failures, consent-expiration windows, API versioning conflicts, "
    "and bank-specific endpoint variance: the things the engineer on that "
    "integration actually fights at 2 a.m.",
])


# ---------------------------------------------------------------------------
# Narrative-mode rotation (Narrative-Diversity Law 1). Three distinct
# structural arcs. ONE is injected per piece (core/generator.py picks it
# deterministically from the topic), so across the network the same template
# never repeats — and no single prompt carries all three. This is what stops
# every blog defaulting to the "debunk / shock-and-awe risk" structure.
# ---------------------------------------------------------------------------
NARRATIVE_MODES: tuple[tuple[str, str], ...] = (
    ("operational_tradeoff",
     "STRUCTURE THIS PIECE AS AN OPERATIONAL TRADE-OFF. Do NOT frame it as "
     "\"the industry is wrong, here is the fix.\" Take two genuinely valid "
     "approaches and weigh the friction of each honestly — what each one costs, "
     "where each one breaks, who each one actually suits. Refuse to crown a "
     "single winner; land on a concrete \"it depends on...\" with the deciding "
     "variable named."),
    ("autopsy",
     "STRUCTURE THIS PIECE AS AN AUTOPSY. Build from the bottom up around one "
     "specific, messy incident or technical bottleneck: what was noticed first, "
     "what the investigation found underneath, the chain of contributing causes, "
     "and what it actually cost. Reconstruct it like an incident review, not a "
     "thesis stated up front. Keep the incident anonymized / composite — never "
     "pinned on a real named company."),
    ("practical_evolution",
     "STRUCTURE THIS PIECE AS A PRACTICAL EVOLUTION. Document a slow, uneven "
     "transition (for example, screen-scraping giving way to OAuth connectivity) "
     "as the half-finished migration it really is — what is moving, what is "
     "stuck, who is dragging their feet and why. Do NOT proclaim a dramatic "
     "\"death\" or \"revolution\"; trace the gradual, constraint-driven shift."),
)


def pick_narrative_mode(seed_text: str) -> str:
    """Deterministically pick one narrative-mode directive from ``seed_text``.

    Hash-based so the same topic always gets the same structure (stable across
    retries) while the network as a whole rotates through all three arcs.
    """
    h = int(hashlib.sha256(seed_text.encode("utf-8")).hexdigest(), 16)
    return NARRATIVE_MODES[h % len(NARRATIVE_MODES)][1]
