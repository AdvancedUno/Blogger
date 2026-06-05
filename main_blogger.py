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
import re
import smtplib
import sys
import time
import traceback
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

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
# Email publishing (fallback for Blogger API 429 daily-quota days)
# =====================================================================
# Mail-to-Blogger: each blog has a unique secret "Mail2Blogger" address;
# an email sent to it is published as a post (Subject -> title, HTML body
# -> content). Use `--publish-method email` to route here instead of the
# REST API. Credentials come from env (GitHub Secrets in CI):
#   SMTP_USER             — Gmail address used to send
#   SMTP_PASSWORD         — Gmail App Password (NOT the account password)
#   BLOGGER_SECRET_EMAIL  — the blog's Mail2Blogger address
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_POST_SEND_SLEEP = 10   # avoid Gmail spam-filter rate flags between sends


class EmailPublishError(RuntimeError):
    """Raised when SMTP / mail-to-Blogger publishing fails."""


def publish_via_email(title: str, html_content: str) -> str:
    """Publish a post by emailing it to the blog's Mail2Blogger address.

    Returns the recipient address on success; raises EmailPublishError on
    any failure (missing creds, SMTP/auth error) so the caller can record
    the site as failed.
    """
    user = os.environ.get("SMTP_USER")
    password = os.environ.get("SMTP_PASSWORD")
    recipient = os.environ.get("BLOGGER_SECRET_EMAIL")
    missing = [
        k for k, v in {
            "SMTP_USER": user,
            "SMTP_PASSWORD": password,
            "BLOGGER_SECRET_EMAIL": recipient,
        }.items() if not v
    ]
    if missing:
        raise EmailPublishError(
            f"Missing required env vars: {', '.join(missing)} — "
            "must be set (GitHub Secrets in CI)."
        )
    if not title or not html_content:
        raise EmailPublishError("Empty title or content cannot be emailed")

    msg = MIMEMultipart()
    msg["From"] = user
    msg["To"] = recipient
    msg["Subject"] = title
    msg.attach(MIMEText(html_content, "html", "utf-8"))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as server:
            server.starttls()
            server.login(user, password)
            server.sendmail(user, [recipient], msg.as_string())
    except Exception as e:
        raise EmailPublishError(f"SMTP send failed: {e}") from e

    # Space out sends so Gmail doesn't flag the burst as spam.
    time.sleep(SMTP_POST_SEND_SLEEP)
    return recipient


# =====================================================================
# Featured image (opt-in via the `featured_image` config flag)
# =====================================================================
# Disabled by default. When enabled, we generate a unique image PER POST,
# host it on GitHub (advancedunolee/blog-assets) and embed an immutable jsDelivr
# CDN URL — NOT a base64 data: URI. Blogger's homepage thumbnail extractor
# and JetTheme's JS only recognize a real http(s) <img src>, so a hosted URL
# is required for thumbnails to render (and it keeps post bodies light).
# Any failure falls back to text-only.
#
# ENGINE: Hugging Face Inference Providers (router.huggingface.co), first-party
# `hf-inference` provider, model black-forest-labs/FLUX.1-schnell — free /
# rate-limited. (SDXL left the free tier; the legacy api-inference host is dead.)
# The HF token must be a fine-grained token with "Inference Providers"
# permission. The Gemini engine below is kept parked for future use.
# =====================================================================
HF_IMAGE_ENDPOINT = (
    "https://router.huggingface.co/hf-inference/models/"
    "black-forest-labs/FLUX.1-schnell"
)

