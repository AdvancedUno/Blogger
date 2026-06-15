"""Pre-publish quality gate — thin / near-duplicate guard.

Google's "scaled content abuse" and "thin content" systems are the main threat
to AdSense approval and indexing for a multi-blog network. This gate refuses to
publish a post that is:

  * too thin  — under ``MIN_WORDS`` words of real body text, or
  * too similar — its content fingerprint overlaps a recently published post
    (network-wide) above ``MAX_BODY_SIMILARITY``, or
  * buzzword-stuffed — overuses the banned corporate filler from core/craft.py
    above ``MAX_BUZZWORD_HITS`` (a backstop behind the prompt-level ban), or
  * sensationalist — uses banned absolute proclamations from core/craft.py
    above ``MAX_ABSOLUTE_HITS`` (a backstop behind the Nuance Tax), or
  * machine-fingerprinted — overuses AI-tell phrases (``MAX_AI_TELL_HITS``),
    "it's not X, it's Y" negative parallelism (``MAX_NEG_PARALLELISM``), or
    em-dashes (density backstop behind the Texture Laws' ration).

Pure, dependency-free logic (token-set Jaccard over the body text), so it runs
before the costly image/publish steps and is fully unit-testable. The fingerprint
is a small, capped set of the post's most frequent significant words, persisted
in the dedup ledger so future posts can be compared against it cheaply.
"""

from __future__ import annotations

import html as _html
import re
from collections import Counter

from blogkit.core.charts import strip_chart_blocks
from blogkit.core.craft import (
    absolute_hits,
    ai_tell_hits,
    buzzword_hits,
    emdash_count,
    negative_parallelism_count,
)

MIN_WORDS = 1000            # minimum real body words to publish
MAX_BODY_SIMILARITY = 0.82  # Jaccard over content fingerprints that's "too similar"
FINGERPRINT_TOKENS = 50     # cap fingerprint size (keeps the ledger small)
# Buzzword backstop: the prompt forbids the banned phrases (core/craft.py), so a
# compliant post has zero. We tolerate the odd incidental slip and only reject on
# clear overuse, so this never silently kills an otherwise-good daily run.
MAX_BUZZWORD_HITS = 3       # total banned-buzzword occurrences allowed before reject
# Absolute-proclamation backstop behind the Nuance Tax. These sensational
# phrases are far rarer than buzzwords, so the tolerance is tighter — one slip
# passes, a pattern of them does not.
MAX_ABSOLUTE_HITS = 1       # total banned-absolute occurrences allowed before reject
# AI-tell backstop behind the prompt's _ANTI_AI ban (core/craft.AI_TELL_PHRASES).
# A compliant post has zero; tolerate a couple of incidental slips.
MAX_AI_TELL_HITS = 2        # total AI-tell phrase occurrences allowed before reject
# Negative parallelism ("it's not X, it's Y") — one can be natural prose; a
# pattern of them is the fingerprint.
MAX_NEG_PARALLELISM = 2     # constructions allowed before reject
# Em-dash density backstop (prompt asks for <= 2-3 per piece). Reject only
# clear statistical overuse: more than 1 em-dash per EMDASH_WORDS_PER words
# AND more than EMDASH_FLOOR total, so legit punctuation never trips it.
EMDASH_WORDS_PER = 120      # density threshold: 1 em-dash per this many words
EMDASH_FLOOR = 8            # never reject below this absolute count

_TAG_RE = re.compile(r"<[^>]+>")
_WORD_RE = re.compile(r"[a-z0-9]+")

# Compact English stopword set — enough to keep the fingerprint on real content.
_STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "if", "then", "else", "of", "to", "in",
    "on", "for", "with", "as", "by", "at", "from", "into", "about", "over",
    "after", "before", "is", "are", "was", "were", "be", "been", "being", "it",
    "its", "this", "that", "these", "those", "they", "them", "their", "there",
    "here", "you", "your", "we", "our", "us", "i", "he", "she", "his", "her",
    "not", "no", "do", "does", "did", "has", "have", "had", "will", "would",
    "can", "could", "should", "may", "might", "must", "than", "so", "such",
    "more", "most", "much", "many", "some", "any", "all", "each", "every",
    "what", "which", "who", "whom", "how", "when", "where", "why", "also",
    "just", "only", "very", "too", "up", "out", "off", "down", "one", "two",
    "new", "now", "get", "got", "make", "made", "use", "used", "like", "via",
}


