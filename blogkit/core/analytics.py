"""Search Console feedback loop.

Closes the loop: what actually earns impressions/clicks in Google should
influence which topics each blog writes about next. We pull each blog's top
queries from the Search Console API and bias the keyword roulette toward the
themes that are already performing — while keeping randomness (and the de-dup
guard) so the blog still explores.

Best-effort: the pure ranking logic is unit-tested; the API call lazy-imports
the Google libs and returns [] on any failure (missing creds, wrong scope,
unverified property), so a run is never blocked.

Auth: needs an OAuth refresh token with the
``https://www.googleapis.com/auth/webmasters.readonly`` scope. Reads
GSC_CLIENT_ID/GSC_CLIENT_SECRET/GSC_REFRESH_TOKEN, falling back to the
GOOGLE_* Blogger creds (which only work if that token was consented with the
webmasters scope too).
"""

from __future__ import annotations

import logging
import os
import random
import re
from datetime import date, timedelta

logger = logging.getLogger(__name__)

GSC_SCOPE = "https://www.googleapis.com/auth/webmasters.readonly"
TOKEN_URI = "https://oauth2.googleapis.com/token"


def _tokens(s: str) -> set[str]:
    return {t for t in re.sub(r"[^a-z0-9 ]+", " ", (s or "").lower()).split() if len(t) > 2}


def score_queries(rss_queries: list[str], gsc_rows: list[dict]) -> list[tuple[str, float]]:
    """Score each configured keyword by token-overlap with performing GSC
    queries, weighted by clicks (5x) + impressions. Pure / testable."""
    scored: list[tuple[str, float]] = []
    for q in rss_queries:
        qt = _tokens(q)
        total = 0.0
        for row in gsc_rows:
            rt = _tokens(row.get("query", ""))
            if not qt or not rt:
                continue
            overlap = len(qt & rt) / len(qt | rt)
            if overlap > 0:
                weight = row.get("clicks", 0) * 5 + row.get("impressions", 0)
                total += overlap * weight
        scored.append((q, total))
    return scored


def prioritize_queries(
    rss_queries: list[str],
    gsc_rows: list[dict],
    *,
    boost: int = 3,
    rng: random.Random | None = None,
) -> list[str]:
    """Return the keyword list with the top-performing themes moved to the
    front (so the fetch loop tries them first) and the rest shuffled for
    variety. With no usable signals this is just a shuffle."""
    rng = rng or random.Random()
    ranked = [q for q, s in sorted(score_queries(rss_queries, gsc_rows),
                                   key=lambda x: x[1], reverse=True) if s > 0]
    top = ranked[:boost]
    rest = [q for q in rss_queries if q not in top]
    rng.shuffle(rest)
    return top + rest


def fetch_top_queries(site_url: str, *, days: int = 28, row_limit: int = 50) -> list[dict]:
    """Best-effort: top Search Console queries for `site_url` over the last
    `days`. Returns [] on any failure so callers can proceed without a boost."""
    client_id = os.environ.get("GSC_CLIENT_ID") or os.environ.get("GOOGLE_CLIENT_ID")
    client_secret = os.environ.get("GSC_CLIENT_SECRET") or os.environ.get("GOOGLE_CLIENT_SECRET")
    refresh_token = os.environ.get("GSC_REFRESH_TOKEN") or os.environ.get("GOOGLE_REFRESH_TOKEN")
    if not (client_id and client_secret and refresh_token and site_url):
        return []
    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build

        creds = Credentials(
            token=None, refresh_token=refresh_token, token_uri=TOKEN_URI,
            client_id=client_id, client_secret=client_secret, scopes=[GSC_SCOPE],
        )
        service = build("searchconsole", "v1", credentials=creds, cache_discovery=False)
        end = date.today()
        start = end - timedelta(days=days)
        resp = service.searchanalytics().query(
            siteUrl=site_url,
            body={
                "startDate": start.isoformat(),
                "endDate": end.isoformat(),
                "dimensions": ["query"],
                "rowLimit": row_limit,
            },
        ).execute()
        rows = [
            {
                "query": (r.get("keys") or [""])[0],
                "clicks": r.get("clicks", 0),
                "impressions": r.get("impressions", 0),
            }
            for r in resp.get("rows", [])
        ]
        logger.info("Search Console: %d query rows for %s", len(rows), site_url)
        return rows
    except Exception as e:
        logger.warning("Search Console fetch failed for %s (%s) — no boost", site_url, e)
        return []
