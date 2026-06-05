"""Network-wide craft laws: prompt block + banned-buzzword backstop."""

from __future__ import annotations

from blogkit.core.archetypes import ARCHETYPES, build_archetype_directive
from blogkit.core.craft import (
    ABSOLUTE_PROCLAMATIONS,
    BANNED_BUZZWORDS,
    CRAFT_LAWS,
    NARRATIVE_LAWS,
    NARRATIVE_MODES,
    PRACTITIONER_LAWS,
    StructurePlan,
    absolute_hits,
    buzzword_hits,
    pick_narrative_mode,
    plan_structure,
    render_structure_plan,
)
from blogkit.core.personas import PERSONAS, build_persona_directive


def test_craft_laws_cover_all_six_rules():
    out = CRAFT_LAWS.lower()
    # Each law's defining instruction is present.
    for marker in ("strip the ai scaffolding", "buzzword tax", "name real vendors",
                   "information gain", "case vignettes", "self-correct"):
        assert marker in out, marker


def test_craft_laws_ban_the_named_cliches_and_buzzwords():
    out = CRAFT_LAWS.lower()
    for cliche in ("the setup", "the stakes", "the watch", "myth 1", "risks & bottlenecks"):
        assert cliche in out, cliche  # named in the ban
    for phrase in BANNED_BUZZWORDS:
        assert phrase.lower() in out, phrase


def test_craft_laws_keep_the_faq_carveout():
    # Law 1 must NOT order the model to rename the FAQ heading (it powers schema).
    assert "Frequently Asked Questions" in CRAFT_LAWS


def test_persona_and_archetype_directives_inject_the_laws():
    p = build_persona_directive(PERSONAS["matt_levine"])
    a = build_archetype_directive(ARCHETYPES["the_engineer"])
    for out in (p, a):
        assert "NON-NEGOTIABLE CRAFT LAWS" in out
        assert "PRACTITIONER LAWS" in out
        assert "NARRATIVE LAWS" in out


def test_practitioner_laws_cover_all_five_rules():
    out = PRACTITIONER_LAWS.lower()
    for marker in ("engineering & financial granularity", "messy case numbers",
                   "one analogy maximum", "operator's caveat", "incident-grade faq"):
        assert marker in out, marker
    # The hard engineering vocabulary the user asked for.
    for term in ("p95", "recall@k", "qps", "cache hit", "audit trail", "sox controls"):
        assert term in out, term


def test_practitioner_laws_cap_analogies_and_ban_vague_arch():
    out = PRACTITIONER_LAWS.lower()
    assert "single analogy" in out or "one analogy" in out
    assert "infrastructure orchestration" in out
    assert "intelligent context routers" in out


def test_buzzword_hits_counts_case_insensitively():
    text = "Our Smart Capital play needs institutional-grade software, smart capital again."
    hits = buzzword_hits(text)
    assert hits.get("smart capital") == 2
    assert hits.get("institutional-grade software") == 1
    assert buzzword_hits("a clean operational sentence") == {}


def test_executive_coinages_are_banned_buzzwords():
    # Narrative Law 3 / Buzzword Tax: high-altitude coinages join the ban list.
    for phrase in ("structural margin crisis", "tollbooth architecture"):
        assert phrase in BANNED_BUZZWORDS
        assert phrase in CRAFT_LAWS.lower()  # surfaced inline in Law 2


def test_narrative_laws_cover_nuance_metrics_and_jargon():
    out = NARRATIVE_LAWS.lower()
    assert "nuance tax" in out
    # Every banned absolute is named in the ban.
    for phrase in ABSOLUTE_PROCLAMATIONS:
        assert phrase in out, phrase
    # Metric-grounding and operator-jargon rules are present.
    assert "illustrative" in out
    for term in ("oauth", "consent-expiration", "endpoint variance"):
        assert term in out, term


def test_thesis_break_section_is_required_on_every_post():
    # Narrative-Diversity Law 3: the counterargument section is now unconditional.
    out = PRACTITIONER_LAWS.lower()
    assert "every post" in out
    assert "argues against your own thesis" in out


def test_absolute_hits_counts_case_insensitively():
    text = "This is The Death Of screen scraping, and the vendor always wins, always wins."
    hits = absolute_hits(text)
    assert hits.get("the death of") == 1
    assert hits.get("always wins") == 2
    assert absolute_hits("a measured, constraint-bounded claim") == {}


def test_narrative_modes_are_three_distinct_structures():
    keys = [k for k, _ in NARRATIVE_MODES]
    assert keys == ["operational_tradeoff", "autopsy", "practical_evolution"]
    for _key, directive in NARRATIVE_MODES:
        assert "STRUCTURE THIS PIECE" in directive


def test_pick_narrative_mode_is_deterministic_and_rotates():
    directives = {d for _, d in NARRATIVE_MODES}
    # Always returns one of the real mode directives.
    assert pick_narrative_mode("anything") in directives
    # Stable for the same seed (survives retries).
    assert pick_narrative_mode("zero_trust") == pick_narrative_mode("zero_trust")
    # Across many seeds the rotation actually reaches all three arcs.
    seen = {pick_narrative_mode(f"topic-{i}") for i in range(60)}
    assert seen == directives


def test_craft_law_4_mandates_cross_source_synthesis():
    out = CRAFT_LAWS.lower()
    assert "synthesis" in out
    assert "proprietary data" in out  # forward-compatible seam


def test_vignette_laws_are_framed_illustrative():
    # Q3 decision: textured but clearly illustrative, never asserted as measured.
    assert "illustrative" in CRAFT_LAWS.lower()
    assert "illustrative" in PRACTITIONER_LAWS.lower()


def test_plan_structure_is_deterministic():
    assert plan_structure("zero_trust") == plan_structure("zero_trust")


def test_plan_structure_length_never_below_gate_floor():
    # A plan must never target a thin-content rejection (quality MIN_WORDS=1000).
    for i in range(200):
        assert plan_structure(f"topic-{i}").target_words >= 1000


def test_plan_structure_varies_shape_across_topics():
    plans = [plan_structure(f"topic-{i}") for i in range(200)]
    # Length and section count both vary.
    assert len({p.target_words for p in plans}) >= 3
    assert {p.sections for p in plans} <= {3, 4, 5, 6}
    assert len({p.sections for p in plans}) >= 3
    # Each optional element is sometimes on and sometimes off (truly probabilistic).
    for attr in ("summary_callout", "pull_quote", "comparison_table", "closing_callout"):
        vals = {getattr(p, attr) for p in plans}
        assert vals == {True, False}, attr


def test_render_structure_plan_keeps_faq_and_references_fixed():
    on = StructurePlan(1600, 4, True, True, True, True)
    off = StructurePlan(1350, 3, False, False, False, False)
    d_on, d_off = render_structure_plan(on), render_structure_plan(off)
    for d in (d_on, d_off):
        # FAQ + References are explicitly always kept, never dropped.
        assert "Frequently Asked Questions" in d
        assert "References" in d
        assert "1600" in d_on and "1350" in d_off
    # Booleans flip the directive language.
    assert "Open with a <blockquote> summary" in d_on
    assert "Do NOT open with a summary callout" in d_off
    assert "Do NOT use a comparison <table>" in d_off
