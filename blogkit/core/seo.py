"""SEO enrichment: JSON-LD structured data + real source citations.

Adds two ranking levers to each post, both derived from content we already
have (no extra model calls):

  * ``build_jsonld`` — an Article + FAQPage JSON-LD ``<script>`` block. FAQPage
    is a direct shot at Google rich results / featured snippets, built from the
    post's own FAQ section.
  * ``build_references_html`` — a real "Sources" list linking the fetched
    articles (outbound citations strengthen E-E-A-T / trust signals).

All pure functions — no network. The post URL isn't known until after publish,
so schema that needs it (Breadcrumb) is intentionally omitted; Article +
FAQPage do not require it.
"""

from __future__ import annotations

import html
import json
import re
from datetime import datetime, timezone

_TAG_RE = re.compile(r"<[^>]+>")
_FAQ_PAIR_RE = re.compile(r"<h3[^>]*>(.*?)</h3>\s*<p[^>]*>(.*?)</p>", re.IGNORECASE | re.DOTALL)


def _text(s: str) -> str:
    """Strip tags + unescape entities -> plain text."""
    return html.unescape(_TAG_RE.sub("", s or "")).strip()


def extract_faqs(html_body: str) -> list[tuple[str, str]]:
    """Pull (question, answer) pairs from the post's FAQ section.

    Looks only after a heading containing "Frequently Asked Questions" (or
    "FAQ") so unrelated h3/p pairs elsewhere aren't captured.
    """
    m = re.search(r"<h2[^>]*>[^<]*(?:frequently asked questions|faq)[^<]*</h2>",
                  html_body, re.IGNORECASE)
    region = html_body[m.end():] if m else ""
    # Stop at the next h2 (end of the FAQ section), if any.
    nxt = re.search(r"<h2", region, re.IGNORECASE)
    if nxt:
        region = region[:nxt.start()]
    faqs = []
    for q, a in _FAQ_PAIR_RE.findall(region):
        qt, at = _text(q), _text(a)
        if qt and at:
            faqs.append((qt, at))
    return faqs


def make_description(html_body: str, title: str, limit: int = 155) -> str:
    """A meta-style description: first paragraph text, trimmed on a word
    boundary; falls back to the title."""
    m = re.search(r"<p[^>]*>(.*?)</p>", html_body, re.IGNORECASE | re.DOTALL)
    text = _text(m.group(1)) if m else _text(title)
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0].rstrip(",.;:") + "…"


def _word_count(html_body: str) -> int:
    return len(_text(html_body).split())


def _site_nodes(blog_name: str, site_url: str, section: str | None, title: str) -> list[dict]:
    """Sitewide schema that needs the blog's home URL: WebSite, Organization,
    and a BreadcrumbList (Home > Section > current page). Omitted entirely when
    no site_url is known (the post URL isn't available pre-publish, so the
    current page is a name-only breadcrumb leaf, which Google accepts)."""
    url = site_url.rstrip("/") + "/"
    org = {"@type": "Organization", "name": blog_name, "url": url}
    website = {"@type": "WebSite", "name": blog_name, "url": url}
    crumbs = [{"@type": "ListItem", "position": 1, "name": "Home", "item": url}]
    pos = 2
    if section:
        crumbs.append({"@type": "ListItem", "position": pos, "name": _text(section)})
        pos += 1
    crumbs.append({"@type": "ListItem", "position": pos, "name": _text(title)[:110]})
    breadcrumb = {"@type": "BreadcrumbList", "itemListElement": crumbs}
    return [website, org, breadcrumb]


def build_jsonld(*, title: str, html_body: str, blog_name: str,
                 news_items: list[dict] | None = None,
                 tags: list[str] | None = None,
                 section: str | None = None,
                 site_url: str | None = None) -> str:
    """Return a JSON-LD <script> block: Article + (if FAQs found) FAQPage, plus
    WebSite + Organization + BreadcrumbList when ``site_url`` is provided."""
    now = datetime.now(timezone.utc).isoformat()
    article: dict = {
        "@type": "Article",
        "headline": _text(title)[:110],
        "description": make_description(html_body, title),
        "datePublished": now,
        "dateModified": now,
        "wordCount": _word_count(html_body),
        "author": {"@type": "Organization", "name": blog_name},
        "publisher": {"@type": "Organization", "name": blog_name},
    }
    if tags:
        article["keywords"] = ", ".join(tags)
    if section:
        article["articleSection"] = section
    graph: list[dict] = [article]
    faqs = extract_faqs(html_body)
    if faqs:
        graph.append({
            "@type": "FAQPage",
            "mainEntity": [
                {"@type": "Question", "name": q,
                 "acceptedAnswer": {"@type": "Answer", "text": a}}
                for q, a in faqs
            ],
        })
    if site_url:
        graph.extend(_site_nodes(blog_name, site_url, section, title))
    payload = {"@context": "https://schema.org", "@graph": graph}
    # </ inside a JSON string would prematurely close the <script>; escape it.
    body = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    return f'<script type="application/ld+json">{body}</script>'


def build_references_html(news_items: list[dict] | None) -> str:
    """A 'Sources' list of real outbound links to the fetched articles."""
    items = news_items or []
    lis = []
    for n in items:
        link = (n.get("link") or "").strip()
        if not link:
            continue
        label = _text(n.get("title") or link)
        source = _text(n.get("source") or "")
        suffix = f" — {source}" if source else ""
        lis.append(
            f'<li><a href="{html.escape(link, quote=True)}" rel="nofollow noopener" '
            f'target="_blank">{html.escape(label)}{html.escape(suffix)}</a></li>'
        )
    if not lis:
        return ""
    return "<h3>Sources</h3>\n<ul>\n" + "\n".join(lis) + "\n</ul>"
