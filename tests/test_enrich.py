"""Tests for on-page enrichment (ToC, reading time, related links)."""

from __future__ import annotations

from blogkit.core.enrich import add_toc, reading_time_badge, related_posts_html

THREE_H2 = (
    "<h2>First Section</h2><p>a</p>"
    "<h2>Second Section</h2><p>b</p>"
    "<h2>Third Section</h2><p>c</p>"
)


def test_add_toc_injects_anchors_and_nav():
    out = add_toc(THREE_H2)
    assert '<nav class="toc' in out
    assert 'id="first-section"' in out
    assert 'href="#first-section"' in out
    # all three sections linked
    assert out.count("<li>") == 3


def test_add_toc_noop_when_too_few_sections():
    short = "<h2>Only One</h2><p>x</p>"
    assert add_toc(short) == short


def test_add_toc_dedupes_anchor_ids():
    dup = "<h2>Risks</h2><p>a</p><h2>Risks</h2><p>b</p><h2>Risks</h2><p>c</p>"
    out = add_toc(dup)
    assert 'id="risks"' in out and 'id="risks-2"' in out and 'id="risks-3"' in out


def test_add_toc_preserves_existing_id():
    out = add_toc('<h2 id="keep">A</h2><p>x</p><h2>B</h2><p>y</p><h2>C</h2><p>z</p>')
    assert 'id="keep"' in out and 'href="#keep"' in out


def test_add_toc_excludes_faq_and_sources_from_nav():
    # FAQ / References / Sources are utility sections: still anchored (deep links
    # work) but kept OUT of the article ToC, which lists only reading sections.
    body = (
        "<h2>Real Section One</h2><p>a</p>"
        "<h2>Open Source Tooling</h2><p>b</p>"            # contains 'source' but editorial
        "<h2>Real Section Three</h2><p>c</p>"
        "<h2>Frequently Asked Questions</h2><p>d</p>"
        "<h2>Sources</h2><p>e</p>"
    )
    out = add_toc(body)
    nav = out.split("</nav>")[0]
    assert nav.count("<li>") == 3                          # 3 editorial sections
    assert "Frequently Asked Questions" not in nav
    assert ">Sources<" not in nav
    assert "Open Source Tooling" in nav                    # NOT dropped (anchored match)
    # ...but the skipped headings still get anchor ids for direct linking.
    assert 'id="frequently-asked-questions"' in out and 'id="sources"' in out


def test_reading_time_badge():
    body = "<p>" + " ".join(["word"] * 440) + "</p>"  # 440 words @220wpm = 2 min
    assert "2 min read" in reading_time_badge(body)
    assert "1 min read" in reading_time_badge("<p>short</p>")


def test_related_posts_html():
    out = related_posts_html([("Post A", "https://b/a"), ("No URL", "")])
    assert 'href="https://b/a"' in out and "Post A" in out
    assert out.count("<li>") == 1  # the urlless one is skipped


def test_related_posts_empty():
    assert related_posts_html([]) == ""
