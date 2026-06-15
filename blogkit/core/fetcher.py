"""Google News RSS fetcher (US English locale).

Returns top news entries for a given query, ranked by Google News. Used by
the Blogger pipeline (main_blogger.py) to seed each post's source data.
"""
from __future__ import annotations

import logging
import random
import time
from urllib.parse import quote_plus

import feedparser

logger = logging.getLogger(__name__)

# US market RSS endpoint — hl/gl/ceid pin Google News to US English signals
# so the model sees the audience-relevant headlines C-suite readers expect.
GOOGLE_NEWS_RSS_URL = (
    "https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"
)

DEFAULT_POOL_SIZE = 10   # top-N candidate pool from which we sample max_items


class FetchError(RuntimeError):
    """Raised when news fetching fails irrecoverably."""


def _entry_to_item(entry) -> dict:
    return {
        "title": (entry.get("title") or "").strip(),
        "link": entry.get("link") or "",
        "summary": (entry.get("summary") or "").strip(),
        "published": entry.get("published") or "",
        "source": (
            entry.get("source", {}).get("title", "")
            if isinstance(entry.get("source"), dict)
            else ""
        ),
    }


def fetch_top_news(
    queries: list[str],
    *,
    blog_name: str = "",
    max_items: int = 6,
    pool_size: int = DEFAULT_POOL_SIZE,
    retries: int = 2,
    retry_delay: float = 2.0,
) -> list[dict]:
    """Keyword Roulette + pool sampling — defeats Google News result bias.

    Behavior:
      1) Pick a single keyword via random.choice from `queries`.
      2) Hit the US Google News RSS endpoint (hl=en-US, gl=US, ceid=US:en).
      3) Take the top `pool_size` entries and randomly sample `max_items`.

    Args:
        queries: Keyword list (the rss_queries field from config.yaml).
        blog_name: Log prefix (e.g., "AI Infra Insider"). Optional.

    Returns:
        List of dicts with keys: title, link, summary, published, source.
    """
    if not queries:
        raise FetchError("rss_queries list is empty — need at least 1 keyword")

    chosen_keyword = random.choice(queries)
    prefix = f"[{blog_name}] " if blog_name else ""
    logger.info("%sSelected Roulette Keyword: %s", prefix, chosen_keyword)

    url = GOOGLE_NEWS_RSS_URL.format(query=quote_plus(chosen_keyword))
    logger.info("Fetching Google News RSS: %s", url)

    last_err: Exception | None = None
    for attempt in range(retries + 1):
        try:
            feed = feedparser.parse(url)
            if feed.bozo and not feed.entries:
                raise FetchError(
                    f"RSS parse failed: {getattr(feed, 'bozo_exception', 'unknown')}"
                )
            if not feed.entries:
                raise FetchError(f"No entries returned for query: {chosen_keyword!r}")

            # 1) Top pool_size entries as the candidate pool.
            pool = feed.entries[:pool_size]

            # 2) Sample max_items at random if the pool is larger; else use
            # the full pool.
            if len(pool) > max_items:
                selected = random.sample(pool, max_items)
                logger.info(
                    "Randomly sampled %d/%d items from top-%d pool "
                    "(de-dup safety for twice-daily runs)",
                    max_items, len(pool), pool_size,
                )
            else:
                selected = pool
                logger.info(
                    "Pool size %d <= requested %d — using all entries",
                    len(pool), max_items,
                )

            return [_entry_to_item(e) for e in selected]

        except Exception as e:
            last_err = e
            logger.warning(
                "Fetch attempt %d/%d failed: %s", attempt + 1, retries + 1, e
            )
            if attempt < retries:
                time.sleep(retry_delay)

    raise FetchError(f"All fetch attempts failed for {chosen_keyword!r}: {last_err}")