# Rotating art-direction presets — picked deterministically per title (hash)
# so each post gets a distinct, on-theme look instead of the same bland frame.
# Mix of photoreal and stylized so the network doesn't feel monotonous.
HF_STYLE_PRESETS = [
    # --- [기존 스타일 (오리지널)] ---
    "cinematic editorial photograph, shallow depth of field, dramatic natural "
    "lighting, photorealistic, shot on 35mm, ultra detailed, 8k",
    
    "wide cinematic establishing shot of a sleek modern high-tech environment, "
    "volumetric light, realistic materials, professional architectural photography",
    
    "premium macro product photography, intricate detail, soft studio lighting, "
    "rich bokeh, hyper realistic",
    
    "sleek isometric 3D render, clean corporate infographic aesthetic, soft "
    "gradients, subtle depth of field, octane render",
    
    "abstract data-flow visualization, glowing interconnected network nodes and "
    "lines on a dark background, futuristic, elegant, depth",
    
    "minimalist conceptual still life, one bold symbolic subject, premium muted "
    "color palette, soft directional shadows, gallery lighting",

    # --- [새로 추가된 B2B 테크 특화 스타일 10종] ---
    
    # 7. 글래스모피즘 (애플/현대 IT 기업 UI 스타일)
    "modern glassmorphism 3D render, translucent frosted glass shapes, "
    "floating tech elements, soft pastel gradient background, ultra clean, 8k",
    
    # 8. 이중 노출 (인간과 기술의 결합, 감성적인 테크)
    "sophisticated double exposure photography, blending a corporate business "
    "silhouette with glowing fiber optic data networks, cinematic, highly detailed",
    
    # 9. 고급 페이퍼크래프트 (추상적이고 깔끔한 비즈니스 은유)
    "elegant minimalist 3D papercraft art, layered clean white paper, "
    "subtle colored backlighting, corporate tech metaphor, highly detailed",
    
    # 10. 마이크로칩 매크로 (하드웨어, 인프라, 보안 주제에 적합)
    "extreme macro photography of a silicon microchip, glowing circuitry pathways, "
    "iridescent gold and blue reflections, hyper-detailed tech photography",
    
    # 11. 청사진/설계도 (아키텍처, 전략, 분석 주제에 적합)
    "futuristic architectural blueprint schematic, glowing neon cyan and gold lines "
    "on dark navy grid, technical data visualization, precise engineering",
    
    # 12. 어두운 서버룸 (클라우드, 데이터센터, 백엔드 주제)
    "cinematic server room interior, moody dark tech atmosphere, glowing led "
    "indicator lights, shallow depth of field, photorealistic, 8k",
    
    # 13. 홀로그램 증강현실 (미래 지향적, 혁신 주제)
    "glowing futuristic 3D hologram floating in a dark modern office setting, "
    "volumetric light rays, augmented reality interface, photorealistic",
    
    # 14. 로우 폴리 (세련된 기하학적 3D, 소프트웨어/SaaS 주제)
    "sleek low poly 3D geometric landscape, corporate tech aesthetic, "
    "smooth shading, ambient occlusion, crisp edges, professional color palette",
    
    # 15. 수채화/잉크 일러스트 (월스트리트 저널 등 고급 언론사 사설 느낌)
    "sophisticated modern editorial illustration, fluid watercolor and ink, "
    "tech business concept, muted corporate colors, elegant and expressive",
    
    # 16. 초현실주의 비즈니스 (마그리트 스타일, 철학적/심층 분석 글에 적합)
    "surreal conceptual photography, floating glowing geometric spheres over a "
    "minimalist concrete desk, dramatic lighting, luxury editorial style"
]
HF_IMAGE_WIDTH = 1024           # 16:9 landscape (multiples of 16 for FLUX)
HF_IMAGE_HEIGHT = 576
HF_MAX_RETRIES = 3              # free model is often cold (503 while loading)
HF_DEFAULT_COLD_WAIT = 20.0     # used when the 503 body has no estimated_time
HF_COLD_WAIT_BUFFER = 5.0       # extra seconds on top of estimated_time
HF_REQUEST_TIMEOUT = 120.0      # cold load + generation can be slow

