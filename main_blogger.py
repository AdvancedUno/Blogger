"""Daily Blogger pipeline entrypoint — Tistory pipeline 과 완전 분리.

config.yaml 의 `blogger_sites` 섹션만 읽어서 영어 글을 생성하고 Blogger v3
REST API 로 발행한다. Playwright/storage_state 의존 없음.
"""
from __future__ import annotations

import argparse
import logging
import os
import random
import sys
import time
import traceback
from pathlib import Path

import yaml

# Gemini free-tier RPM 회피용 사이트 간 sleep (초)
INTER_SITE_SLEEP_SECONDS = 15

from src.fetcher import FetchError, fetch_top_news
from src.generator import GenerationError, generate_post
from src.blogger_publisher import BloggerPublishError, publish_to_blogger

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("daily_blogger")

CONFIG_PATH = Path(__file__).parent / "config.yaml"


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"Missing config file: {CONFIG_PATH}")
    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def run_one(site: dict, defaults: dict) -> tuple[bool, str]:
    name = site.get("name", "<unnamed>")
    logger.info("================ START : %s ================", name)

    # ----- 1. Fetch (Keyword Fallback Loop) ---------------------------
    # B2B 마이크로 니치 키워드는 그날 뉴스가 0건일 확률이 높아, random.choice
    # 하나로는 자주 실패함. 그래서 rss_queries 를 셔플하고 순서대로 시도하면서
    # 첫 번째 뉴스가 잡히는 키워드에서 break. 전부 0건이면 그 사이트만 skip.
    try:
        queries = list(site["rss_queries"])
    except KeyError as e:
        logger.error("[%s] Fetcher failed: missing rss_queries: %s", name, e)
        return False, f"fetcher: {e}"

    if not queries:
        logger.error("[%s] rss_queries 가 비어 있음", name)
        return False, "fetcher: empty rss_queries"

    random.shuffle(queries)
    max_items = int(site.get("max_news_items", defaults.get("max_news_items", 6)))
    news: list[dict] = []
    chosen_keyword = ""

    for kw in queries:
        logger.info("[%s] Trying keyword: %r", name, kw)
        try:
            news = fetch_top_news(
                queries=[kw],         # 단일 키워드로 호출 → fallback 다음 키워드 시도
                language="en",        # US locale (hl=en-US, gl=US, ceid=US:en)
                blog_name=name,
                max_items=max_items,
                retries=0,            # 빠른 fail → 다음 키워드로 즉시 넘어감
            )
            if news:
                chosen_keyword = kw
                break
        except FetchError as e:
            logger.warning(
                "[%s] Keyword %r yielded no news (%s) — trying next",
                name, kw, e,
            )
        except Exception as e:
            logger.warning(
                "[%s] Keyword %r unexpected error (%s) — trying next",
                name, kw, e,
            )

    if not news:
        logger.warning(
            "[%s] All %d keywords in rss_queries yielded no news today. Skipping site.",
            name, len(queries),
        )
        return False, f"skipped: all {len(queries)} keywords empty"

    logger.info(
        "[%s] Fetch OK via fallback — keyword=%r, %d items",
        name, chosen_keyword, len(news),
    )

    # ----- 2. Generate (English prompt) -------------------------------
    # Multi-key routing
    api_key_env = site.get("api_key_env", "GEMINI_API_KEY")
    api_key = os.environ.get(api_key_env)
    if not api_key:
        logger.warning(
            "[%s] api_key_env=%s 의 환경변수가 비어 있음 — GEMINI_API_KEY fallback 시도",
            name, api_key_env,
        )

    try:
        post = generate_post(
            topic_label=site.get("topic_label", name),
            niche_keyword=site.get("niche_keyword", "business"),
            news_items=news,
            language=site.get("language", "en"),
            api_key=api_key,
            focus_keyword=chosen_keyword,
        )
        logger.info(
            "[%s] Generated post — title=%s (html %d chars)",
            name, post.title, len(post.html),
        )
    except GenerationError as e:
        logger.error("[%s] Generator failed: %s", name, e)
        return False, f"generator: {e}"
    except Exception as e:
        logger.error("[%s] Generator unexpected error: %s\n%s",
                     name, e, traceback.format_exc())
        return False, f"generator-unexpected: {e}"

    # ----- 3. Publish (Blogger v3 REST API) ---------------------------
    ai_tags = list(post.tags or [])
    config_tags = list(site.get("tags") or [])
    final_tags = ai_tags if ai_tags else config_tags
    logger.info(
        "[%s] Tag source: %s (ai=%d, config=%d) → %s",
        name,
        "AI" if ai_tags else "config-fallback",
        len(ai_tags), len(config_tags), final_tags,
    )

    try:
        url = publish_to_blogger(
            blog_id=site["blog_id"],
            title=post.title,
            html_content=post.html,
            tags=final_tags,
            is_draft=bool(site.get("draft", False)),
        )
        logger.info("[%s] Published OK -> %s", name, url)
        return True, url
    except BloggerPublishError as e:
        logger.error("[%s] Publisher failed: %s", name, e)
        return False, f"publisher: {e}"
    except Exception as e:
        logger.error("[%s] Publisher unexpected error: %s\n%s",
                     name, e, traceback.format_exc())
        return False, f"publisher-unexpected: {e}"


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Daily Blogger pipeline")
    p.add_argument(
        "--group", type=int, default=None,
        help="run_group 일치하는 사이트만 실행. 미지정이면 전체.",
    )
    return p.parse_args()


def main() -> int:
    args = _parse_args()
    cfg = load_config()
    sites = cfg.get("blogger_sites") or []
    defaults = cfg.get("defaults") or {}

    if not sites:
        logger.error("No blogger_sites configured in %s", CONFIG_PATH)
        return 1

    # run_group 필터
    if args.group is not None:
        sites = [s for s in sites if s.get("run_group") == args.group]
        logger.info("Filtered by run_group=%d → %d site(s)", args.group, len(sites))
        if not sites:
            logger.warning("No sites matched run_group=%d", args.group)
            return 0

    results: list[tuple[str, bool, str]] = []
    total = len(sites)
    for idx, site in enumerate(sites):
        ok, info = run_one(site, defaults)
        results.append((site.get("name", "<unnamed>"), ok, info))

        if idx < total - 1:
            logger.info(
                "Sleeping %ds before next site (Gemini RPM safeguard)",
                INTER_SITE_SLEEP_SECONDS,
            )
            time.sleep(INTER_SITE_SLEEP_SECONDS)

    logger.info("=================== SUMMARY ===================")
    for name, ok, info in results:
        status = "OK  " if ok else "FAIL"
        logger.info("  [%s] %s — %s", status, name, info)

    failed = [r for r in results if not r[1]]
    return 0 if not failed else 2


if __name__ == "__main__":
    sys.exit(main())
