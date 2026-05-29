"""Google News RSS fetcher (한국어).

Returns top news entries for a given query, ranked by Google News.
"""
from __future__ import annotations

import logging
import random
import time
from urllib.parse import quote_plus

import feedparser

logger = logging.getLogger(__name__)

GOOGLE_NEWS_RSS = (
    "https://news.google.com/rss/search?q={query}&hl=ko&gl=KR&ceid=KR:ko"
)

DEFAULT_POOL_SIZE = 10   # 상위 N 개 풀에서 max_items 만큼 랜덤 샘플링


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
    query: str,
    max_items: int = 6,
    pool_size: int = DEFAULT_POOL_SIZE,
    retries: int = 2,
    retry_delay: float = 2.0,
) -> list[dict]:
    """Fetch Google News items for `query` and randomly sample `max_items`
    from the top `pool_size` recent entries.

    하루 2회(아침/저녁) 실행 시 동일 1순위 기사 중복 작성을 방지하기 위해,
    상위 `pool_size` 개 안에서 `max_items` 개를 무작위 추출한다.
    각 실행은 독립적인 random seed 를 쓰므로 회차마다 다른 조합이 나온다.

    Returns: list of dicts with keys title/link/summary/published/source.
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

            # 1) 최신 상위 pool_size 개를 후보 풀로 확보
            pool = feed.entries[:pool_size]

            # 2) 풀 크기가 요청 개수보다 많으면 무작위 샘플링, 아니면 그대로 사용
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
                    "Pool size %d ≤ requested %d — using all entries",
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

    raise FetchError(f"All fetch attempts failed for {query!r}: {last_err}")
