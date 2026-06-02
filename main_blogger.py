"""Daily content pipeline — generates English posts via Gemini and ships
them to Blogger via the Mail-to-Blogger SMTP feature.

The Blogger v3 REST API was abandoned after hitting daily write quotas
(repeated 429 errors). Each blog now has a `secret_email` in config.yaml
configured at Blogger Settings -> Email -> "Posting using email". This
script emails the post; Blogger publishes it on receipt.
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

# Gemini free-tier RPM ceiling is 5/min. 30s between sites keeps the loop
# in a comfortable quota window so the in-generator 65s quota-retry rarely
# fires.
INTER_SITE_SLEEP_SECONDS = 30

# Gmail's anti-spam heuristics throttle scripts that send 20 messages
# back-to-back. Sleeping 15s after each successful send keeps the cadence
# below Gmail's automated-bot threshold.
POST_SEND_ANTISPAM_SLEEP_SECONDS = 15

from src.fetcher import FetchError, fetch_top_news
from src.generator import GenerationError, generate_post
from src.mailer import MailPublishError, publish_via_email

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

    # Validate the email target up-front so we fail fast before the
    # expensive Gemini call when a config entry is missing its mail target.
    target_email = (site.get("secret_email") or "").strip()
    if not target_email:
        logger.error(
            "[%s] `secret_email` is missing from config.yaml — skipping. "
            "Add the Blogger Mail-to-Blogger address for this blog under "
            "Settings -> Email.",
            name,
        )
        return False, "config: secret_email missing"

    # ----- 1. Fetch (Keyword Fallback Loop) ---------------------------
    # B2B micro-niche keywords have a high probability of zero news on any
    # given day, so random.choice on a single keyword often fails. Shuffle
    # rss_queries and try them sequentially; break on the first keyword
    # that returns news. Skip the site only when every keyword is empty.
    try:
        queries = list(site["rss_queries"])
    except KeyError as e:
        logger.error("[%s] Fetcher failed: missing rss_queries: %s", name, e)
        return False, f"fetcher: {e}"

    if not queries:
        logger.error("[%s] rss_queries is empty", name)
        return False, "fetcher: empty rss_queries"

    random.shuffle(queries)
    max_items = int(site.get("max_news_items", defaults.get("max_news_items", 6)))
    news: list[dict] = []
    chosen_keyword = ""

    for kw in queries:
        logger.info("[%s] Trying keyword: %r", name, kw)
        try:
            news = fetch_top_news(
                queries=[kw],         # single keyword — fallback to next on empty
                blog_name=name,
                max_items=max_items,
                retries=0,            # fail fast so we can try the next keyword
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
    # Multi-key routing — per-site Gemini key with single-key fallback.
    api_key_env = site.get("api_key_env", "GEMINI_API_KEY")
    api_key = os.environ.get(api_key_env)
    if not api_key:
        logger.warning(
            "[%s] %s env var is empty — falling back to GEMINI_API_KEY",
            name, api_key_env,
        )

    try:
        post = generate_post(
            topic_label=site.get("topic_label", name),
            niche_keyword=site.get("niche_keyword", "business"),
            news_items=news,
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

    # ----- 3. Publish via Mail-to-Blogger SMTP ------------------------
    ai_tags = list(post.tags or [])
    config_tags = list(site.get("tags") or [])
    final_tags = ai_tags if ai_tags else config_tags
    logger.info(
        "[%s] Tag source: %s (ai=%d, config=%d) -> %s",
        name,
        "AI" if ai_tags else "config-fallback",
        len(ai_tags), len(config_tags), final_tags,
    )
    # NOTE: Mail-to-Blogger does NOT set post labels from email metadata —
    # the `final_tags` list is logged for traceability only. To attach
    # labels you'd need to edit each post once in Blogger UI, or switch
    # back to the API.

    try:
        publish_via_email(
            target_email=target_email,
            post_title=post.title,
            html_content=post.html,
        )
        logger.info("[%s] Emailed -> %s", name, target_email)
    except MailPublishError as e:
        logger.error("[%s] Mailer failed: %s", name, e)
        return False, f"mailer: {e}"
    except Exception as e:
        logger.error("[%s] Mailer unexpected error: %s\n%s",
                     name, e, traceback.format_exc())
        return False, f"mailer-unexpected: {e}"

    # Gmail anti-spam pause — fires only on a successful send.
    logger.info(
        "[%s] Sleeping %ds (Gmail anti-spam pause)",
        name, POST_SEND_ANTISPAM_SLEEP_SECONDS,
    )
    time.sleep(POST_SEND_ANTISPAM_SLEEP_SECONDS)

    return True, target_email


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Daily content pipeline (Mail-to-Blogger)")
    p.add_argument(
        "--group", type=int, default=None,
        help="Run only sites with a matching run_group value. Default: all.",
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

    # run_group filter
    if args.group is not None:
        sites = [s for s in sites if s.get("run_group") == args.group]
        logger.info("Filtered by run_group=%d -> %d site(s)", args.group, len(sites))
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
        logger.info("  [%s] %s -- %s", status, name, info)

    failed = [r for r in results if not r[1]]
    return 0 if not failed else 2


if __name__ == "__main__":
    sys.exit(main())