def extract_text(html_body: str) -> str:
    """Strip rendered charts + tags + unescape entities -> plain prose text.

    Chart blocks are removed first so SVG labels / captions / stat numbers never
    inflate the word count (a thin-content guard) or pollute the dedup
    fingerprint.
    """
    return _html.unescape(_TAG_RE.sub(" ", strip_chart_blocks(html_body or ""))).strip()


def word_count(html_body: str) -> int:
    return len(extract_text(html_body).split())


def content_fingerprint(html_body: str, cap: int = FINGERPRINT_TOKENS) -> list[str]:
    """A small, stable fingerprint: the most frequent significant words.

    Deterministic (ties broken alphabetically) so the same body always yields
    the same fingerprint, and capped so it stays cheap to store and compare.
    """
    words = [w for w in _WORD_RE.findall(extract_text(html_body).lower())
             if len(w) > 3 and w not in _STOPWORDS]
    if not words:
        return []
    counts = Counter(words)
    # Most frequent first; alphabetical tiebreak for determinism.
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return sorted(w for w, _ in ranked[:cap])


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def max_similarity(fp: list[str], others: list[list[str]]) -> float:
    """Highest Jaccard overlap between ``fp`` and any prior fingerprint."""
    s = set(fp)
    return max((jaccard(s, set(o)) for o in others if o), default=0.0)


def check_quality(
    html_body: str,
    recent_fingerprints: list[list[str]] | None = None,
    *,
    min_words: int = MIN_WORDS,
    max_similarity_threshold: float = MAX_BODY_SIMILARITY,
    max_buzzword_hits: int = MAX_BUZZWORD_HITS,
    max_absolute_hits: int = MAX_ABSOLUTE_HITS,
) -> tuple[bool, str]:
    """Return (ok, reason). ``ok=False`` means do NOT publish.

    Checks word count first (cheap), then near-duplication against recent
    fingerprints, then backstops for overused banned buzzwords and sensational
    absolute proclamations. The reason string is safe to log and to surface in
    the run summary.
    """
    wc = word_count(html_body)
    if wc < min_words:
        return False, f"thin content: {wc} words (< {min_words})"

    fp = content_fingerprint(html_body)
    sim = max_similarity(fp, recent_fingerprints or [])
    if sim >= max_similarity_threshold:
        return False, f"near-duplicate: {sim:.2f} similarity (>= {max_similarity_threshold})"

    text = extract_text(html_body)

    hits = buzzword_hits(text)
    total_hits = sum(hits.values())
    if total_hits > max_buzzword_hits:
        worst = ", ".join(f"{p!r}x{n}" for p, n in sorted(hits.items(), key=lambda kv: -kv[1]))
        return False, f"buzzword overuse: {total_hits} hits (> {max_buzzword_hits}) — {worst}"

    abs_hits = absolute_hits(text)
    total_abs = sum(abs_hits.values())
    if total_abs > max_absolute_hits:
        worst = ", ".join(f"{p!r}x{n}" for p, n in sorted(abs_hits.items(), key=lambda kv: -kv[1]))
        return False, f"absolute proclamations: {total_abs} hits (> {max_absolute_hits}) — {worst}"

    tells = ai_tell_hits(text)
    total_tells = sum(tells.values())
    if total_tells > MAX_AI_TELL_HITS:
        worst = ", ".join(f"{p!r}x{n}" for p, n in sorted(tells.items(), key=lambda kv: -kv[1]))
        return False, f"AI-tell phrases: {total_tells} hits (> {MAX_AI_TELL_HITS}) — {worst}"

    neg = negative_parallelism_count(text)
    if neg > MAX_NEG_PARALLELISM:
        return False, (
            f"negative parallelism: {neg} 'not X, but Y' constructions "
            f"(> {MAX_NEG_PARALLELISM})"
        )

    # Em-dash density is checked on the raw HTML (entities included).
    dashes = emdash_count(html_body)
    if dashes > EMDASH_FLOOR and dashes * EMDASH_WORDS_PER > wc:
        return False, (
            f"em-dash overuse: {dashes} in {wc} words "
            f"(> 1 per {EMDASH_WORDS_PER} words)"
        )

    return True, f"ok: {wc} words, max similarity {sim:.2f}"
