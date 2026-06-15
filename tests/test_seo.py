"""Pure-logic tests for SEO enrichment (JSON-LD + citations)."""

from __future__ import annotations

import json

from blogkit.core.seo import (
    build_jsonld,
    build_references_html,
    extract_faqs,
    make_description,
)

SAMPLE = """<h1>Enterprise RTP Integration</h1>
<p>Real-time payments are reshaping corporate treasury operations this quarter.</p>
<h2>Regulatory Pressures</h2>
<p>ISO 20022 matters.</p>
<h2>Frequently Asked Questions</h2>
<h3>What is the primary blind spot?</h3>
<p>Legacy ERP connectivity is the usual blocker.</p>
<h3>How should CFOs model ROI?</h3>
<p>Use conservative 12-18 month ranges.</p>
<h2>References</h2>
<p>Synthesized from signals.</p>
"""


def test_extract_faqs_only_from_faq_section():
    faqs = extract_faqs(SAMPLE)
    assert len(faqs) == 2
    assert faqs[0][0] == "What is the primary blind spot?"
    assert "Legacy ERP" in faqs[0][1]
    # the Regulatory h3-less section must not leak in
    assert all("ISO 20022" not in a for _, a in faqs)


def test_make_description_uses_first_paragraph():
    d = make_description(SAMPLE, "Enterprise RTP Integration")
    assert d.startswith("Real-time payments")
    assert len(d) <= 156


def test_make_description_skips_summary_blockquote():
    # Real posts open with a <blockquote> summary callout whose first <p> is
    # just a short box heading — the description must skip it and use the
    # snippet-worthy opening body paragraph instead.
    body = (
        "<blockquote><p><strong>The 60-Second Briefing</strong></p>"
        "<ul><li><strong>Trigger:</strong> something happened.</li></ul></blockquote>"
        "<h2>What the market missed</h2>"
        "<p>Real-time payment rails are quietly rewiring how mid-market "
        "treasurers move cash this quarter, and the ERP vendors are not ready.</p>"
    )
    d = make_description(body, "RTP Rails")
    assert d.startswith("Real-time payment rails")
    assert "60-Second" not in d


def test_make_description_prefers_substantive_paragraph():
    # A short one-sentence punch paragraph should not win over a real one.
    body = "<p>It broke.</p><p>" + "word " * 40 + "and the details that matter.</p>"
    d = make_description(body, "T")
    assert not d.startswith("It broke")


def test_build_jsonld_is_valid_and_has_faqpage():
    block = build_jsonld(title="Enterprise RTP Integration", html_body=SAMPLE,
                         blog_name="B2B Payment Rails")
    assert block.startswith('<script type="application/ld+json">')
    inner = block[len('<script type="application/ld+json">'):-len("</script>")]
    data = json.loads(inner.replace("<\\/", "</"))
    types = {node["@type"] for node in data["@graph"]}
    assert "Article" in types and "FAQPage" in types
    faqpage = next(n for n in data["@graph"] if n["@type"] == "FAQPage")
    assert len(faqpage["mainEntity"]) == 2


def _article_node(block: str) -> dict:
    inner = block[len('<script type="application/ld+json">'):-len("</script>")]
    data = json.loads(inner.replace("<\\/", "</"))
    return next(n for n in data["@graph"] if n["@type"] == "Article")


def test_jsonld_article_has_inlanguage_and_optional_image():
    # inLanguage always present; image only when a CDN URL is supplied.
    plain = _article_node(build_jsonld(title="T", html_body=SAMPLE, blog_name="B"))
    assert plain["inLanguage"] == "en"
    assert "image" not in plain
    withimg = _article_node(build_jsonld(
        title="T", html_body=SAMPLE, blog_name="B",
        image_url="https://cdn.jsdelivr.net/gh/x/y@sha/img.png",
    ))
    assert withimg["image"] == ["https://cdn.jsdelivr.net/gh/x/y@sha/img.png"]


def test_extract_faqs_captures_multi_paragraph_answer():
    body = (
        "<h2>Frequently Asked Questions</h2>"
        "<h3>What breaks first?</h3>"
        "<p>The connector layer goes first.</p>"
        "<p>Then the audit trail drifts out of sync.</p>"
        "<h3>How long to recover?</h3>"
        "<p>Usually a sprint.</p>"
    )
    faqs = extract_faqs(body)
    assert len(faqs) == 2
    # Both paragraphs of the first answer are captured, not just the first.
    assert "connector layer" in faqs[0][1] and "audit trail" in faqs[0][1]
    assert faqs[1][1] == "Usually a sprint."


def test_jsonld_has_no_raw_closing_tag():
    block = build_jsonld(title="X</script> hack", html_body="<p>hi</p>",
                         blog_name="Blog")
    # no unescaped </ that could break out of the <script>
    assert "</" not in block[:-len("</script>")]


def test_references_links_real_sources():
    news = [
        {"title": "RTP hits record volume", "link": "https://ex.com/a", "source": "Reuters"},
        {"title": "No link item", "link": "", "source": "X"},
    ]
    out = build_references_html(news)
    assert 'href="https://ex.com/a"' in out and "Reuters" in out
    assert out.count("<li>") == 1  # the linkless item is skipped
    # Top-level section heading (not an h3) so heading order stays valid.
    assert out.startswith("<h2>Sources</h2>")


def test_references_empty_when_no_links():
    assert build_references_html([]) == ""
