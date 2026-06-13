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
    TEXTURE_LAWS,
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
        assert "PROSE TEXTURE LAWS" in out


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


def test_craft_law_4_engineers_net_new_concepts():
    out = CRAFT_LAWS.lower()
    assert "original contribution" in out
    assert "coined term" in out or "named framework" in out


def test_texture_laws_break_the_llm_cadence():
    out = TEXTURE_LAWS.lower()
    assert "looping transitions" in out
    for tell in ("that said", "moreover", "make no mistake"):
        assert tell in out, tell
    # The "it's not just X, it's Y" antithesis tell is banned by name.
    assert "antithesis" in out
    # Mid-sentence bold guidance is present.
    assert "mid-sentence" in out or "inside a sentence" in out


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
    for attr in ("summary_callout", "pull_quote", "comparison_table",
                 "closing_callout", "data_visual", "one_sentence_para",
                 "rule_of_thumb"):
        vals = {getattr(p, attr) for p in plans}
        assert vals == {True, False}, attr


def test_plan_structure_varies_faq_and_summary_bullet_counts():
    # The two elements that otherwise stay byte-stable across a blog's posts must
    # now move within their bands (2-4 FAQ, 3-5 bullets) and actually rotate.
    plans = [plan_structure(f"topic-{i}") for i in range(200)]
    faq_vals = {p.faq_count for p in plans}
    bullet_vals = {p.summary_bullets for p in plans}
    assert faq_vals <= {2, 3, 4} and len(faq_vals) >= 2
    assert bullet_vals <= {3, 4, 5} and len(bullet_vals) >= 2


def test_render_structure_plan_varies_furniture_labels_and_faq_count():
    p = plan_structure("zero_trust")
    d = render_structure_plan(p)
    # FAQ count is stated and overrides the template's two.
    assert f"{p.faq_count} Q&A pairs" in d
    # Furniture labels are explicitly told to be original (kills the byte-stable
    # "The Bottom Line" / stock summary-box fingerprint).
    assert "ORIGINAL short heading" in d
    assert "The Bottom Line" in d  # named as a banned reuse


def test_data_visual_is_occasional():
    # The chart should be a treat, not on most posts — roughly a third.
    rate = sum(plan_structure(f"t-{i}").data_visual for i in range(400)) / 400
    assert 0.15 < rate < 0.45


def test_render_structure_plan_keeps_faq_and_references_fixed():
    on = StructurePlan(1600, 4, True, True, True, True, True, True, True)
    off = StructurePlan(1350, 3, False, False, False, False, False, False, False)
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
    assert "Include ONE data visual" in d_on
    assert "Do NOT include a chart" in d_off
    # Occasional devices: a line only when on, silent when off.
    assert "ONE-SENTENCE paragraph" in d_on
    assert "Rule of" in d_on
    assert "ONE-SENTENCE paragraph" not in d_off
    assert "Rule of" not in d_off


def test_ai_tell_hits_counts_the_measurable_tells():
    from blogkit.core.craft import AI_TELL_PHRASES, ai_tell_hits

    text = "Let's delve into this tapestry; it's important to note the paradigm shift."
    hits = ai_tell_hits(text)
    assert hits.get("delve") == 1
    assert hits.get("tapestry") == 1
    assert hits.get("it's important to note") == 1
    assert hits.get("paradigm shift") == 1
    assert ai_tell_hits("a clean operator sentence about OAuth token refresh") == {}
    # The list itself stays measurable substrings (no regex metachars needed).
    assert all(p == p.lower() for p in AI_TELL_PHRASES)


def test_negative_parallelism_is_counted():
    from blogkit.core.craft import negative_parallelism_count

    text = (
        "This is not just a latency problem, it's a capacity problem. "
        "The fix is not about tooling; this is governance. "
        "Success here is less about model choice and more about data hygiene."
    )
    assert negative_parallelism_count(text) == 3
    assert negative_parallelism_count("The retriever stalls under load.") == 0


def test_emdash_count_covers_literal_and_entities():
    from blogkit.core.craft import emdash_count

    assert emdash_count("a — b &mdash; c &#8212; d") == 3
    assert emdash_count("a - b -- c") == 0  # hyphens don't count


def test_texture_laws_ration_the_emdash():
    out = TEXTURE_LAWS.lower()
    assert "ration the em-dash" in out
    assert "negative parallelism" in out


def test_headline_style_rotates_and_renders():
    from blogkit.core.craft import HEADLINE_STYLES

    keys = {k for k, _ in HEADLINE_STYLES}
    assert keys == {"flat_claim", "question", "number", "how", "tension"}
    plans = [plan_structure(f"topic-{i}") for i in range(200)]
    assert {p.headline_style for p in plans} == keys  # all shapes reached
    # Only the tension shape may permit a colon; the rest forbid it.
    for k, directive in HEADLINE_STYLES:
        if k == "tension":
            assert "colon is allowed" in directive
        else:
            assert "NO colon" in directive
    d = render_structure_plan(plan_structure("zero_trust"))
    assert "HEADLINE SHAPE:" in d


def test_reader_question_and_evergreen_are_occasional():
    plans = [plan_structure(f"topic-{i}") for i in range(400)]
    rq = sum(p.reader_question for p in plans) / len(plans)
    ev = sum(p.evergreen_lean for p in plans) / len(plans)
    assert 0.15 < rq < 0.45
    assert 0.25 < ev < 0.55
    # Rendered only when on.
    p_on = next(p for p in plans if p.reader_question and p.evergreen_lean)
    p_off = next(p for p in plans if not p.reader_question and not p.evergreen_lean)
    d_on, d_off = render_structure_plan(p_on), render_structure_plan(p_off)
    assert "ONE pointed, specific question" in d_on
    assert "12 MONTHS FROM NOW" in d_on
    assert "ONE pointed, specific question" not in d_off
    assert "12 MONTHS FROM NOW" not in d_off
