"""Run digest notifications to a webhook (Discord/Slack-compatible).

So a silent failure across 20 blogs doesn't go unnoticed. Best-effort: never
raises, no-ops when RUN_WEBHOOK_URL is unset.
"""

from __future__ import annotations

import logging
import os

import requests

logger = logging.getLogger(__name__)

WEBHOOK_TIMEOUT = 15.0


def format_digest(results: list[tuple[str, bool, str]], *, dry_run: bool = False) -> str:
    """results: list of (slug, ok, info)."""
    ok = sum(1 for _, k, _ in results if k)
    tag = "(dry-run) " if dry_run else ""
    lines = [f"blogkit run {tag}— {ok}/{len(results)} OK"]
    for slug, k, info in results:
        lines.append(f"{'✅' if k else '❌'} {slug}: {info}")
    return "\n".join(lines)


def send_digest(text: str, webhook_url: str | None = None) -> bool:
    """POST the digest. Payload carries both 'content' (Discord) and 'text'
    (Slack) so one URL works for either. Returns True on success."""
    url = webhook_url or os.environ.get("RUN_WEBHOOK_URL")
    if not url:
        return False
    try:
        r = requests.post(url, json={"content": text, "text": text}, timeout=WEBHOOK_TIMEOUT)
        r.raise_for_status()
        return True
    except Exception as e:
        logger.warning("Run digest webhook failed (%s)", e)
        return False
