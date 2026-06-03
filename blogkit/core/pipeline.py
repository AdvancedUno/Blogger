"""The per-blog pipeline: fetch -> generate (persona) -> image (style pool) ->
publish (API or email). One function, driven entirely by a BlogProfile.
"""

from __future__ import annotations

import logging
import os
import random
import traceback

from blogkit.core.fetcher import FetchError, fetch_top_news
from blogkit.core.generator import GenerationError, Voice, generate_post
from blogkit.core.imager import build_featured_image_html
from blogkit.core.publisher import (
    BloggerPublishError,
    EmailPublishError,
    publish_to_blogger,
    publish_via_email,
)
from blogkit.profiles.base import BlogProfile

logger = logging.getLogger(__name__)

INTER_SITE_SLEEP_SECONDS = 30   # Gemini free-tier RPM safeguard between blogs
DEFAULT_MAX_NEWS_ITEMS = 6


def run_profile(profile: BlogProfile, publish_method: str = "api") -> tuple[bool, str]:
    """Run the full pipeline for one blog. Returns (ok, info)."""
    name = profile.name
    logger.info("================ START : %s ================", name)

    # ----- 1. Fetch (keyword fallback loop) ---------------------------
    queries = list(profile.rss_queries)
    random.shuffle(queries)
    news: list[dict] = []
    chosen_keyword = ""
    for kw in queries:
        try:
            news = fetch_top_news(
                queries=[kw], blog_name=name,
                max_items=DEFAULT_MAX_NEWS_ITEMS, retries=0,
            )
            if news:
                chosen_keyword = kw
                break
        except FetchError as e:
            logger.warning("[%s] Keyword %r yielded no news (%s) — next", name, kw, e)
        except Exception as e:
            logger.warning("[%s] Keyword %r error (%s) — next", name, kw, e)

    if not news:
        logger.warning("[%s] All %d keywords empty — skipping.", name, len(queries))
        return False, f"skipped: all {len(queries)} keywords empty"
    logger.info("[%s] Fetch OK — keyword=%r, %d items", name, chosen_keyword, len(news))

    # ----- 2. Generate (per-blog persona) -----------------------------
    api_key = os.environ.get(profile.api_key_env)
    if not api_key:
        logger.warning("[%s] %s empty — falling back to GEMINI_API_KEY",
                       name, profile.api_key_env)
    try:
        post = generate_post(
            topic_label=name,
            niche_keyword=profile.niche_keyword,
            news_items=news,
            api_key=api_key,
            focus_keyword=chosen_keyword,
            voice=Voice(
                persona=profile.persona,
                persona_brief=profile.persona_brief,
                tone=profile.tone,
                voice_traits=profile.voice_traits,
                flow=profile.flow,
                banned_phrases=profile.banned_phrases,
            ),
            blog_name=name,
        )
        logger.info("[%s] Generated — title=%s (%d chars)", name, post.title, len(post.html))
    except GenerationError as e:
        logger.error("[%s] Generator failed: %s", name, e)
        return False, f"generator: {e}"
    except Exception as e:
        logger.error("[%s] Generator error: %s\n%s", name, e, traceback.format_exc())
        return False, f"generator-unexpected: {e}"

    # ----- 2.5 Featured image (per-blog style pool) -------------------
    html_content = post.html
    if profile.featured_image:
        hf_token = os.environ.get("HF_API_TOKEN")
        featured = build_featured_image_html(post.title, hf_token, styles=profile.style_pool())
        if featured:
            html_content = featured + "\n" + post.html
            logger.info("[%s] Prepended hosted featured image", name)
        else:
            logger.info("[%s] No featured image — text-only", name)

    # ----- 3. Publish -------------------------------------------------
    if publish_method == "email":
        try:
            recipient = publish_via_email(post.title, html_content)
            logger.info("[%s] Emailed to Mail2Blogger (%s) OK", name, recipient)
            return True, f"emailed:{recipient}"
        except EmailPublishError as e:
            logger.error("[%s] Email publish failed: %s", name, e)
            return False, f"email: {e}"

    tags = list(post.tags or profile.tags)
    try:
        url = publish_to_blogger(
            blog_id=profile.blog_id,
            title=post.title,
            html_content=html_content,
            tags=tags,
            is_draft=profile.draft,
        )
        logger.info("[%s] Published OK -> %s", name, url)
        return True, url
    except BloggerPublishError as e:
        logger.error("[%s] Publisher failed: %s", name, e)
        return False, f"publisher: {e}"
    except Exception as e:
        logger.error("[%s] Publisher error: %s\n%s", name, e, traceback.format_exc())
        return False, f"publisher-unexpected: {e}"
