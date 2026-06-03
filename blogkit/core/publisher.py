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

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)


class BloggerPublishError(RuntimeError):
    """Raised when publishing to Blogger fails."""


class EmailPublishError(RuntimeError):
    """Raised when SMTP / mail-to-Blogger publishing fails."""


SCOPES = ["https://www.googleapis.com/auth/blogger"]
TOKEN_URI = "https://oauth2.googleapis.com/token"


def _build_service():
    """Build a Blogger v3 service object from refresh-token credentials."""
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
) -> str:
    """Publish a single post via the Blogger v3 API and return its URL.

    Args:
        blog_id: Internal numeric Blogger blog id (e.g., "1234567890").
        title: Post title (plain text).
        html_content: Post body HTML.
        tags: List of labels to attach to the post.
        is_draft: When True, save as draft (default False = publish live).

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

    service = _build_service()

    body: dict = {
        "kind": "blogger#post",
        "title": title,
        "content": html_content,
    }
    if tags:
        body["labels"] = list(tags)

    try:
        result = (
            service.posts()
            .insert(blogId=blog_id, body=body, isDraft=is_draft)
            .execute()
        )
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
