"""On-page engagement + SEO scaffolding applied to the generated HTML.

Pure HTML transforms (no network, fully testable):
  * ``add_toc``            — heading anchors + a clickable Table of Contents
                             (Google sitelinks eligibility + dwell time).
  * ``reading_time_badge`` — "N min read" badge.
  * ``related_posts_html`` — internal "Related from this blog" links (crawl
                             depth + session depth, a strong ranking signal).
"""

from __future__ import annotations

import html
import re

from blogkit.core.charts import strip_chart_blocks

_TAG_RE = re.compile(r"<[^>]+>")
_H2_RE = re.compile(r"<h2([^>]*)>(.*?)</h2>", re.IGNORECASE | re.DOTALL)
_ID_RE = re.compile(r"""\bid=['"]([^'"]+)['"]""", re.IGNORECASE)
# Headings that are utility sections, not editorial ones — they get anchor ids
# (so deep links keep working) but are kept OUT of the article's Table of
# Contents, which should list only the real reading sections. Anchored to the
# WHOLE heading text so an editorial section that merely contains one of these
# words (e.g. "Open Source Tooling", "API Reference") is NOT dropped.
_TOC_SKIP_RE = re.compile(
    r"^\s*(?:frequently\s+asked\s+questions|faq|sources?|references?(?:\s*&.*)?"
    r"|further\s+reading|citations?)\s*$",
    re.IGNORECASE,
)


def _strip(s: str) -> str:
    return html.unescape(_TAG_RE.sub("", s or "")).strip()


def _anchor_id(text: str, used: set[str]) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", _strip(text).lower()).strip("-")[:50] or "section"
    aid, i = base, 2
    while aid in used:
        aid, i = f"{base}-{i}", i + 1
    used.add(aid)
    return aid


def add_toc(html_body: str, *, min_sections: int = 3) -> str:
    """Inject ``id`` anchors into every <h2> and prepend a clickable ToC.

    No-op (returns input) when there are fewer than ``min_sections`` headings —
    a ToC on a short post is noise.
    """
    used: set[str] = set()
    toc: list[tuple[str, str]] = []

    def repl(m: re.Match) -> str:
        attrs, inner = m.group(1), m.group(2)
        text = _strip(inner)
        existing = _ID_RE.search(attrs)
        if existing:
            aid = existing.group(1)
        else:
            aid = _anchor_id(inner, used)
            attrs = f'{attrs} id="{aid}"'
        # Anchor every h2 (deep links keep working) but list only editorial
        # sections in the ToC — skip FAQ / References / Sources utility headings.
        if not _TOC_SKIP_RE.search(text):
            toc.append((aid, text))
        return f"<h2{attrs}>{inner}</h2>"

    new_body = _H2_RE.sub(repl, html_body)
    if len(toc) < min_sections:
        return html_body

    items = "\n".join(f'<li><a href="#{aid}">{html.escape(text)}</a></li>'
                      for aid, text in toc)
    nav = (
        '<nav class="toc mb-4">\n<p><strong>In this article</strong></p>\n'
        f"<ul>\n{items}\n</ul>\n</nav>"
    )
    return nav + "\n" + new_body


def reading_time_badge(html_body: str, *, wpm: int = 220) -> str:
    # Charts excluded so their SVG/caption text doesn't skew the estimate.
    words = len(_strip(strip_chart_blocks(html_body)).split())
    minutes = max(1, round(words / wpm))
    return f'<p class="reading-time text-muted"><em>{minutes} min read</em></p>'


def related_posts_html(items: list[tuple[str, str]], *, limit: int = 5) -> str:
    """`items`: (title, url) pairs (e.g. this blog's recent posts)."""
    links = [(t, u) for t, u in items if u]
    if not links:
        return ""
    lis = "\n".join(
        f'<li><a href="{html.escape(u, quote=True)}">{html.escape(t)}</a></li>'
        for t, u in links[:limit]
    )
    # <h2> (not <h3>): this is a top-level section appended after the body, so an
    # <h3> here would skip a heading level (h2 -> h3 with no parent) and trip
    # accessibility/SEO heading-order audits.
    return f"<h2>Related from this blog</h2>\n<ul>\n{lis}\n</ul>"
