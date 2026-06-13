"""Pre-publish quality gate: thin + near-duplicate detection."""

from __future__ import annotations

from blogkit.core.quality import (
    MAX_ABSOLUTE_HITS,
    MAX_BUZZWORD_HITS,
    MIN_WORDS,
    check_quality,
    content_fingerprint,
    jaccard,
    word_count,
)


def _post(words: int, vocab: int = 120) -> str:
    return "<h2>Title</h2>\n<p>" + " ".join(f"topic{i % vocab}" for i in range(words)) + "</p>"


def test_word_count_strips_tags():
    assert word_count("<p>one two three</p><h2>four</h2>") == 4


def test_thin_post_is_rejected():
    ok, why = check_quality(_post(300))
    assert not ok and "thin" in why


def test_long_post_passes_when_no_priors():
    ok, why = check_quality(_post(MIN_WORDS + 200))
    assert ok and "ok" in why


def test_fingerprint_is_deterministic_and_capped():
    body = _post(1200)
    fp1 = content_fingerprint(body)
    fp2 = content_fingerprint(body)
    assert fp1 == fp2
    assert len(fp1) <= 50
    assert fp1 == sorted(fp1)


def test_near_duplicate_is_rejected():
    body = _post(1200)
    prior = content_fingerprint(body)
    ok, why = check_quality(body, [prior])   # identical body -> ~1.0 similarity
    assert not ok and "near-duplicate" in why


def test_distinct_post_passes_against_priors():
    prior = content_fingerprint(_post(1200, vocab=120))
    other = "<h2>X</h2>\n<p>" + " ".join(f"unrelated{i % 120}" for i in range(1200)) + "</p>"
    ok, why = check_quality(other, [prior])
    assert ok, why


def test_buzzword_overuse_is_rejected():
    body = _post(MIN_WORDS + 200) + "<p>" + ("smart capital " * (MAX_BUZZWORD_HITS + 1)) + "</p>"
    ok, why = check_quality(body)
    assert not ok and "buzzword" in why


def test_one_incidental_buzzword_still_passes():
    body = _post(MIN_WORDS + 200) + "<p>a single smart capital mention</p>"
    ok, why = check_quality(body)
    assert ok, why


def test_absolute_proclamation_overuse_is_rejected():
    body = _post(MIN_WORDS + 200) + "<p>" + ("the death of x " * (MAX_ABSOLUTE_HITS + 1)) + "</p>"
    ok, why = check_quality(body)
    assert not ok and "absolute" in why


def test_one_incidental_absolute_still_passes():
    body = _post(MIN_WORDS + 200) + "<p>some say this is the death of the old way</p>"
    ok, why = check_quality(body)
    assert ok, why


def test_jaccard_basics():
    assert jaccard(set(), {"a"}) == 0.0
    assert jaccard({"a", "b"}, {"a", "b"}) == 1.0
    assert jaccard({"a", "b"}, {"b", "c"}) == 1 / 3


def test_ai_tell_overuse_is_rejected():
    base = _post(MIN_WORDS + 200)
    spiked = base + "<p>" + "Let's delve into the tapestry of this paradigm shift. " * 2 + "</p>"
    ok, why = check_quality(spiked)
    assert not ok and "AI-tell" in why


def test_a_couple_of_tells_pass():
    base = _post(MIN_WORDS + 200)
    ok, _ = check_quality(base + "<p>We delve into one corner of the system.</p>")
    assert ok


def test_negative_parallelism_overuse_is_rejected():
    base = _post(MIN_WORDS + 200)
    spiked = base + "<p>" + "It is not just speed, it's trust. " * 4 + "</p>"
    ok, why = check_quality(spiked)
    assert not ok and "parallelism" in why


def test_emdash_overuse_is_rejected_but_normal_use_passes():
    words = MIN_WORDS + 200
    base = _post(words)
    heavy = base + "<p>" + ("x — y. " * (words // 60)) + "</p>"
    ok, why = check_quality(heavy)
    assert not ok and "em-dash" in why
    light = base + "<p>one — two — three.</p>"
    ok, _ = check_quality(light)
    assert ok
