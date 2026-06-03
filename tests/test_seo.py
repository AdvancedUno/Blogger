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


def test_references_empty_when_no_links():
    assert build_references_html([]) == ""
