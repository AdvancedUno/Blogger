"""SMTP-based publishing via Blogger's Mail-to-Blogger feature.

Blogger lets each blog accept posts by email at a secret address configured
under Settings -> Email -> "Posting using email". Anything sent to that
address gets published as a post, with the email Subject becoming the post
title and the email body becoming the post HTML body.

This module ships posts via Gmail's SMTP server, bypassing the Blogger v3
REST API's strict daily write quota (the source of recurring 429 errors).

Required environment variables:
    SENDER_EMAIL        The Gmail address you're sending from.
    GMAIL_APP_PASSWORD  A Gmail "App Password" specifically generated for
                        this script -- NOT your normal Gmail password.
                        Generate one at https://myaccount.google.com/apppasswords
                        (requires 2-Step Verification on the Gmail account).
"""
from __future__ import annotations

import logging
import os
import smtplib
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587   # STARTTLS — preferred over 465's implicit SSL
SMTP_TIMEOUT = 30  # seconds


class MailPublishError(RuntimeError):
    """Raised when an SMTP send fails or required env vars are missing."""


def publish_via_email(
    target_email: str,
    post_title: str,
    html_content: str,
) -> str:
    """Send an HTML post to a Blogger Mail-to-Blogger secret address.

    Args:
        target_email: The blog's secret_email (e.g. "user.secret@blogger.com").
            Each post emailed to this address publishes immediately on that
            specific blog.
        post_title: Becomes both the email Subject and the Blogger post title.
        html_content: The post body, as HTML. Blogger renders this directly.

    Returns:
        The target email (for logging convenience).

    Raises:
        MailPublishError: For missing credentials, auth failures, SMTP
            protocol errors, or network errors.
    """
    sender_email = os.getenv("SENDER_EMAIL")
    app_password = os.getenv("GMAIL_APP_PASSWORD")

    if not sender_email:
        raise MailPublishError(
            "SENDER_EMAIL env var is missing — set it to the Gmail address "
            "the script should send from."
        )
    if not app_password:
        raise MailPublishError(
            "GMAIL_APP_PASSWORD env var is missing — generate an app "
            "password at https://myaccount.google.com/apppasswords "
            "(requires 2-Step Verification on the Gmail account)."
        )
    if not target_email:
        raise MailPublishError(
            "target_email is empty — set `secret_email` for this blog in "
            "config.yaml."
        )
    if not post_title or not html_content:
        raise MailPublishError("Cannot send an empty title or body.")

    # MIME alternative carries the HTML payload Blogger consumes. Could
    # add a plain-text part for fallback, but Blogger ignores it.
    msg = MIMEMultipart("alternative")
    msg["Subject"] = post_title
    msg["From"] = sender_email
    msg["To"] = target_email
    msg.attach(MIMEText(html_content, "html", "utf-8"))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=SMTP_TIMEOUT) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.ehlo()
            smtp.login(sender_email, app_password)
            smtp.send_message(msg)
    except smtplib.SMTPAuthenticationError as e:
        raise MailPublishError(
            f"SMTP authentication failed — check SENDER_EMAIL and "
            f"GMAIL_APP_PASSWORD: {e}"
        ) from e
    except smtplib.SMTPException as e:
        raise MailPublishError(f"SMTP protocol error: {e}") from e
    except (OSError, TimeoutError) as e:
        raise MailPublishError(
            f"Network error connecting to {SMTP_HOST}:{SMTP_PORT}: {e}"
        ) from e

    logger.info(
        "Email sent: %s -> %s (%d chars HTML)",
        sender_email, target_email, len(html_content),
    )
    return target_email
