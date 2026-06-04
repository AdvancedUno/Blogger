"""Cross-blog de-duplication ledger.

20 blogs drawing from overlapping B2B news pools risk near-duplicate content —
which Google's "scaled content" / duplicate systems penalize and which hurts
AdSense approval. This module keeps a small persisted ledger of which source
articles and titles each blog has already used, so:

  * the same source article is not reused network-wide within a recency window,
  * near-duplicate titles are detected (soft warning).

The ledger is a JSON file in the image-hosting GitHub repo (reusing
ASSETS_REPO_PAT). Everything is best-effort: if the store is unavailable, the
ledger is simply empty and the pipeline proceeds normally (no dedup, no crash).

The pure ``Ledger`` logic is fully unit-testable without any network.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

import requests

from blogkit.core.imager import ASSETS_REPO, GITHUB_CONTENTS_API, GITHUB_UPLOAD_TIMEOUT

logger = logging.getLogger(__name__)

LEDGER_PATH = "ledger/dedup.json"
LINK_RECENCY_DAYS = 14      # don't reuse a source article within this window
TITLE_RECENCY_DAYS = 30     # window for near-duplicate title checks
LEDGER_MAX_AGE_DAYS = 120   # prune entries older than this on save
_TITLE_SIMILARITY = 0.6     # Jaccard token overlap that counts as "too similar"


def link_hash(url: str) -> str:
    """Stable short hash of a source URL (ignores fragments/trailing slashes)."""
    norm = (url or "").split("#", 1)[0].rstrip("/").strip().lower()
    return hashlib.sha1(norm.encode("utf-8")).hexdigest()[:16]


def normalize_title(title: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", (title or "").lower())).strip()


def _title_tokens(title: str) -> set[str]:
    return {t for t in normalize_title(title).split() if len(t) > 2}


def titles_similar(a: str, b: str) -> bool:
    ta, tb = _title_tokens(a), _title_tokens(b)
    if not ta or not tb:
        return False
    overlap = len(ta & tb) / len(ta | tb)
    return overlap >= _TITLE_SIMILARITY


def _today() -> datetime:
    return datetime.now(timezone.utc)


def _days_ago(iso_date: str) -> float:
    try:
        d = datetime.fromisoformat(iso_date)
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
    except Exception:
        return 1e9
    return (_today() - d).total_seconds() / 86400.0


@dataclass
class Ledger:
    """In-memory record of used (source link, title) per blog. Pure logic."""

    entries: list[dict] = field(default_factory=list)

    def used_link_hashes(self, days: int = LINK_RECENCY_DAYS) -> set[str]:
        out: set[str] = set()
        for e in self.entries:
            if _days_ago(e.get("ts", "")) <= days:
                out.update(e.get("links", []))
        return out

    def recent_titles(self, days: int = TITLE_RECENCY_DAYS) -> list[str]:
        return [e["title"] for e in self.entries
                if e.get("title") and _days_ago(e.get("ts", "")) <= days]

    def fresh_links(self, links: list[str], days: int = LINK_RECENCY_DAYS) -> list[str]:
        """Subset of `links` (raw URLs) not used network-wide within `days`."""
        used = self.used_link_hashes(days)
        return [url for url in links if link_hash(url) not in used]

    def title_clashes(self, title: str, days: int = TITLE_RECENCY_DAYS) -> str | None:
        for prior in self.recent_titles(days):
            if titles_similar(title, prior):
                return prior
        return None

    def record(self, *, slug: str, keyword: str, title: str, links: list[str],
               url: str = "") -> None:
        self.entries.append({
            "ts": _today().isoformat(),
            "slug": slug,
            "keyword": keyword,
            "title": title,
            "url": url,
            "links": [link_hash(u) for u in links],
        })

    def recent_posts(self, slug: str, *, days: int = 90,
                     limit: int = 5) -> list[tuple[str, str]]:
        """(title, url) for this blog's recent posts that have a URL, newest
        first — for internal "related posts" linking."""
        rows = [e for e in self.entries
                if e.get("slug") == slug and e.get("url")
                and _days_ago(e.get("ts", "")) <= days]
        rows.sort(key=lambda e: e.get("ts", ""), reverse=True)
        return [(e["title"], e["url"]) for e in rows[:limit]]

    def prune(self, max_age_days: int = LEDGER_MAX_AGE_DAYS) -> None:
        self.entries = [e for e in self.entries if _days_ago(e.get("ts", "")) <= max_age_days]

    def to_json(self) -> str:
        return json.dumps({"entries": self.entries}, ensure_ascii=False, indent=0)

    @classmethod
    def from_json(cls, text: str) -> Ledger:
        try:
            data = json.loads(text)
            entries = data.get("entries", []) if isinstance(data, dict) else []
        except Exception:
            entries = []
        return cls(entries=[e for e in entries if isinstance(e, dict)])


class GitHubLedgerStore:
    """Loads/saves the Ledger as a JSON file in the assets repo. Best-effort."""

    def __init__(self, path: str = LEDGER_PATH) -> None:
        self.path = path
        self._sha: str | None = None
        self._pat = os.environ.get("ASSETS_REPO_PAT")

    def _url(self) -> str:
        return GITHUB_CONTENTS_API.format(repo=ASSETS_REPO, path=self.path)

    def load(self) -> Ledger:
        if not self._pat:
            logger.info("Dedup ledger disabled (no ASSETS_REPO_PAT)")
            return Ledger()
        try:
            r = requests.get(
                self._url(),
                headers={"Authorization": f"Bearer {self._pat}",
                         "Accept": "application/vnd.github+json"},
                timeout=GITHUB_UPLOAD_TIMEOUT,
            )
            if r.status_code == 404:
                return Ledger()
            r.raise_for_status()
            payload = r.json()
            self._sha = payload.get("sha")
            content = base64.b64decode(payload.get("content", "")).decode("utf-8")
            ledger = Ledger.from_json(content)
            logger.info("Dedup ledger loaded — %d entries", len(ledger.entries))
            return ledger
        except Exception as e:
            logger.warning("Dedup ledger load failed (%s) — proceeding without it", e)
            return Ledger()

    def save(self, ledger: Ledger) -> None:
        if not self._pat:
            return
        try:
            ledger.prune()
            body = {
                "message": "Update dedup ledger",
                "content": base64.b64encode(ledger.to_json().encode("utf-8")).decode("ascii"),
            }
            if self._sha:
                body["sha"] = self._sha
            r = requests.put(
                self._url(),
                headers={"Authorization": f"Bearer {self._pat}",
                         "Accept": "application/vnd.github+json",
                         "X-GitHub-Api-Version": "2022-11-28"},
                json=body,
                timeout=GITHUB_UPLOAD_TIMEOUT,
            )
            r.raise_for_status()
            self._sha = r.json().get("commit", {}).get("sha") or self._sha
            logger.info("Dedup ledger saved — %d entries", len(ledger.entries))
        except Exception as e:
            logger.warning("Dedup ledger save failed (%s) — continuing", e)
