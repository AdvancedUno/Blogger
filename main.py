"""Daily multi-blog pipeline entrypoint.

Loops over every blog profile defined in `config.yaml`:
  1) Fetch top Google News RSS items for the blog's query
  2) Generate a Tistory-ready Korean HTML post via Gemini
  3) Publish to Tistory via Open API

A failure in one blog does NOT abort the pipeline for the others.
The process exits non-zero if any blog failed (so CI surfaces it).
"""
from __future__ import annotations

import logging
import sys
import traceback
from pathlib import Path

import yaml

from src.fetcher import FetchError, fetch_top_news
from src.generator import GenerationError, generate_post
from src.publisher import PublishError, publish_to_tistory

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("daily_post")

CONFIG_PATH = Path(__file__).parent / "config.yaml"


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"Missing config file: {CONFIG_PATH}")
    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def run_one(blog: dict, defaults: dict) -> tuple[bool, str]:
    name = blog.get("name", "<unnamed>")
    logger.info("================ START : %s ================", name)

    # ----- 1. Fetch ---------------------------------------------------
    try:
        news = fetch_top_news(
            query=blog["rss_query"],
            max_items=int(blog.get("max_news_items", defaults.get("max_news_items", 6))),
        )
        logger.info("[%s] Fetched %d news items", name, len(news))
    except (FetchError, KeyError) as e:
        logger.error("[%s] Fetcher failed: %s", name, e)
        return False, f"fetcher: {e}"
    except Exception as e:
        logger.error("[%s] Fetcher unexpected error: %s\n%s",
                     name, e, traceback.format_exc())
        return False, f"fetcher-unexpected: {e}"

    # ----- 2. Generate ------------------------------------------------
    try:
        post = generate_post(
            topic_label=blog["topic_label"],
            niche_keyword=blog["niche_keyword"],
            news_items=news,
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

    # ----- 3. Publish (Playwright + storage_state 주입) ---------------
    # 태그 우선순위: AI 가 생성한 5~7개 SEO 태그 → 비었으면 config 태그.
    ai_tags = list(post.tags or [])
    config_tags = list(blog.get("tags") or [])
    final_tags = ai_tags if ai_tags else config_tags
    logger.info(
        "[%s] Tag source: %s (ai=%d, config=%d) → %s",
        name,
        "AI" if ai_tags else "config-fallback",
        len(ai_tags), len(config_tags), final_tags,
    )

    try:
        url = publish_to_tistory(
            blog_name=blog["blog_name"],
            title=post.title,
            html_content=post.html,
            tags=final_tags,
            headless=bool(defaults.get("headless", True)),
        )
        logger.info("[%s] Published OK -> %s", name, url)
        return True, url
    except PublishError as e:
        logger.error("[%s] Publisher failed: %s", name, e)
        return False, f"publisher: {e}"
    except Exception as e:
        logger.error("[%s] Publisher unexpected error: %s\n%s",
                     name, e, traceback.format_exc())
        return False, f"publisher-unexpected: {e}"


def main() -> int:
    cfg = load_config()
    blogs = cfg.get("blogs") or []
    defaults = cfg.get("defaults") or {}

    if not blogs:
        logger.error("No blogs configured in %s", CONFIG_PATH)
        return 1

    results: list[tuple[str, bool, str]] = []
    for blog in blogs:
        ok, info = run_one(blog, defaults)
        results.append((blog.get("name", "<unnamed>"), ok, info))

    logger.info("=================== SUMMARY ===================")
    for name, ok, info in results:
        status = "OK  " if ok else "FAIL"
        logger.info("  [%s] %s — %s", status, name, info)

    failed = [r for r in results if not r[1]]
    return 0 if not failed else 2


if __name__ == "__main__":
    sys.exit(main())
