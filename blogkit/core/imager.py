"""Featured image: generate -> host (GitHub Contents API) -> embed an
immutable jsDelivr CDN URL.

A real https URL (not a base64 data: URI) is required so Blogger's homepage
thumbnail extractor and JetTheme's JS recognize the featured image — and it
keeps post bodies light (AdSense / page-speed). Any failure returns None so the
caller can publish text-only.

The per-post style is picked deterministically from the blog's style pool
(``BlogProfile.style_pool()``) by hashing the title, so each post is distinct
and on-brand for that blog.

GENERATION ENGINE — pluggable via the ``IMAGE_PROVIDER`` env var:

  * ``hf`` (default) — Hugging Face FLUX.1-schnell via router.huggingface.co.
    The HF token must be a fine-grained token with "Inference Providers"
    permission. Free tier, but rate-limited.
  * ``vertex`` — Google Cloud Vertex AI Imagen (bills against GCP credits).
    Needs a GCP project with the Vertex AI API enabled. No cold-start, higher
    quality, paid. Auth is keyless-first (see below).

HOSTING is identical for both: the PNG is committed to ASSETS_REPO and served
from jsDelivr.

Vertex auth (no long-lived key required — works with "Secure by Default" orgs
that block service-account JSON keys):
  * Locally:  `gcloud auth application-default login` (ADC), set GCP_PROJECT.
  * In CI:    Workload Identity Federation via the google-github-actions/auth
              action, which exports GOOGLE_APPLICATION_CREDENTIALS +
              GOOGLE_CLOUD_PROJECT. The code picks these up automatically.
  * Optional: GCP_SA_KEY (inline service-account JSON) if your org allows keys.

Env:
  IMAGE_PROVIDER         "hf" (default) | "vertex"
  HF_API_TOKEN           hf provider: generation token
  GCP_PROJECT            vertex: project id (else GOOGLE_CLOUD_PROJECT / creds)
  VERTEX_LOCATION        vertex: region (default us-central1)
  VERTEX_IMAGE_MODEL     vertex: model id (default imagen-4.0-fast-generate-001)
  GCP_SA_KEY             vertex (optional): service-account JSON as a string
  GOOGLE_APPLICATION_CREDENTIALS  vertex (optional): path to an ADC/WIF file
  ASSETS_REPO_PAT        both: contents:write on ASSETS_REPO (hosting)
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import re
import time
from datetime import datetime, timezone
from typing import Any

import requests

from blogkit.core.styles import STYLE_PRESETS

logger = logging.getLogger(__name__)


def active_provider() -> str:
    """The configured image-generation provider ('hf' default, or 'vertex')."""
    return (os.environ.get("IMAGE_PROVIDER") or "hf").strip().lower()


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

# --- Vertex AI Imagen image generation -------------------------------------
VERTEX_LOCATION_DEFAULT = "us-central1"
# imagen-4.0-fast-generate-001 is the cheapest Imagen 4 tier — the sensible
# default for a high-volume blog network. Override with VERTEX_IMAGE_MODEL
# (e.g. imagen-4.0-generate-001 / imagen-4.0-ultra-generate-001).
VERTEX_IMAGE_MODEL_DEFAULT = "imagen-4.0-fast-generate-001"
VERTEX_ASPECT_RATIO = "16:9"
VERTEX_REQUEST_TIMEOUT = 120.0
VERTEX_SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]
# Imagen seeds are uint32, but reproducible seeds require the SynthID watermark
# to be disabled (the two are mutually exclusive in the API).
_VERTEX_SEED_MOD = 2**31

# --- Image hosting (GitHub Contents API -> jsDelivr CDN) -------------------
ASSETS_REPO = "advancedunolee/blog-assets"
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


def _resolve_gcp_project(fallback: str = "") -> str:
    """The GCP project id from env, else ``fallback``.

    Checks ``GCP_PROJECT`` then ``GOOGLE_CLOUD_PROJECT`` (the latter is what
    ``gcloud`` and the ``google-github-actions/auth`` action export), so the
    keyless / Workload Identity path needs no explicit project wiring.
    """
    return (
        (os.environ.get("GCP_PROJECT") or "").strip()
        or (os.environ.get("GOOGLE_CLOUD_PROJECT") or "").strip()
        or (fallback or "").strip()
    )


def _vertex_config() -> tuple[str, str, str]:
    """(project, location, model) for Vertex from env, with sane defaults.

    The project falls back to "" here; the caller resolves it from the
    credentials' own project when no env project is set.
    """
    location = (os.environ.get("VERTEX_LOCATION") or "").strip() or VERTEX_LOCATION_DEFAULT
    model = (os.environ.get("VERTEX_IMAGE_MODEL") or "").strip() or VERTEX_IMAGE_MODEL_DEFAULT
    return _resolve_gcp_project(), location, model


def _vertex_credentials() -> tuple[Any, str]:
    """Build Google credentials + resolve the project id.

    Three auth shapes, in priority order:
      1. Inline service-account JSON in ``GCP_SA_KEY`` (key-based).
      2. Application Default Credentials — covers both keyless paths:
         ``gcloud auth application-default login`` locally, and Workload
         Identity Federation in CI (the ``google-github-actions/auth`` action
         writes an external-account credential file and points
         ``GOOGLE_APPLICATION_CREDENTIALS`` at it). No long-lived key needed.
    Returns (credentials, project_id).
    """
    raw = os.environ.get("GCP_SA_KEY")
    if raw:
        from google.oauth2 import service_account

        info = json.loads(raw)
        creds = service_account.Credentials.from_service_account_info(
            info, scopes=VERTEX_SCOPES
        )
        return creds, info.get("project_id", "")

    import google.auth

    creds, project = google.auth.default(scopes=VERTEX_SCOPES)
    return creds, (project or "")


def _vertex_access_token() -> tuple[str, str]:
    """A fresh OAuth2 access token + the resolved project id."""
    from google.auth.transport.requests import Request

    creds, creds_project = _vertex_credentials()
    creds.refresh(Request())
    project = _resolve_gcp_project(creds_project)
    if not project:
        raise ValueError(
            "no GCP project id — set GCP_PROJECT, or use credentials (service "
            "account / ADC) that carry a project"
        )
    return creds.token, project


def _vertex_endpoint(project: str, location: str, model: str) -> str:
    return (
        f"https://{location}-aiplatform.googleapis.com/v1/projects/{project}"
        f"/locations/{location}/publishers/google/models/{model}:predict"
    )


def _vertex_generate_png(prompt: str, seed: int) -> bytes | None:
    """Generate one PNG via Vertex AI Imagen. Returns bytes, or None when the
    response carries no image (e.g. a safety filter blocked it)."""
    token, project = _vertex_access_token()
    _, location, model = _vertex_config()
    endpoint = _vertex_endpoint(project, location, model)
    payload: dict[str, Any] = {
        "instances": [{"prompt": prompt}],
        "parameters": {
            "sampleCount": 1,
            "aspectRatio": VERTEX_ASPECT_RATIO,
            "seed": seed % _VERTEX_SEED_MOD,
            # Reproducible seeds require the SynthID watermark off.
            "addWatermark": False,
            "personGeneration": "allow_adult",
        },
    }
    resp = requests.post(
        endpoint,
        headers={"Authorization": f"Bearer {token}",
                 "Content-Type": "application/json"},
        json=payload,
        timeout=VERTEX_REQUEST_TIMEOUT,
    )
    resp.raise_for_status()
    preds = resp.json().get("predictions", []) or []
    if not preds:
        logger.warning("Vertex Imagen returned no predictions — text-only")
        return None
    b64 = preds[0].get("bytesBase64Encoded")
    if not b64:
        reason = preds[0].get("raiFilteredReason") or "no image bytes in response"
        logger.warning("Vertex Imagen produced no image (%s) — text-only", reason)
        return None
    return base64.b64decode(b64)


def _generate_png(prompt: str, seed: int) -> bytes | None:
    """Dispatch to the configured provider. Returns PNG bytes or None."""
    provider = active_provider()
    if provider == "vertex":
        return _vertex_generate_png(prompt, seed)
    hf_token = os.environ.get("HF_API_TOKEN")
    if not hf_token:
        raise ValueError("no Hugging Face token available (HF_API_TOKEN)")
    png = _hf_generate_png(prompt, seed, hf_token)
    if png is None:
        logger.warning(
            "HF image still loading after %d retries — publishing text-only",
            HF_MAX_RETRIES,
        )
    return png


def build_featured_image(
    title: str,
    styles: list[str] | None = None,
) -> tuple[str, str] | None:
    """Generate a creative on-theme image, host it, and return
    ``(div_html, cdn_url)`` — the JetTheme <div> with a jsDelivr CDN <img src>,
    plus the raw CDN URL (so callers can also feed it into JSON-LD ``image``).
    Best-effort: None on any failure.

    The generation engine is chosen by the IMAGE_PROVIDER env var (hf default,
    or vertex). Hosting (GitHub -> jsDelivr) is identical either way.

    Args:
        title: Post title (drives prompt + seed).
        styles: The blog's resolved style-preset pool (``profile.style_pool()``).
            None/empty => the full catalog.
    """
    try:
        prompt, seed = _build_image_prompt(title, styles or [])
        png_bytes = _generate_png(prompt, seed)
        if png_bytes is None:
            return None
        logger.info(
            "Image generated via %s — %d KB (seed=%d)",
            active_provider(), len(png_bytes) // 1024, seed,
        )

        cdn_url = _upload_image_to_github(png_bytes, title)
        logger.info("Featured image hosted -> %s", cdn_url)

        alt = title.replace('"', "&quot;")
        div = (
            '<div class="mb-5">'
            f'<img src="{cdn_url}" '
            f'class="img-fluid rounded shadow-sm w-100" alt="{alt}" />'
            '</div>'
        )
        return div, cdn_url
    except Exception as e:
        logger.warning(
            "Featured image generation/upload failed (%s) — publishing "
            "text-only", e,
        )
        return None


def build_featured_image_html(
    title: str,
    styles: list[str] | None = None,
) -> str | None:
    """The featured-image <div> HTML only (or None). Thin wrapper over
    ``build_featured_image`` for callers that don't need the raw CDN URL."""
    result = build_featured_image(title, styles)
    return result[0] if result else None


def warm_up_image_model() -> None:
    """Pre-load the HF model once before a batch so per-blog calls get fast
    200s instead of each paying the cold-start delay. Never raises.

    Vertex AI has no cold-start, so this is a no-op for the vertex provider.
    """
    if active_provider() == "vertex":
        logger.info("Vertex provider — no warm-up needed")
        return
    hf_token = os.environ.get("HF_API_TOKEN")
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
