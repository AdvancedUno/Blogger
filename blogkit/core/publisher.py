"""Blogger publishing — two transports behind one module.

1. Blogger v3 REST API (default), via OAuth2 refresh-token credentials.
2. Mail-to-Blogger SMTP (fallback for API 429 daily-quota days).

Required environment variables (provided via GitHub Secrets in CI):
    # API transport
    GOOGLE_CLIENT_ID       — OAuth client id (Google Cloud Console)
    GOOGLE_CLIENT_SECRET   — OAuth client secret
    GOOGLE_REFRESH_TOKEN   — Refresh token from a one-time local OAuth flow
    # Email transport
    SMTP_USER              — Gmail address used to send
    SMTP_PASSWORD          — Gmail App Password (NOT the account password)
    BLOGGER_SECRET_EMAIL   — the blog's Mail2Blogger address
"""
from __future__ import annotations

import logging
import os
import smtplib
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)


class BloggerPublishError(RuntimeError):
    """Raised when publishing to Blogger fails."""


class EmailPublishError(RuntimeError):
    """Raised when SMTP / mail-to-Blogger publishing fails."""


SCOPES = ["https://www.googleapis.com/auth/blogger"]
TOKEN_URI = "https://oauth2.googleapis.com/token"


# =====================================================================
# Blogger category labels
# ---------------------------------------------------------------------
# One clean, human-readable Blogger category per blog, keyed by the blog's
# slug (the stable per-blog identifier — NOT the rotating natural-language RSS
# query, which changes every run). This is the SINGLE source of truth for the
# `labels` array in the Posts.insert payload: the model is not allowed to
# invent tags, so categories stay consistent across the network (clean archive
# pages, predictable label URLs, no tag sprawl that dilutes topical authority).
# Add a row here when a new blog is added; an unmapped slug falls back to a
# Title-Cased version of the slug via ``category_for``.
# =====================================================================
CATEGORY_BY_SLUG: dict[str, str] = {
    # briefing (finance / markets)
    "b2b_payment_rails": "Payments",
    "corporate_treasury_tech": "Treasury Tech",
    "wealthtech_systems": "WealthTech",
    "institutional_digital_assets": "Digital Assets",
    "marketing_attribution_mmm": "Marketing Analytics",
    # op_ed (opinion / thesis)
    "programmatic_adtech_privacy": "AdTech Privacy",
    "enterprise_revops": "RevOps",
    "enterprise_insurtech": "InsurTech",
    "b2b_seo_content_ops": "Content Ops",
    "conversational_cx_automation": "CX Automation",
    # playbook (engineer how-to)
    "platform_engineering_idp": "Platform Engineering",
    "observability_sre": "Observability & SRE",
    "finops_cloud_cost": "FinOps",
    "api_management_integration": "API Management",
    "kubernetes_container_security": "Container Security",
    # deep_dive (investigation / security / frontier)
    "zero_trust_enterprise": "Zero Trust",
    "cyber_compliance_automation": "Cyber Compliance",
    "meddevice_cybersecurity": "MedDevice Security",
    "quantum_commercialization": "Quantum Computing",
    "autonomous_fleet_ops": "Autonomous Fleets",
    # explainer (teaching)
    "ai_infra_insider": "AI Infrastructure",
    "dataops_vector_dbs": "DataOps",
    "digital_health_interoperability": "Health Interoperability",
    "customer_data_platforms": "Customer Data Platforms",
    "industrial_edge_ai": "Edge AI",
    # buyers_guide (evaluation)
    "clinical_trial_tech": "Clinical Trials",
    "commercial_proptech": "PropTech",
    "legaltech_enterprise": "LegalTech",
    "supply_chain_visibility": "Supply Chain",
    "hr_tech_people_analytics": "HR Tech",
    # case_study (narrative field story)
    "field_service_management": "Field Service",
    "construction_tech": "Construction Tech",
    "hospitality_tech": "Hospitality Tech",
    "manufacturing_erp_mes": "Manufacturing ERP",
    # market_outlook (forward-looking sector)
    "smart_building_esg": "Smart Buildings",
    "grid_energy_storage": "Energy Storage",
    "ev_charging_infrastructure": "EV Charging",
    "carbon_accounting_esg": "Carbon Accounting",
    "agtech_precision_ag": "AgTech",
    "space_satellite_connectivity": "Satellite Connectivity",
}


def _titleize(slug: str) -> str:
    """Fallback label for an unmapped slug: underscores -> spaces, Title Case."""
    return " ".join(w.capitalize() for w in slug.replace("_", " ").split())


def category_for(slug: str) -> str:
    """The clean Blogger category for ``slug``.

    Returns the curated label from ``CATEGORY_BY_SLUG`` when present, else a
    Title-Cased fallback derived from the slug (e.g. "new_vertical" ->
    "New Vertical"). Empty/blank slug returns "" (caller applies no label).
    """
    slug = (slug or "").strip()
    if not slug:
        return ""
    return CATEGORY_BY_SLUG.get(slug) or _titleize(slug)


