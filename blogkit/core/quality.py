"""Pre-publish quality gate — thin / near-duplicate guard.

Google's "scaled content abuse" and "thin content" systems are the main threat
to AdSense approval and indexing for a multi-blog network. This gate refuses to
publish a post that is:

  * too thin  — under ``MIN_WORDS`` words of real body text, or
  * too similar — its content fingerprint overlaps a recently published post
    (network-wide) above ``MAX_BODY_SIMILARITY``.

Pure, dependency-free logic (token-set Jaccard over the body text), so it runs
before the costly image/publish steps and is fully unit-testable. The fingerprint
is a small, capped set of the post's most frequent significant words, persisted
in the dedup ledger so future posts can be compared against it cheaply.
"""

from __future__ import annotations

import html as _html
import re
from collections import Counter

MIN_WORDS = 1000            # minimum real body words to publish
MAX_BODY_SIMILARITY = 0.82  # Jaccard over content fingerprints that's "too similar"
FINGERPRINT_TOKENS = 50     # cap fingerprint size (keeps the ledger small)

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
    """Strip tags + unescape entities -> plain text."""
    return _html.unescape(_TAG_RE.sub(" ", html_body or "")).strip()


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
) -> tuple[bool, str]:
    """Return (ok, reason). ``ok=False`` means do NOT publish.

    Checks word count first (cheap), then near-duplication against recent
    fingerprints. The reason string is safe to log and to surface in the run
    summary.
    """
    wc = word_count(html_body)
    if wc < min_words:
        return False, f"thin content: {wc} words (< {min_words})"

    fp = content_fingerprint(html_body)
    sim = max_similarity(fp, recent_fingerprints or [])
    if sim >= max_similarity_threshold:
        return False, f"near-duplicate: {sim:.2f} similarity (>= {max_similarity_threshold})"

    return True, f"ok: {wc} words, max similarity {sim:.2f}"