# --- Image hosting (GitHub Contents API -> jsDelivr CDN) -------------------
ASSETS_REPO = "advancedunolee/blog-assets"
GITHUB_CONTENTS_API = "https://api.github.com/repos/{repo}/contents/{path}"
JSDELIVR_URL = "https://cdn.jsdelivr.net/gh/{repo}@{sha}/{path}"
GITHUB_UPLOAD_TIMEOUT = 30.0


def _slugify(text: str) -> str:
    """Lowercase, hyphenate, ASCII-safe slug (<=60 chars) for the file path."""
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return s[:60].strip("-") or "post"


def _build_hf_image_prompt(title: str) -> tuple[str, int]:
    """Build a creative, on-theme image prompt + a deterministic seed.

    The same title always yields the same prompt/seed (reproducible), but the
    style preset rotates by hash so different posts look meaningfully different.
    """
    seed = int(hashlib.sha256(title.encode("utf-8")).hexdigest(), 16) % (2 ** 32)
    style = HF_STYLE_PRESETS[seed % len(HF_STYLE_PRESETS)]
    prompt = (
        f'A striking editorial cover image that visually represents the concept '
        f'of "{title}". {style}. Strong single focal subject, clean composition, '
        f'no text, no words, no letters, no watermark, no logos.'
    )
    return prompt, seed


def _upload_image_to_github(png_bytes: bytes, title: str) -> str:
    """PUT the PNG to the blog-assets repo via the GitHub Contents API and
    return an immutable jsDelivr CDN URL pinned to the new commit SHA.

    Raises on any failure (missing PAT, HTTP error, malformed response) so the
    caller's try/except can fall back to text-only.
    """
    pat = os.environ.get("ASSETS_REPO_PAT")
    if not pat:
        raise ValueError("no ASSETS_REPO_PAT available for image upload")

    now = datetime.now(timezone.utc)
    # The timestamp keeps every path unique, so the PUT is always a fresh
    # create (no need to fetch an existing blob sha for an update), and repeats
    # of the same title never collide.
    path = (
        f"images/{now:%Y}/{now:%m}/"
        f"{_slugify(title)}-{now:%Y%m%d%H%M%S}.png"
    )

    payload = {
        "message": f"Add featured image: {title[:72]}",
        # GitHub Contents API wants the file content base64-encoded in JSON.
        "content": base64.b64encode(png_bytes).decode("ascii"),
    }
    headers = {
        "Authorization": f"Bearer {pat}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    resp = requests.put(
        GITHUB_CONTENTS_API.format(repo=ASSETS_REPO, path=path),
        headers=headers,
        json=payload,
        timeout=GITHUB_UPLOAD_TIMEOUT,
    )
    resp.raise_for_status()

    sha = resp.json()["commit"]["sha"]   # immutable commit SHA for the CDN URL
    return JSDELIVR_URL.format(repo=ASSETS_REPO, sha=sha, path=path)


