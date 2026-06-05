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
from dataclasses import dataclass

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
    "data-collection bottleneck more than a software problem\". Your real original "
    "contribution is SYNTHESIS the inputs lack individually: connect and contrast "
    "what the separate Source Data items (and any proprietary data provided) each "
    "report, surface the through-line or the contradiction no single article "
    "names, and assemble the comparison or timeline they're each missing — never "
    "just re-summarize one source. Then go further and ENGINEER information gain "
    "that isn't anywhere on the first page of results: introduce at least one "
    "genuinely original contribution of your own — a named framework, a coined "
    "term, a decision heuristic, a scoring rubric, or a blunt rule of thumb. Vary "
    "its form from post to post (never bolt the same labeled box onto every "
    "article), and keep it clearly your own analytical lens — an idea, never an "
    "invented fact or statistic.",
    "",
    "5. USE TEXTURED — BUT CLEARLY ILLUSTRATIVE — CASE VIGNETTES. Never use "
    "suspiciously round, perfectly tidy numbers (\"a 200,000 sq ft building saving "
    "$0.40 per sq ft\"). Write gritty, specific, slightly messy vignettes — but "
    "frame them plainly as representative composites (\"in a representative "
    "secondary-market office portfolio…\", \"a pattern that recurs…\"), NEVER as a "
    "specific real event you witnessed or measured. E.g. \"in a representative "
    "~430,000-sq-ft office portfolio, an HVAC retrofit might stall until an audit "
    "finds the chiller loops overriding the night-setback schedule — quietly "
    "bleeding on the order of $18,000 a month\". Keep them anonymized/composite, "
    "never pinned on a real named organization, and never dress an invented figure "
    "up as a measured fact.",
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
    "400ms.\" Frame the scenario as illustrative (\"in a typical high-traffic "
    "run…\"), not as a specific incident you personally measured; keep it "
    "anonymized/composite, never pinned on a real named company, and never present "
    "an invented number as a real measurement.",
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
# Prose-texture laws — defeat the DEFAULT LLM cadence. A model's rhythm (every
# thought glued to the next with the same connective tissue, uniform paragraph
# blocks, emphasis only on labels) is as much an AI fingerprint as its
# vocabulary. These are network-wide standing rules; the occasional devices
# (a one-sentence paragraph, a rule-of-thumb blockquote) are dialed in per
# piece via StructurePlan so they stay "time to time", not every post.
# ---------------------------------------------------------------------------
TEXTURE_LAWS = "\n".join([
    "PROSE TEXTURE LAWS (the rhythm of the prose is as much an AI tell as the "
    "words — break it):",
    "",
    "1. KILL THE LOOPING TRANSITIONS. LLMs bolt every sentence to the next with "
    "the same connective tissue. Do NOT lean on \"That said\", \"That being "
    "said\", \"Ultimately\", \"Importantly\", \"Notably\", \"Crucially\", "
    "\"What's more\", \"Moreover\", \"Furthermore\", \"Additionally\", \"Simply "
    "put\", \"In other words\", \"Here's the thing\", \"Here's the kicker\", "
    "\"The reality is\", \"The truth is\", \"Make no mistake\", \"At its core\", "
    "\"On the flip side\". Never open two paragraphs in a row with a transition "
    "word — let most paragraphs start cold on a concrete subject. And avoid the "
    "signature \"it's not just X, it's Y\" / \"this isn't about X; it's about Y\" "
    "antithesis construction entirely; it is a dead giveaway.",
    "",
    "2. BOLD MID-SENTENCE, NOT JUST LABELS. Use <strong> to spotlight the "
    "load-bearing phrase INSIDE a sentence — the surprising figure, the "
    "counterintuitive claim — not only at the start of a bullet or a definition. "
    "Use it sparingly enough that it still carries weight.",
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


# ---------------------------------------------------------------------------
# Per-piece structural plan (anti scaled-content fingerprint).
# Every post in the network sharing the SAME fixed scaffold (summary box ->
# sections -> FAQ -> closing callout -> References, at a fixed length) is a
# programmatic signature a classifier can flag regardless of how human the
# prose is. This varies the *shape* per piece — length, section count, and
# which optional elements appear — deterministically from the topic seed.
#
# "Moderate" policy (chosen deliberately): the FAQ and the References/Sources
# list ALWAYS stay (they carry FAQPage schema + outbound-citation trust). Only
# the summary callout, mid-article pull-quote, comparison table, and closing
# callout are made probabilistic. Lengths stay >= the quality gate's MIN_WORDS
# floor with margin so a plan never plans a post into a thin-content rejection.
# ---------------------------------------------------------------------------
_LENGTH_BANDS: tuple[int, ...] = (1100, 1350, 1600, 1850, 2100)


@dataclass(frozen=True)
class StructurePlan:
    """The shape of ONE post. FAQ + References are always kept and so are not
    represented here — only the variable elements are."""

    target_words: int
    sections: int            # number of main <h2> body sections
    summary_callout: bool    # opening <blockquote> summary box
    pull_quote: bool         # one mid-article <blockquote>
    comparison_table: bool   # a comparison <table> (only if material supports)
    closing_callout: bool    # closing <blockquote>
    data_visual: bool        # one rendered chart/visual (see core/charts.py)
    one_sentence_para: bool  # a deliberate one-sentence paragraph for punch
    rule_of_thumb: bool      # a hot-take / "Rule of Thumb" <blockquote>
    # Defaulted (appended) so existing positional StructurePlan(...) callers
    # keep working. These vary the two elements that otherwise stay byte-stable
    # across a blog's posts — the FAQ length and the summary-box bullet count.
    faq_count: int = 2       # number of Q&A pairs in the FAQ (heading stays fixed)
    summary_bullets: int = 3 # bullets in the opening summary callout, when present


def plan_structure(seed_text: str) -> StructurePlan:
    """Deterministically derive a StructurePlan from ``seed_text``.

    Salted independently of the angle/narrative-mode picks so shape varies on
    its own axis, and stable for a given topic so retries don't reshuffle it.
    """
    h = int(hashlib.sha256((seed_text + "::structure").encode("utf-8")).hexdigest(), 16)
    target = _LENGTH_BANDS[h % len(_LENGTH_BANDS)]
    h //= 97
    sections = 3 + (h % 4)          # 3..6 main sections
    h //= 97
    summary = (h % 10) < 7          # ~70% keep the summary box
    h //= 10
    pull = (h % 10) < 6             # ~60% a pull-quote
    h //= 10
    table = (h % 10) < 4            # ~40% a comparison table
    h //= 10
    closing = (h % 10) < 6          # ~60% a closing callout
    h //= 10
    visual = (h % 10) < 3           # ~30% a rendered data visual (occasional treat)
    h //= 10
    one_sentence = (h % 10) < 4     # ~40% a deliberate one-sentence paragraph
    h //= 10
    rot = (h % 10) < 3              # ~30% a rule-of-thumb / hot-take blockquote
    h //= 10
    faq_count = 2 + (h % 3)        # 2..4 FAQ questions (heading stays verbatim)
    h //= 3
    summary_bullets = 3 + (h % 3)  # 3..5 bullets in the opening summary callout
    return StructurePlan(
        target_words=target, sections=sections, summary_callout=summary,
        pull_quote=pull, comparison_table=table, closing_callout=closing,
        data_visual=visual, one_sentence_para=one_sentence, rule_of_thumb=rot,
        faq_count=faq_count, summary_bullets=summary_bullets,
    )


def render_structure_plan(plan: StructurePlan) -> str:
    """Render a StructurePlan as a prompt directive injected per piece."""
    lines = [
        "STRUCTURAL PLAN FOR THIS PIECE — deliberately shaped so no two posts "
        "share the same skeleton (this is what defeats programmatic / "
        "scaled-content pattern detection). It OVERRIDES the layout template's "
        "optional furniture. The Frequently Asked Questions section and the "
        "closing References/Sources list ALWAYS stay; everything else here is for "
        "THIS post only:",
        f"- Target length: about {plan.target_words} words. Write to the ideas — "
        "never pad, restate, or repeat to hit the number.",
        f"- Organize the body into roughly {plan.sections} main <h2> sections "
        "(split or merge to fit the material; don't force an exact count).",
        (f"- Open with a <blockquote> summary callout of {plan.summary_bullets} "
         "bullets, under a SHORT heading you write fresh for this piece (never "
         "the template's stock label, never \"TL;DR\")." if plan.summary_callout
         else "- Do NOT open with a summary callout <blockquote>; go straight into "
              "a strong lede."),
        ("- Place exactly one <blockquote> pull-quote mid-article."
         if plan.pull_quote
         else "- Do NOT use a mid-article pull-quote in this piece."),
        ("- Include a comparison <table> ONLY if the material genuinely supports a "
         "side-by-side; otherwise skip it." if plan.comparison_table
         else "- Do NOT use a comparison <table> in this piece."),
        ("- End with a short closing <blockquote> callout."
         if plan.closing_callout
         else "- Do NOT end with a closing callout <blockquote>; land on a strong "
              "final line instead."),
        ("- Include ONE data visual (a chart) where it genuinely clarifies a "
         "comparison, trend, or share — follow the CHART FORMAT spec below. Skip "
         "it if you'd have to invent the numbers to fill it."
         if plan.data_visual
         else "- Do NOT include a chart or data visual in this piece."),
        (f"- Write {plan.faq_count} Q&A pairs in the Frequently Asked Questions "
         "section (this overrides the template's two). Keep the \"Frequently Asked "
         "Questions\" heading verbatim; make each question incident-grade, not a "
         "restatement of a section."),
        ("- Give the summary callout and the closing callout (whichever appear) "
         "each an ORIGINAL short heading in your own voice for this piece — never "
         "a reused stock label like \"The Bottom Line\", \"Key Takeaways\", or "
         "\"TL;DR\". The \"Frequently Asked Questions\" and References headings are "
         "the ONLY fixed labels."),
    ]
    # Occasional stylistic devices — only mandated when their flag is on, so they
    # stay "time to time" rather than a per-post tic. (No line when off.)
    if plan.one_sentence_para:
        lines.append(
            "- Drop in at least one deliberate ONE-SENTENCE paragraph for punch, "
            "set off on its own."
        )
    if plan.rule_of_thumb:
        lines.append(
            "- Include exactly one <blockquote> framed as a blunt \"Rule of "
            "Thumb\" or a contrarian hot take — an opinion stated flatly, NOT a "
            "quotation."
        )
    return "\n".join(lines)
