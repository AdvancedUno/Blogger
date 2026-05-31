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

# Google News RSS URL 은 language 에 따라 다른 hl/gl/ceid 사용.
# - ko : 한국 시장 뉴스 (Tistory)
# - en : 미국 시장 뉴스 (Blogger — US-centric C-suite 타깃)
GOOGLE_NEWS_RSS_BY_LANG = {
    "ko": "https://news.google.com/rss/search?q={query}&hl=ko&gl=KR&ceid=KR:ko",
    "en": "https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en",
}

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
    queries: list[str],
    *,
    language: str = "ko",
    blog_name: str = "",
    max_items: int = 6,
    pool_size: int = DEFAULT_POOL_SIZE,
    retries: int = 2,
    retry_delay: float = 2.0,
) -> list[dict]:
    """Keyword Roulette + 풀 샘플링 — Google News 결과 편향 회피.

    동작:
      1) `queries` 리스트에서 random.choice 로 **단 하나의 키워드** 선택.
      2) language 에 따른 locale 의 Google News RSS 호출
         (ko → hl=ko&gl=KR&ceid=KR:ko, en → hl=en-US&gl=US&ceid=US:en).
      3) 상위 `pool_size` 결과에서 `max_items` 개를 무작위 샘플.

    Args:
        queries: 키워드 리스트 (config 의 rss_queries 필드).
        language: "ko" (default, 한국 뉴스) 또는 "en" (US 뉴스).
        blog_name: 로그 prefix 용 (e.g., "Tech Blog"). 선택.

    Returns: list of dicts with keys title/link/summary/published/source.
    """
    if not queries:
        raise FetchError("rss_queries 리스트가 비어 있음 — 최소 1개 키워드 필요")

    chosen_keyword = random.choice(queries)
    prefix = f"[{blog_name}] " if blog_name else ""
    logger.info("%sSelected Roulette Keyword: %s (lang=%s)",
                prefix, chosen_keyword, language)

    rss_template = GOOGLE_NEWS_RSS_BY_LANG.get(
        language, GOOGLE_NEWS_RSS_BY_LANG["ko"]
    )
    url = rss_template.format(query=quote_plus(chosen_keyword))
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

    raise FetchError(f"All fetch attempts failed for {chosen_keyword!r}: {last_err}")
