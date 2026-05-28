"""Google News RSS fetcher (한국어).

Returns top news entries for a given query, ranked by Google News.
"""
from __future__ import annotations

import logging
import time
from urllib.parse import quote_plus

import feedparser

logger = logging.getLogger(__name__)

GOOGLE_NEWS_RSS = (
    "https://news.google.com/rss/search?q={query}&hl=ko&gl=KR&ceid=KR:ko"
)


class FetchError(RuntimeError):
    """Raised when news fetching fails irrecoverably."""


def fetch_top_news(
    query: str,
    max_items: int = 6,
    retries: int = 2,
    retry_delay: float = 2.0,
) -> list[dict]:
    """Fetch top Google News items for `query`.

    Each returned dict has: title, link, summary, published, source.
    """
    url = GOOGLE_NEWS_RSS.format(query=quote_plus(query))
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
                raise FetchError(f"No entries returned for query: {query!r}")

            items: list[dict] = []
            for entry in feed.entries[:max_items]:
                items.append(
                    {
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
                )
            return items
        except Exception as e:
            last_err = e
            logger.warning(
                "Fetch attempt %d/%d failed: %s", attempt + 1, retries + 1, e
            )
            if attempt < retries:
                time.sleep(retry_delay)

    raise FetchError(f"All fetch attempts failed for {query!r}: {last_err}")
