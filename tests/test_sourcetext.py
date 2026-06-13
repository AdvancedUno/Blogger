"""Source-text grounding: URL decoding + article extraction (pure parts only).

Network paths (_resolve_via_api, enrich_news's HTTP) are intentionally not
exercised — they're best-effort by design and fully exception-wrapped.
"""

from __future__ import annotations

import base64

import pytest

pytest.importorskip("requests")

from blogkit.core.sourcetext import (  # noqa: E402
    MAX_SUMMARY_CHARS,
    decode_gnews_url,
    extract_article_text,
)


def _old_style_link(url: str) -> str:
    """Build an old-style Google News RSS link embedding `url` in its token."""
    raw = b"\x08\x13\x22" + bytes([len(url)]) + url.encode() + b"\xd2\x01\x00"
    token = base64.urlsafe_b64encode(raw).decode().rstrip("=")
    return f"https://news.google.com/rss/articles/{token}?oc=5"


def test_decode_old_style_token_recovers_publisher_url():
    url = "https://example.com/story/grid-storage-permits"
    assert decode_gnews_url(_old_style_link(url)) == url


def test_decode_rejects_non_gnews_and_garbage():
    assert decode_gnews_url("https://example.com/a") == ""
    assert decode_gnews_url("https://news.google.com/rss/articles/!!!") == ""
    assert decode_gnews_url("") == ""


def test_extract_keeps_body_paragraphs_drops_boilerplate():
    para = ("This is a real article paragraph with enough length to count as "
            "body prose, including facts.")
    nav_p = ("Home | News | A long navigation paragraph that should never "
             "appear in output text.")
    foot_p = ("Copyright legal boilerplate text that is also long enough to "
              "look like prose maybe.")
    page = (
        "<html><head><script>var x=1;</script><style>p{}</style></head><body>"
        f"<nav><p>{nav_p}</p></nav>"
        f"<article><p>{para}</p><p>Short.</p><p>{para}</p></article>"
        f"<footer><p>{foot_p}</p></footer>"
        "</body></html>"
    )
    out = extract_article_text(page)
    assert para in out
    assert "navigation" not in out
    assert "Copyright" not in out
    assert "Short." not in out          # too short to be body prose


def test_extract_caps_length_on_word_boundary():
    page = "".join(f"<p>{'sentence word ' * 20}{i}</p>" for i in range(60))
    out = extract_article_text(page)
    assert len(out) <= MAX_SUMMARY_CHARS
    assert not out.endswith(" ")
