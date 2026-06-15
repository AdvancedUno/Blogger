"""Best-effort full-text grounding for fetched news items.

Google News RSS gives the model almost nothing to work with: each entry's
description is a link stub, so generation ends up grounded in headlines alone.
That headline-only diet is the root cause of generic prose and hallucination
pressure — "ground every claim in the Source Data" can't work when the Source
Data is twelve words per item.

This module upgrades each news item, best-effort:

  1. resolve the news.google.com redirect link to the real publisher URL
     (old-style tokens embed the URL base64-encoded; new-style tokens are
     resolved via the batchexecute endpoint Google's own web app uses),
  2. fetch the publisher page (short timeout, browser UA),
  3. extract the main article paragraphs dependency-free (no readability lib),
  4. write the first ~1,100 chars of real article text into item["summary"]
     and keep the resolved URL in item["source_url"].

item["link"] is NEVER touched — the dedup ledger hashes the original RSS link,
so rewriting it would break the network-wide duplicate guard.

EVERY step is wrapped: a paywall, consent wall, timeout, or Google changing
its URL format just leaves that item exactly as fetched. No new dependencies.
"""

from __future__ import annotations

import base64
import html as _html
import json
import logging
import re
import time

import requests

logger = logging.getLogger(__name__)

FETCH_TIMEOUT = 8           # seconds per HTTP call
MAX_SUMMARY_CHARS = 1100    # cap on extracted text per item (prompt budget)
MIN_USEFUL_CHARS = 280      # below this, extraction is judged a failure
MAX_ITEMS_ENRICHED = 5      # bound the per-post runtime
TOTAL_TIME_BUDGET = 45.0    # seconds across all items in one post

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

_GNEWS_TOKEN_RE = re.compile(r"news\.google\.com/(?:rss/)?articles/([^?/&#]+)")
_URL_IN_BYTES_RE = re.compile(rb"https?://[A-Za-z0-9\-._~:/?#\[\]@!$&'()*+,;=%]+")
_BOILERPLATE_TAGS_RE = re.compile(
    r"(?is)<(script|style|noscript|svg|nav|header|footer|form|aside|figure)[^>]*>.*?</\1>"
)
_P_RE = re.compile(r"(?is)<p[^>]*>(.*?)</p>")
_TAG_RE = re.compile(r"<[^>]+>")


def decode_gnews_url(url: str) -> str:
    """Decode an old-style Google News article token into the publisher URL.

    Old tokens ("CBMi...") are base64 with the article URL embedded as a
    length-prefixed string. Returns "" when the token is new-style or invalid.
    """
    m = _GNEWS_TOKEN_RE.search(url or "")
    if not m:
        return ""
    token = m.group(1)
    try:
        raw = base64.urlsafe_b64decode(token + "=" * (-len(token) % 4))
    except Exception:
        return ""
    for hit in _URL_IN_BYTES_RE.finditer(raw):
        candidate = hit.group(0).decode("utf-8", "replace")
        if "news.google.com" not in candidate:
            return candidate
    return ""


