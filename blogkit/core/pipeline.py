"""The per-blog pipeline: fetch -> generate (persona) -> image (style pool) ->
publish (API or email). One function, driven entirely by a BlogProfile.
"""

from __future__ import annotations

import logging
import os
import random
import traceback

from blogkit.core.analytics import fetch_top_queries, prioritize_queries
from blogkit.core.dedup import Ledger
from blogkit.core.enrich import add_toc, reading_time_badge, related_posts_html
from blogkit.core.fetcher import FetchError, fetch_top_news
from blogkit.core.formats import resolve_format_name
from blogkit.core.generator import GenerationError, Voice, generate_post
from blogkit.core.imager import build_featured_image_html
from blogkit.core.publisher import (
    BloggerPublishError,
    EmailPublishError,
    publish_to_blogger,
    publish_via_email,
)
from blogkit.core.seo import build_jsonld, build_references_html
from blogkit.profiles.base import BlogProfile

logger = logging.getLogger(__name__)

INTER_SITE_SLEEP_SECONDS = 30   # Gemini free-tier RPM safeguard between blogs
DEFAULT_MAX_NEWS_ITEMS = 6


def run_profile(
    profile: BlogProfile,
    publish_method: str = "api",
    ledger: Ledger | None = None,
    dry_run: bool = False,
) -> tuple[bool, str]:
    """Run the full pipeline for one blog. Returns (ok, info).

    When a `ledger` is supplied, source articles already used network-wide
    within the recency window are filtered out (duplicate-content guard), and
    the published title/links are recorded back into it.

    With `dry_run=True`, the post is generated and assembled but NOT published,
    the ledger is NOT updated, and the (costly) featured image is skipped — for
    safe, cheap end-to-end testing.
    """
    name = profile.name
    logger.info("================ START : %s ================", name)

    # ----- 1. Fetch (keyword fallback loop + cross-blog de-dup) --------
    # Bias the roulette toward Search Console winners when configured; else
    # plain shuffle. Best-effort — GSC failure just falls back to shuffle.
    queries = list(profile.rss_queries)
    gsc_rows = (
        fetch_top_queries(profile.analytics_site)
        if (profile.analytics_site and not dry_run) else []
    )
    if gsc_rows:
        queries = prioritize_queries(queries, gsc_rows)
        logger.info("[%s] Keyword order biased by %d Search Console signals",
                    name, len(gsc_rows))
    else:
        random.shuffle(queries)
    news: list[dict] = []
    chosen_keyword = ""
    for kw in queries:
        try:
            fetched = fetch_top_news(
                queries=[kw], blog_name=name,
                max_items=DEFAULT_MAX_NEWS_ITEMS, retries=0,
            )
        except FetchError as e:
            logger.warning("[%s] Keyword %r yielded no news (%s) — next", name, kw, e)
            continue
        except Exception as e:
            logger.warning("[%s] Keyword %r error (%s) — next", name, kw, e)
            continue
        if not fetched:
            continue
        # Drop source articles already used network-wide recently.
        if ledger is not None:
            urls = [n.get("link", "") for n in fetched if n.get("link")]
            fresh = set(ledger.fresh_links(urls))
            kept = [n for n in fetched if not n.get("link") or n["link"] in fresh]
            if len(kept) < len(fetched):
                logger.info("[%s] De-dup dropped %d/%d used articles for %r",
                            name, len(fetched) - len(kept), len(fetched), kw)
            fetched = kept
        if fetched:
            news = fetched
            chosen_keyword = kw
            break

    if not news:
        logger.warning("[%s] No fresh news across %d keywords — skipping.", name, len(queries))
        return False, f"skipped: no fresh news ({len(queries)} keywords)"
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
            post_format=resolve_format_name(profile.slug, profile.post_format),
        )
        logger.info("[%s] Generated — title=%s (%d chars)", name, post.title, len(post.html))
    except GenerationError as e:
        logger.error("[%s] Generator failed: %s", name, e)
        return False, f"generator: {e}"
    except Exception as e:
        logger.error("[%s] Generator error: %s\n%s", name, e, traceback.format_exc())
        return False, f"generator-unexpected: {e}"

    # Soft near-duplicate-title check (warn only — don't waste the generation).
    if ledger is not None:
        clash = ledger.title_clashes(post.title)
        if clash:
            logger.warning("[%s] Title near-dupe of recent %r — publishing anyway", name, clash)

    def _record(url: str = "") -> None:
        if ledger is not None:
            ledger.record(
                slug=profile.slug, keyword=chosen_keyword, title=post.title,
                links=[n["link"] for n in news if n.get("link")], url=url,
            )

    # ----- 2.5 Engagement + SEO enrichment ----------------------------
    # reading-time + clickable ToC (with heading anchors) at the top; internal
    # related-posts links + real source citations + JSON-LD at the bottom.
    body = reading_time_badge(post.html) + "\n" + add_toc(post.html)
    if ledger is not None:
        related = related_posts_html(ledger.recent_posts(profile.slug))
        if related:
            body += "\n" + related
    refs = build_references_html(news)
    if refs:
        body += "\n" + refs
    body += "\n" + build_jsonld(
        title=post.title, html_body=post.html, blog_name=name, news_items=news,
        tags=list(post.tags or profile.tags), section=profile.niche_keyword,
    )

    # ----- 2.6 Featured image (per-blog style pool; skipped in dry-run) ---
    html_content = body
    if dry_run:
        logger.info(
            "[%s] DRY-RUN — would publish %d-char post titled %r (image skipped). "
            "Not published, ledger untouched.", name, len(html_content), post.title,
        )
        return True, f"dry-run:{len(html_content)} chars"

    if profile.featured_image:
        hf_token = os.environ.get("HF_API_TOKEN")
        featured = build_featured_image_html(post.title, hf_token, styles=profile.style_pool())
        if featured:
            html_content = featured + "\n" + body
            logger.info("[%s] Prepended hosted featured image", name)
        else:
            logger.info("[%s] No featured image — text-only", name)

    # ----- 3. Publish -------------------------------------------------
    if publish_method == "email":
        try:
            recipient = publish_via_email(post.title, html_content)
            logger.info("[%s] Emailed to Mail2Blogger (%s) OK", name, recipient)
            _record()
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
        _record(url)
        return True, url
    except BloggerPublishError as e:
        logger.error("[%s] Publisher failed: %s", name, e)
        return False, f"publisher: {e}"
    except Exception as e:
        logger.error("[%s] Publisher error: %s\n%s", name, e, traceback.format_exc())
        return False, f"publisher-unexpected: {e}"