def build_hf_featured_image_html(title: str, hf_token: str | None) -> str | None:
    """Generate a creative, on-theme image via HF (hf-inference / FLUX.1-schnell),
    upload it to the blog-assets GitHub repo, and return a JetTheme-styled <div>
    whose <img src> is an immutable jsDelivr CDN URL.

    A real https URL (not a data: URI) is required so Blogger's homepage
    thumbnail extractor and JetTheme's JS recognize it as the featured image.

    The free tier may return 503 while a cold model loads; we honor the
    `estimated_time` from the body and retry up to HF_MAX_RETRIES times.

    Args:
        title: Post title — drives the (rotating) prompt and the seed.
        hf_token: Hugging Face token with Inference Providers permission
            (HF_API_TOKEN env var).

    Best-effort: returns None on any failure (HF still cold after all retries,
    HTTP error, GitHub upload failure) so the caller can publish text-only
    without crashing.
    """
    try:
        if not hf_token:
            raise ValueError("no Hugging Face token available (HF_API_TOKEN)")

        prompt, seed = _build_hf_image_prompt(title)
        headers = {"Authorization": f"Bearer {hf_token}"}
        payload = {
            "inputs": prompt,
            "parameters": {
                "width": HF_IMAGE_WIDTH,
                "height": HF_IMAGE_HEIGHT,
                "seed": seed,
            },
        }

        # 1) Generate — get the raw PNG bytes (with cold-model 503 retry).
        png_bytes: bytes | None = None
        for attempt in range(HF_MAX_RETRIES):
            resp = requests.post(
                HF_IMAGE_ENDPOINT,
                headers=headers,
                json=payload,
                timeout=HF_REQUEST_TIMEOUT,
            )

            # 503 = model cold/loading. Back off for estimated_time + buffer.
            if resp.status_code == 503:
                try:
                    wait = float(resp.json().get("estimated_time",
                                                 HF_DEFAULT_COLD_WAIT))
                except Exception:
                    wait = HF_DEFAULT_COLD_WAIT
                wait += HF_COLD_WAIT_BUFFER
                logger.warning(
                    "HF model loading (503), attempt %d/%d — sleeping %.0fs",
                    attempt + 1, HF_MAX_RETRIES, wait,
                )
                time.sleep(wait)
                continue

            resp.raise_for_status()   # any other non-2xx -> outer except
            if not resp.content:
                raise ValueError("empty image body from Hugging Face")
            png_bytes = resp.content
            logger.info(
                "HF image generated — %d KB (seed=%d)", len(png_bytes) // 1024, seed
            )
            break

        if png_bytes is None:
            logger.warning(
                "HF image still loading after %d retries — publishing text-only",
                HF_MAX_RETRIES,
            )
            return None

        # 2) Host it — Blogger thumbnails need a real http(s) URL, not base64.
        cdn_url = _upload_image_to_github(png_bytes, title)
        logger.info("Featured image hosted -> %s", cdn_url)

        # 3) Wrap the CDN URL in the JetTheme container.
        alt = title.replace('"', "&quot;")   # safe in attr context
        return (
            '<div class="mb-5">'
            f'<img src="{cdn_url}" '
            f'class="img-fluid rounded shadow-sm w-100" alt="{alt}" />'
            '</div>'
        )
    except Exception as e:
        logger.warning(
            "HF featured image generation/upload failed (%s) — publishing "
            "text-only", e,
        )
        return None


WARM_UP_PROMPT = "warm up the model, a simple blue cube"


def warm_up_hf_model(hf_token: str | None) -> None:
    """Fire a dummy generation at the HF endpoint so the model is loaded into
    memory BEFORE the per-blog loop — absorbing the cold-start 503/load delay
    once, up front, instead of inside the first blog's publish.

    Uses the same 503 retry/sleep logic as build_hf_featured_image_html. We
    discard the image; the only goal is to make the model hot. Returns once it
    gets a 200 (or exhausts retries). Never raises — warm-up is best-effort,
    so a failure here must not abort the run.
    """
    if not hf_token:
        logger.warning("HF warm-up skipped — no HF_API_TOKEN")
        return

    headers = {"Authorization": f"Bearer {hf_token}", "Accept": "image/jpeg"}
    payload = {"inputs": WARM_UP_PROMPT}
    try:
        for attempt in range(HF_MAX_RETRIES):
            resp = requests.post(
                HF_IMAGE_ENDPOINT,
                headers=headers,
                json=payload,
                timeout=HF_REQUEST_TIMEOUT,
            )

            # 503 = model cold/loading. Back off for estimated_time + buffer.
            if resp.status_code == 503:
                try:
                    wait = float(resp.json().get("estimated_time",
                                                 HF_DEFAULT_COLD_WAIT))
                except Exception:
                    wait = HF_DEFAULT_COLD_WAIT
                wait += HF_COLD_WAIT_BUFFER
                logger.info(
                    "HF warm-up: model loading (503), attempt %d/%d — "
                    "sleeping %.0fs", attempt + 1, HF_MAX_RETRIES, wait,
                )
                time.sleep(wait)
                continue

            if resp.ok:
                logger.info("HF warm-up: model is hot (HTTP %d)", resp.status_code)
            else:
                logger.warning(
                    "HF warm-up: unexpected HTTP %d — continuing anyway",
                    resp.status_code,
                )
            return

        logger.warning(
            "HF warm-up: model still loading after %d retries — continuing "
            "anyway (first blog may absorb the remaining load time)",
            HF_MAX_RETRIES,
        )
    except Exception as e:
        logger.warning("HF warm-up failed (%s) — continuing anyway", e)


