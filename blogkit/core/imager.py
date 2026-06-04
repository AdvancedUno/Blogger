"""Featured image: generate (Hugging Face FLUX.1-schnell) -> host (GitHub
Contents API) -> embed an immutable jsDelivr CDN URL.

A real https URL (not a base64 data: URI) is required so Blogger's homepage
thumbnail extractor and JetTheme's JS recognize the featured image — and it
keeps post bodies light (AdSense / page-speed). Any failure returns None so the
caller can publish text-only.

The per-post style is picked deterministically from the blog's style pool
(``BlogProfile.style_pool()``) by hashing the title, so each post is distinct
and on-brand for that blog. Engine: hf-inference provider via router.huggingface.co
(SDXL left the free tier; the legacy api-inference host is dead). The HF token
must be a fine-grained token with "Inference Providers" permission.

Env: HF_API_TOKEN (generation), ASSETS_REPO_PAT (contents:write on ASSETS_REPO).
"""

from __future__ import annotations

import base64
import hashlib
import logging
import os
import re
import time
from datetime import datetime, timezone
from typing import Any

import requests

from blogkit.core.styles import STYLE_PRESETS

logger = logging.getLogger(__name__)

# --- Hugging Face image generation -----------------------------------------
HF_IMAGE_ENDPOINT = (
    "https://router.huggingface.co/hf-inference/models/"
    "black-forest-labs/FLUX.1-schnell"
)
HF_IMAGE_WIDTH = 1024           # 16:9 landscape (multiples of 16 for FLUX)
HF_IMAGE_HEIGHT = 576
HF_MAX_RETRIES = 3              # free model is often cold (503 while loading)
HF_DEFAULT_COLD_WAIT = 20.0     # used when the 503 body has no estimated_time
HF_COLD_WAIT_BUFFER = 5.0       # extra seconds on top of estimated_time
HF_REQUEST_TIMEOUT = 120.0      # cold load + generation can be slow

# --- Image hosting (GitHub Contents API -> jsDelivr CDN) -------------------
ASSETS_REPO = "AdvancedUno/blog-assets"
GITHUB_CONTENTS_API = "https://api.github.com/repos/{repo}/contents/{path}"
JSDELIVR_URL = "https://cdn.jsdelivr.net/gh/{repo}@{sha}/{path}"
GITHUB_UPLOAD_TIMEOUT = 30.0

WARM_UP_PROMPT = "warm up the model, a simple blue cube"


def _slugify(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return s[:60].strip("-") or "post"


def _build_image_prompt(title: str, styles: list[str]) -> tuple[str, int]:
    """Creative, on-theme prompt + deterministic seed.

    Same title -> same prompt/seed (reproducible); the style is chosen from the
    blog's pool by hash, so different posts on the same blog still vary.
    """
    seed = int(hashlib.sha256(title.encode("utf-8")).hexdigest(), 16) % (2**32)
    pool = styles or list(STYLE_PRESETS.values())
    style = pool[seed % len(pool)]
    prompt = (
        f'A striking editorial cover image that visually represents the concept '
        f'of "{title}". {style}. Strong single focal subject, clean composition, '
        f'no text, no words, no letters, no watermark, no logos.'
    )
    return prompt, seed


def _upload_image_to_github(png_bytes: bytes, title: str) -> str:
    """PUT the PNG to the assets repo and return an immutable jsDelivr URL."""
    pat = os.environ.get("ASSETS_REPO_PAT")
    if not pat:
        raise ValueError("no ASSETS_REPO_PAT available for image upload")

    now = datetime.now(timezone.utc)
    path = f"images/{now:%Y}/{now:%m}/{_slugify(title)}-{now:%Y%m%d%H%M%S}.png"
    payload = {
        "message": f"Add featured image: {title[:72]}",
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
    sha = resp.json()["commit"]["sha"]
    return JSDELIVR_URL.format(repo=ASSETS_REPO, sha=sha, path=path)


def _hf_generate_png(prompt: str, seed: int, hf_token: str) -> bytes | None:
    """POST to the HF endpoint, honoring the cold-model 503 retry. Returns the
    raw PNG bytes, or None if the model is still loading after all retries."""
    headers = {"Authorization": f"Bearer {hf_token}"}
    payload: dict[str, Any] = {
        "inputs": prompt,
        "parameters": {"width": HF_IMAGE_WIDTH, "height": HF_IMAGE_HEIGHT, "seed": seed},
    }
    for attempt in range(HF_MAX_RETRIES):
        resp = requests.post(
            HF_IMAGE_ENDPOINT, headers=headers, json=payload, timeout=HF_REQUEST_TIMEOUT
        )
        if resp.status_code == 503:
            try:
                wait = float(resp.json().get("estimated_time", HF_DEFAULT_COLD_WAIT))
            except Exception:
                wait = HF_DEFAULT_COLD_WAIT
            wait += HF_COLD_WAIT_BUFFER
            logger.warning(
                "HF model loading (503), attempt %d/%d — sleeping %.0fs",
                attempt + 1, HF_MAX_RETRIES, wait,
            )
            time.sleep(wait)
            continue
        resp.raise_for_status()
        if not resp.content:
            raise ValueError("empty image body from Hugging Face")
        return resp.content
    return None


def build_featured_image_html(
    title: str,
    hf_token: str | None,
    styles: list[str] | None = None,
) -> str | None:
    """Generate a creative on-theme image, host it, and return a JetTheme <div>
    with a jsDelivr CDN <img src>. Best-effort: None on any failure.

    Args:
        title: Post title (drives prompt + seed).
        hf_token: HF token with Inference Providers permission.
        styles: The blog's resolved style-preset pool (``profile.style_pool()``).
            None/empty => the full catalog.
    """
    try:
        if not hf_token:
            raise ValueError("no Hugging Face token available (HF_API_TOKEN)")

        prompt, seed = _build_image_prompt(title, styles or [])
        png_bytes = _hf_generate_png(prompt, seed, hf_token)
        if png_bytes is None:
            logger.warning(
                "HF image still loading after %d retries — publishing text-only",
                HF_MAX_RETRIES,
            )
            return None
        logger.info("HF image generated — %d KB (seed=%d)", len(png_bytes) // 1024, seed)

        cdn_url = _upload_image_to_github(png_bytes, title)
        logger.info("Featured image hosted -> %s", cdn_url)

        alt = title.replace('"', "&quot;")
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


def warm_up_hf_model(hf_token: str | None) -> None:
    """Pre-load the model once before a batch so per-blog calls get fast 200s
    instead of each paying the cold-start delay. Never raises."""
    if not hf_token:
        logger.warning("HF warm-up skipped — no HF_API_TOKEN")
        return
    try:
        png = _hf_generate_png(WARM_UP_PROMPT, seed=0, hf_token=hf_token)
        if png is not None:
            logger.info("HF warm-up: model is hot")
        else:
            logger.warning(
                "HF warm-up: still loading after %d retries — continuing anyway",
                HF_MAX_RETRIES,
            )
    except Exception as e:
        logger.warning("HF warm-up failed (%s) — continuing anyway", e)
