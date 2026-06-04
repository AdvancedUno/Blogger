"""Network-wide craft laws: prompt block + banned-buzzword backstop."""

from __future__ import annotations

from blogkit.core.archetypes import ARCHETYPES, build_archetype_directive
from blogkit.core.craft import BANNED_BUZZWORDS, CRAFT_LAWS, buzzword_hits
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
    assert "NON-NEGOTIABLE CRAFT LAWS" in p
    assert "NON-NEGOTIABLE CRAFT LAWS" in a


def test_buzzword_hits_counts_case_insensitively():
    text = "Our Smart Capital play needs institutional-grade software, smart capital again."
    hits = buzzword_hits(text)
    assert hits.get("smart capital") == 2
    assert hits.get("institutional-grade software") == 1
    assert buzzword_hits("a clean operational sentence") == {}