# =====================================================================
# Preserved for future use when Google Cloud Billing is enabled
# =====================================================================
# gemini-2.5-flash-image is a Gemini model (uses :generateContent, NOT
# :predict / :generateImages — those are Imagen's predict API). The image
# returns as an inlineData part on the first candidate, already base64.
# This is a BILLED image model, not part of the free text tier — that's why
# the active engine above is Hugging Face. Not called in the main loop.
IMAGE_MODEL = "gemini-2.5-flash-image"
GENAI_IMAGE_ENDPOINT = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
)
IMAGE_PROMPT_TEMPLATE = (
    "Abstract minimalist 3D geometric rendering representing {title}, "
    "dark corporate tech aesthetic, professional lighting, high detail, no text"
)
IMAGE_ASPECT_RATIO = "16:9"     # blog-thumbnail friendly
IMAGE_REQUEST_TIMEOUT = 60.0    # image generation is slower than text


def build_gemini_featured_image_html(
    generated_title: str, api_key: str | None
) -> str | None:
    """Generate a unique image for this post via the gemini-2.5-flash-image
    REST endpoint and return a JetTheme-styled <div> with it inlined as base64.

    Args:
        generated_title: Post title — embedded in the prompt for uniqueness.
        api_key: The per-site Gemini key resolved by the caller (falls back
            to the GEMINI_API_KEY env var, same as the text generator).

    Best-effort: returns None on any failure (quota, timeout, malformed
    response) so the caller can publish text-only without crashing.
    """
    try:
        effective_key = api_key or os.environ.get("GEMINI_API_KEY")
        if not effective_key:
            raise ValueError("no Gemini API key available for image generation")

        prompt = IMAGE_PROMPT_TEMPLATE.format(title=generated_title)
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseModalities": ["IMAGE"],
                "imageConfig": {"aspectRatio": IMAGE_ASPECT_RATIO},
            },
        }

        resp = requests.post(
            GENAI_IMAGE_ENDPOINT.format(model=IMAGE_MODEL),
            params={"key": effective_key},
            json=payload,
            timeout=IMAGE_REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()

        # The base64 image is an inlineData part on the first candidate.
        parts = (
            data.get("candidates", [{}])[0]
            .get("content", {})
            .get("parts", [])
        )
        inline = next(
            (p["inlineData"] for p in parts
             if p.get("inlineData", {}).get("data")),
            None,
        )
        if not inline:
            raise ValueError(f"no inline image in response: {str(data)[:200]}")

        b64 = inline["data"]                       # already base64
        mime = inline.get("mimeType", "image/png")  # model returns PNG
        alt = generated_title.replace('"', "&quot;")   # safe in attr context
        logger.info(
            "Featured image OK — %s, %d KB base64", mime, len(b64) // 1024
        )
        return (
            '<div class="mb-5">'
            f'<img src="data:{mime};base64,{b64}" '
            f'class="img-fluid rounded shadow-sm w-100" alt="{alt}" />'
            '</div>'
        )
    except Exception as e:
        logger.warning(
            "Featured image generation failed (%s) — publishing text-only", e
        )
        return None


def run_one(site: dict, defaults: dict, publish_method: str = "api") -> tuple[bool, str]:
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
        # Active engine: Hugging Face FLUX.1-schnell (free). Token: HF_API_TOKEN.
        # (Gemini engine is preserved but not wired in — see
        # build_gemini_featured_image_html.)
        hf_token = os.environ.get("HF_API_TOKEN")
        featured_html = build_hf_featured_image_html(post.title, hf_token)
        if featured_html:
            html_content = featured_html + "\n" + post.html
            logger.info(
                "[%s] Prepended hosted featured image (body now %d chars)",
                name, len(html_content),
            )
        else:
            logger.info("[%s] Featured image failed — publishing text-only", name)

    # ----- 3. Publish (route on --publish-method) ---------------------
    # Email fallback (Mail2Blogger) — for days the REST API is 429'd.
    if publish_method == "email":
        try:
            recipient = publish_via_email(post.title, html_content)
            logger.info("[%s] Emailed to Mail2Blogger (%s) OK", name, recipient)
            return True, f"emailed:{recipient}"
        except EmailPublishError as e:
            logger.error("[%s] Email publish failed: %s", name, e)
            return False, f"email: {e}"
        except Exception as e:
            logger.error("[%s] Email publish unexpected error: %s\n%s",
                         name, e, traceback.format_exc())
            return False, f"email-unexpected: {e}"

    # Default: Blogger v3 REST API.
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
    p.add_argument(
        "--publish-method", choices=["api", "email"], default="api",
        help="How to publish: 'api' (Blogger v3 REST, default) or 'email' "
             "(Mail2Blogger SMTP fallback for API 429 quota days).",
    )
    p.add_argument(
        "--selftest-image", action="store_true",
        help="Generate ONE featured image, upload it to blog-assets, print the "
             "jsDelivr URL + HTML, then exit. Publishes nothing. Use to test "
             "the HF + GitHub-upload path. Needs HF_API_TOKEN and ASSETS_REPO_PAT.",
    )
    return p.parse_args()


def _run_selftest_image() -> int:
    """Exercise the full featured-image path (HF generate -> GitHub upload ->
    jsDelivr URL) once, without fetching news or publishing a post."""
    hf_token = os.environ.get("HF_API_TOKEN")
    missing = [
        k for k, v in {
            "HF_API_TOKEN": hf_token,
            "ASSETS_REPO_PAT": os.environ.get("ASSETS_REPO_PAT"),
        }.items() if not v
    ]
    if missing:
        logger.error("--selftest-image needs env vars: %s", ", ".join(missing))
        return 1

    sample_title = (
        "Self-Test: Enterprise AI Infrastructure Cost Optimization in 2026"
    )
    logger.info("Self-test: warming up model, then generating one image for %r",
                sample_title)
    warm_up_hf_model(hf_token)

    html = build_hf_featured_image_html(sample_title, hf_token)
    if not html:
        logger.error(
            "Self-test FAILED — no image HTML produced (see warnings above)."
        )
        return 2

    m = re.search(r'src="([^"]+)"', html)
    logger.info("Self-test OK")
    logger.info("  CDN URL : %s", m.group(1) if m else "<not found>")
    logger.info("  HTML    : %s", html)
    return 0


def main() -> int:
    args = _parse_args()

    # Standalone image-path test — generate + upload one image, then exit.
    if args.selftest_image:
        return _run_selftest_image()

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

    # One-shot HF warm-up: if any site in this run will request a featured
    # image, pre-load the FLUX.1-schnell model once so the per-blog calls get
    # fast 200s instead of each paying the cold-start 503/load delay.
    featured_default = bool(defaults.get("featured_image", False))
    featured_any = featured_default or any(
        s.get("featured_image", featured_default) for s in sites
    )
    hf_token = os.environ.get("HF_API_TOKEN")
    if featured_any and hf_token:
        logger.info("Warming up Hugging Face FLUX.1-schnell model...")
        warm_up_hf_model(hf_token)

    logger.info("Publish method: %s", args.publish_method)

    results: list[tuple[str, bool, str]] = []
    total = len(sites)
    for idx, site in enumerate(sites):
        ok, info = run_one(site, defaults, publish_method=args.publish_method)
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