def _resolve_via_api(token: str) -> str:
    """Resolve a new-style token via the endpoint the Google News web app uses.

    Best-effort by design — Google can change this at any time, in which case
    we silently fall back to headline-only behaviour.
    """
    art = requests.get(
        f"https://news.google.com/rss/articles/{token}",
        headers=_HEADERS, timeout=FETCH_TIMEOUT,
    )
    art.raise_for_status()
    m_ts = re.search(r'data-n-a-ts="([^"]+)"', art.text)
    m_sg = re.search(r'data-n-a-sg="([^"]+)"', art.text)
    if not (m_ts and m_sg):
        return ""
    ts = int(float(m_ts.group(1)))
    inner = json.dumps([
        "garturlreq",
        [["X", "X", ["X", "X"], None, None, 1, 1, "US:en", None, 1,
          None, None, None, None, None, 0, 1],
         "X", "X", 1, [1, 1, 1], 1, 1, None, 0, 0, None, 0],
        token, ts, m_sg.group(1),
    ])
    resp = requests.post(
        "https://news.google.com/_/DotsSplashUi/data/batchexecute",
        headers={**_HEADERS,
                 "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"},
        data={"f.req": json.dumps([[["Fbv4je", inner, None, "generic"]]])},
        timeout=FETCH_TIMEOUT,
    )
    resp.raise_for_status()
    # The publisher URL is a JSON string nested inside the batchexecute JSON, so
    # its slashes arrive escaped ("https:\/\/host\/path"). Unescape them first or
    # the '//'-anchored pattern below never matches and new-style tokens silently
    # fall back to headline-only grounding.
    text = resp.text.replace("\\/", "/")
    for m in re.finditer(r'https?://[^"\\\s]+', text):
        u = m.group(0)
        if "google.com" not in u and "gstatic.com" not in u:
            return u
    return ""


def resolve_publisher_url(link: str) -> str:
    """The real publisher URL behind a (possibly Google News) link, or ""."""
    if not (link or "").startswith("http"):
        return ""
    if "news.google.com" not in link:
        return link
    decoded = decode_gnews_url(link)
    if decoded:
        return decoded
    m = _GNEWS_TOKEN_RE.search(link)
    if m:
        try:
            resolved = _resolve_via_api(m.group(1))
            if resolved:
                return resolved
        except Exception:
            pass
    # Last resort: plain redirect-following (works for legacy ./rss/rd links).
    try:
        r = requests.get(link, headers=_HEADERS, timeout=FETCH_TIMEOUT,
                         allow_redirects=True)
        if "news.google.com" not in r.url:
            return r.url
    except Exception:
        pass
    return ""


def extract_article_text(page_html: str, cap: int = MAX_SUMMARY_CHARS) -> str:
    """Pull the main article paragraphs out of a publisher page.

    Dependency-free heuristic: drop scripts/nav/boilerplate containers, keep
    <p> blocks long enough (>= 80 chars) to be body prose, join and cap.
    """
    cleaned = _BOILERPLATE_TAGS_RE.sub(" ", page_html or "")
    paras: list[str] = []
    for p in _P_RE.findall(cleaned):
        t = _html.unescape(_TAG_RE.sub(" ", p))
        t = re.sub(r"\s+", " ", t).strip()
        if len(t) >= 80:
            paras.append(t)
        if sum(len(x) for x in paras) >= cap * 2:
            break
    joined = " ".join(paras)
    return joined[:cap].rsplit(" ", 1)[0] if len(joined) > cap else joined


def enrich_news(items: list[dict]) -> int:
    """Upgrade items' summaries with real article text, in place. Best-effort.

    Returns the number of items that received full text. Stops early when the
    time budget or the per-post item cap is exhausted.
    """
    enriched = 0
    started = time.monotonic()
    for item in items:
        if enriched >= MAX_ITEMS_ENRICHED:
            break
        if time.monotonic() - started > TOTAL_TIME_BUDGET:
            logger.info("Source-text budget exhausted after %d enrichments", enriched)
            break
        link = item.get("link") or ""
        try:
            # Reuse a publisher URL the caller already resolved (the pipeline
            # resolves it up front for cross-blog dedup), else resolve it now.
            pub_url = item.get("source_url") or resolve_publisher_url(link)
            if not pub_url:
                continue
            page = requests.get(pub_url, headers=_HEADERS, timeout=FETCH_TIMEOUT)
            page.raise_for_status()
            text = extract_article_text(page.text)
            if len(text) >= MIN_USEFUL_CHARS:
                item["summary"] = text
                item["source_url"] = pub_url
                enriched += 1
        except Exception as e:
            logger.debug("Source-text enrichment skipped for %s (%s)", link, e)
    return enriched
