"""Daily Blogger pipeline entrypoint.

Reads the `blogger_sites` section of config.yaml, generates an English
analytical post via Gemini, and publishes it through the Blogger v3 REST
API. No Playwright / storage_state dependency, no SMTP — pure REST.

Required environment variables (provided via GitHub Secrets in CI):
    GEMINI_API_KEY (+ optional GEMINI_API_KEY_1..10 for multi-key routing)
    GOOGLE_CLIENT_ID
    GOOGLE_CLIENT_SECRET
    GOOGLE_REFRESH_TOKEN
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import logging
import os
import random
import sys
import time
import traceback
from pathlib import Path
from urllib.parse import quote

import requests
import yaml

# Sleep between sites to stay under the Gemini free-tier RPM ceiling
# (5 requests/min). 30s spreads the loop across enough quota windows that
# the in-generator 65s quota-retry rarely needs to fire.
INTER_SITE_SLEEP_SECONDS = 30

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


# =====================================================================
# Featured image (opt-in via the `featured_image` config flag)
# =====================================================================
# Disabled by default: the blog is text-only, which keeps post bodies
# light (AdSense / page-speed friendly) and never depends on a flaky
# external image CDN. When enabled, we generate a unique pollinations.ai
# image PER POST, download it HERE (at publish time), and inline it as
# base64 — so the *live* post never makes an external image request.
# Any failure falls back to text-only (see build_featured_image_html).
POLLINATIONS_ENDPOINT = "https://image.pollinations.ai/prompt/{prompt}"
IMAGE_PROMPT_TEMPLATE = (
    "Abstract minimalist 3D geometric rendering representing {title}, "
    "dark corporate tech aesthetic, professional lighting, high detail, no text"
)
IMAGE_REQUEST_TIMEOUT = 30.0   # pollinations generates on first request (slow)


def build_featured_image_html(generated_title: str) -> str | None:
    """Generate a unique pollinations.ai image for this post, download it,
    and return a JetTheme-styled <div> with the image inlined as base64.

    Best-effort: returns None on any failure so the caller can publish
    text-only without crashing.
    """
    try:
        # Deterministic seed from the title: distinct titles -> distinct
        # images, and re-running the same post reproduces the same image.
        seed = int(
            hashlib.sha256(generated_title.encode("utf-8")).hexdigest(), 16
        ) % (10 ** 8)

        prompt = IMAGE_PROMPT_TEMPLATE.format(title=generated_title)
        url = POLLINATIONS_ENDPOINT.format(prompt=quote(prompt, safe=""))
        params = {
            "width": 1200,
            "height": 630,
            "seed": seed,
            "nologo": "true",
            "model": "flux",
        }

        resp = requests.get(url, params=params, timeout=IMAGE_REQUEST_TIMEOUT)
        resp.raise_for_status()

        # Use the real content-type rather than assuming jpeg — pollinations
        # sometimes returns PNG, and a mismatched data-URI prefix renders
        # broken in some browsers.
        content_type = (
            resp.headers.get("content-type") or "image/jpeg"
        ).split(";")[0].strip()
        if not content_type.startswith("image/"):
            raise ValueError(f"unexpected content-type: {content_type!r}")
        if not resp.content:
            raise ValueError("empty image body")

        b64 = base64.b64encode(resp.content).decode("ascii")
        alt = generated_title.replace('"', "&quot;")   # safe in attr context
        logger.info(
            "Featured image OK — %s, %d KB base64", content_type, len(b64) // 1024
        )
        return (
            '<div class="mb-5">'
            f'<img src="data:{content_type};base64,{b64}" '
            f'class="img-fluid rounded shadow-sm w-100" alt="{alt}" />'
            '</div>'
        )
    except Exception as e:
        logger.warning(
            "Featured image generation failed (%s) — publishing text-only", e
        )
        return None


def run_one(site: dict, defaults: dict) -> tuple[bool, str]:
    name = site.get("name", "<unnamed>")
    logger.info("================ START : %s ================", name)

    # Validate the blog_id up-front so we fail fast before the expensive
    # Gemini call when a config entry is missing its target.
    blog_id = str(site.get("blog_id") or "").strip()
    if not blog_id or blog_id.startswith("["):
        logger.error(
            "[%s] `blog_id` is missing or a placeholder (%r) — skipping.",
            name, blog_id,
        )
        return False, "config: blog_id missing"

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

    # ----- 2.5 Featured image (opt-in, base64-embedded) ---------------
    # Off unless `featured_image: true` is set on the site or in defaults.
    html_content = post.html
    featured_enabled = bool(
        site.get("featured_image", defaults.get("featured_image", False))
    )
    if featured_enabled:
        featured_html = build_featured_image_html(post.title)
        if featured_html:
            html_content = featured_html + "\n" + post.html
            logger.info(
                "[%s] Prepended base64 featured image (body now %d chars)",
                name, len(html_content),
            )
        else:
            logger.info("[%s] Featured image failed — publishing text-only", name)

    # ----- 3. Publish via Blogger v3 REST API -------------------------
    ai_tags = list(post.tags or [])
    config_tags = list(site.get("tags") or [])
    final_tags = ai_tags if ai_tags else config_tags
    logger.info(
        "[%s] Tag source: %s (ai=%d, config=%d) -> %s",
        name,
        "AI" if ai_tags else "config-fallback",
        len(ai_tags), len(config_tags), final_tags,
    )

    try:
        url = publish_to_blogger(
            blog_id=blog_id,
            title=post.title,
            html_content=html_content,
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
    p = argparse.ArgumentParser(description="Daily Blogger pipeline (Blogger v3 REST API)")
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
