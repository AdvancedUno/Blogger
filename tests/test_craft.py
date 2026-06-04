"""Network-wide craft laws: prompt block + banned-buzzword backstop."""

from __future__ import annotations

from blogkit.core.archetypes import ARCHETYPES, build_archetype_directive
from blogkit.core.craft import (
    BANNED_BUZZWORDS,
    CRAFT_LAWS,
    PRACTITIONER_LAWS,
    buzzword_hits,
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