def _build_service():
    """Build a Blogger v3 service object from refresh-token credentials."""
    # Lazy import so the module is importable (and the pipeline unit-testable)
    # without the Google client libraries present.
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    client_id = os.environ.get("GOOGLE_CLIENT_ID")
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET")
    refresh_token = os.environ.get("GOOGLE_REFRESH_TOKEN")
    missing = [
        k for k, v in {
            "GOOGLE_CLIENT_ID": client_id,
            "GOOGLE_CLIENT_SECRET": client_secret,
            "GOOGLE_REFRESH_TOKEN": refresh_token,
        }.items() if not v
    ]
    if missing:
        raise BloggerPublishError(
            f"Missing required environment variables: {', '.join(missing)} — "
            "must be set in GitHub Secrets."
        )

    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri=TOKEN_URI,
        client_id=client_id,
        client_secret=client_secret,
        scopes=SCOPES,
    )
    # cache_discovery=False avoids disk writes on ephemeral runners.
    return build("blogger", "v3", credentials=creds, cache_discovery=False)


def publish_to_blogger(
    blog_id: str,
    title: str,
    html_content: str,
    tags: list[str] | None = None,
    is_draft: bool = False,
    search_description: str = "",
    slug: str = "",
    published: str = "",
) -> str:
    """Publish a single post via the Blogger v3 API and return its URL.

    Args:
        blog_id: Internal numeric Blogger blog id (e.g., "1234567890").
        title: Post title (plain text).
        html_content: Post body HTML.
        tags: Legacy label fallback, used ONLY when ``slug`` is empty. When a
            slug is given, the post's single category comes from
            ``category_for(slug)`` and these are ignored (the model is not
            allowed to invent the labels).
        slug: Blog slug. When set, the Blogger ``labels`` array is exactly one
            clean category from ``CATEGORY_BY_SLUG`` (Title-Cased slug for an
            unmapped blog) — see ``category_for``.
        is_draft: When True, save as draft (default False = publish live).
        published: Optional RFC 3339 timestamp for the post's visible publish
            time. Used to back-date posts within a window so the network's
            publish times are staggered rather than all identical (see
            ``core.cadence``). Must be in the past — a future value would make
            Blogger schedule the post as a draft instead of publishing it.
        search_description: Meta/search description for the post. Blogger's v3
            API does not officially expose this field, so it is attempted as
            ``searchDescription`` and silently dropped (with a retry) if the API
            rejects it — the post still publishes either way.

    Returns:
        Public URL of the published post.

    Raises:
        BloggerPublishError: For auth / API / network errors.
    """
    if not blog_id or blog_id.startswith("["):
        raise BloggerPublishError(
            f"blog_id is unset or a placeholder: {blog_id!r}"
        )
    if not title or not html_content:
        raise BloggerPublishError("Empty title or content cannot be published")

    from googleapiclient.errors import HttpError

    service = _build_service()

    body: dict = {
        "kind": "blogger#post",
        "title": title,
        "content": html_content,
    }
    # Labels: a single clean category from the slug mapping is the source of
    # truth. Only when no slug is supplied do we fall back to caller-provided
    # tags (legacy / direct callers). This keeps model-invented tags out of the
    # blog's category taxonomy.
    if slug:
        category = category_for(slug)
        if category:
            body["labels"] = [category]
    elif tags:
        body["labels"] = list(tags)
    if search_description:
        body["searchDescription"] = search_description
    if published:
        body["published"] = published

    def _insert(post_body: dict) -> dict:
        return (
            service.posts()
            .insert(blogId=blog_id, body=post_body, isDraft=is_draft)
            .execute()
        )

    try:
        try:
            result = _insert(body)
        except HttpError as e:
            # Blogger v3 can 400 on the optional fields: the unofficial
            # searchDescription, or (on some blogs/accounts) a `published`
            # timestamp on insert. Drop BOTH and retry once so the core
            # title/content/labels still publish. Only retry when at least one
            # optional field was actually present (otherwise the 400 is real).
            status = getattr(e.resp, "status", None)
            if (search_description or published) and str(status) == "400":
                logger.warning(
                    "Blogger rejected an optional field (HTTP 400) — retrying "
                    "without searchDescription/published for blog_id=%s", blog_id,
                )
                body.pop("searchDescription", None)
                body.pop("published", None)
                result = _insert(body)
            else:
                raise
    except HttpError as e:
        status = getattr(e.resp, "status", "?")
        raise BloggerPublishError(
            f"Blogger API HTTP {status}: {e}"
        ) from e
    except Exception as e:
        raise BloggerPublishError(
            f"Unexpected error publishing to Blogger: {e}"
        ) from e

    post_url = result.get("url") or ""
    post_id = result.get("id") or ""
    logger.info(
        "Published to Blogger — blog_id=%s post_id=%s url=%s",
        blog_id, post_id, post_url,
    )
    return post_url


# =====================================================================
# Email transport (Mail2Blogger SMTP) — fallback for API 429 quota days
# =====================================================================
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_POST_SEND_SLEEP = 10   # avoid Gmail spam-filter rate flags between sends


def publish_via_email(
    title: str,
    html_content: str,
    *,
    recipient: str | None = None,
) -> str:
    """Publish a post by emailing it to the blog's Mail2Blogger address.

    Args:
        title: Post title (email Subject).
        html_content: Post body HTML (email body).
        recipient: Mail2Blogger address. Defaults to the BLOGGER_SECRET_EMAIL
            env var when not given (lets a profile override it per blog).

    Returns the recipient on success; raises EmailPublishError on failure.
    """
    user = os.environ.get("SMTP_USER")
    password = os.environ.get("SMTP_PASSWORD")
    recipient = recipient or os.environ.get("BLOGGER_SECRET_EMAIL")
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
    # Narrow Optional[str] -> str now that presence is guaranteed.
    assert user and password and recipient
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
