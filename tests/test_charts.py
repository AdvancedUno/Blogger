"""Inline data-visual rendering: marker parsing, the 4 chart kinds, safety."""

from __future__ import annotations

import json

from blogkit.core.charts import CHART_INSTRUCTION, render_charts


def _marker(spec: dict) -> str:
    return "[[CHART]]" + json.dumps(spec) + "[[/CHART]]"


def test_no_marker_returns_body_unchanged():
    body = "<p>Just prose, no visuals.</p>"
    assert render_charts(body) == body


def test_bar_chart_renders_svg_with_labels():
    body = "<p>Intro.</p>" + _marker({
        "kind": "bar", "title": "Vendor cost", "unit": "$/mo", "source": "illustrative",
        "data": [{"label": "Acme", "value": 12}, {"label": "Globex", "value": 30}],
    })
    out = render_charts(body)
    assert "[[CHART]]" not in out and "[[/CHART]]" not in out
    assert "<svg" in out and "<rect" in out
    assert "Acme" in out and "Globex" in out
    assert "Vendor cost" in out                 # title rendered


def test_line_donut_and_stats_each_render():
    line = render_charts(_marker({
        "kind": "line", "data": [
            {"label": "Q1", "value": 4}, {"label": "Q2", "value": 9},
            {"label": "Q3", "value": 7},
        ]}))
    assert "<polyline" in line

    donut = render_charts(_marker({
        "kind": "donut", "data": [
            {"label": "A", "value": 3}, {"label": "B", "value": 1},
        ]}))
    assert "stroke-dasharray" in donut
    assert "75%" in donut and "25%" in donut       # A = 3/4, B = 1/4

    stats = render_charts(_marker({
        "kind": "stats", "data": [
            {"label": "p95 latency", "value": "6.2s"},
            {"label": "cache hit", "value": "71%"},
        ]}))
    assert "6.2s" in stats and "p95 latency" in stats
    assert "<svg" not in stats                   # stat cards are HTML, not SVG


def test_every_chart_carries_an_honesty_caption():
    illustrative = render_charts(_marker({
        "kind": "bar", "data": [{"label": "x", "value": 1}],
    }))
    assert "Illustrative" in illustrative
    real = render_charts(_marker({
        "kind": "bar", "source": "real", "data": [{"label": "x", "value": 1}],
    }))
    assert "compiled from the sources" in real


def test_malformed_chart_is_dropped_not_shipped():
    body = "<p>Before.</p>[[CHART]]{not valid json[[/CHART]]<p>After.</p>"
    out = render_charts(body)
    assert "[[CHART]]" not in out          # marker consumed
    assert "<svg" not in out               # nothing rendered
    assert "Before." in out and "After." in out


def test_unknown_kind_is_dropped():
    out = render_charts(_marker({"kind": "pie3d", "data": [{"label": "x", "value": 1}]}))
    assert out == ""                       # whole marker dropped


def test_labels_are_escaped():
    out = render_charts(_marker({
        "kind": "bar", "data": [{"label": "<script>alert(1)</script>", "value": 5}],
    }))
    assert "<script>" not in out
    assert "&lt;script&gt;" in out


def test_chart_count_is_capped():
    spec = {"kind": "bar", "data": [{"label": "x", "value": 1}]}
    body = (_marker(spec) + "<p>mid</p>") * 3
    out = render_charts(body, max_charts=2)
    assert out.count("<svg") == 2          # third marker dropped
    assert "[[CHART]]" not in out


def test_enclosing_paragraph_is_consumed():
    body = "<p>[[CHART]]" + json.dumps(
        {"kind": "bar", "data": [{"label": "x", "value": 1}]}
    ) + "[[/CHART]]</p>"
    out = render_charts(body)
    # The wrapping <p> is absorbed so we don't nest a block div inside a <p>.
    assert not out.startswith("<p>")
    assert "<svg" in out


def test_chart_instruction_states_marker_and_honesty_rule():
    assert "[[CHART]]" in CHART_INSTRUCTION
    assert "illustrative" in CHART_INSTRUCTION.lower()
    assert "never" in CHART_INSTRUCTION.lower()   # never label invented data "real"
