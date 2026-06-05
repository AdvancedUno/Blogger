"""Inline data visuals (charts) rendered by us, not by the model.

The model is unreliable at hand-drawing correct SVG, and a chart full of
invented numbers is the exact fabrication risk the craft laws fight. So the
contract is split:

* The model decides WHEN a visual genuinely helps and emits a small, structured
  data block — a ``[[CHART]]{json}[[/CHART]]`` marker — with an honest
  ``source`` flag (``"real"`` = grounded in the cited sources, else illustrative).
* This module parses that marker and renders clean, consistent, validated inline
  SVG/HTML. Malformed or fabricated-looking data is dropped gracefully (the post
  still publishes), and every visual carries a visible honesty caption.

Inline SVG is allowed markup (not an ``<img>``), needs no JavaScript or external
request, scales crisply, stays selectable, and is tiny — AdSense- and
Core-Web-Vitals-friendly. Four visual kinds are supported: ``bar`` (horizontal
comparison), ``line`` (trend), ``donut`` (share), and ``stats`` (big-number
callout cards).

All functions are pure (no network, no SDK) and unit-testable.
"""

from __future__ import annotations

import html as _html
import json
import logging
import math
import re

logger = logging.getLogger(__name__)

# At most this many visuals per post (a treat, not a tic) and this many data
# points per chart (kept small so they read cleanly on mobile).
MAX_CHARTS = 2
_MAX_POINTS = 6          # bar / donut
_MAX_LINE_POINTS = 8     # line / trend
_MAX_STATS = 4           # stat cards

# Palette + neutrals. One tasteful, consistent house style across the network
# (a clean, well-made chart is a positive quality signal, not a fingerprint).
_PALETTE = ("#2563eb", "#16a34a", "#d97706", "#dc2626", "#7c3aed", "#0891b2")
_INK = "#0f172a"      # primary text / dark fill
_MUTED = "#64748b"    # captions / secondary labels
_TRACK = "#e2e8f0"    # bar tracks, grid lines, donut base ring

# Paired marker the model emits. Tolerates an enclosing <p> the model may add
# and multiline JSON between the delimiters.
_MARKER_RE = re.compile(
    r"(?:<p>\s*)?\[\[CHART\]\](.*?)\[\[/CHART\]\](?:\s*</p>)?",
    re.DOTALL | re.IGNORECASE,
)
_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


# The instruction injected into the prompt ONLY when the per-piece structural
# plan calls for a visual. Kept concise and explicit about the honesty rule.
CHART_INSTRUCTION = (
    "CHART FORMAT (use ONLY for the single data visual the structural plan "
    "asked for, and only if it genuinely clarifies a comparison, trend, or "
    "share — never decoration, never invented data to fill it):\n"
    "Emit the visual as a marker on its own line, exactly:\n"
    "[[CHART]]{\"kind\":\"bar\",\"title\":\"...\",\"unit\":\"%\","
    "\"source\":\"illustrative\",\"data\":[{\"label\":\"...\",\"value\":12}]}"
    "[[/CHART]]\n"
    "- kind: \"bar\" (horizontal comparison), \"line\" (trend over an ordered "
    "x-axis), \"donut\" (share of a whole), or \"stats\" (2-4 big-number "
    "callout cards; each value may be a string like \"6.2s\").\n"
    "- data: 2-6 points (2-4 for stats); numeric \"value\" for bar/line/donut.\n"
    "- source: \"real\" ONLY if every number traces to the Source Data provided; "
    "otherwise \"illustrative\" (the default). NEVER label invented figures "
    "\"real\". If you would have to make the numbers up to draw it, do NOT emit "
    "a chart — write the point in prose instead.\n"
    "- Keep all other prose as normal HTML; the marker is the only place JSON "
    "may appear. At most one chart in the piece."
)


def _esc(s: object) -> str:
    return _html.escape(str(s))


def _fmt(v: float) -> str:
    """Compact number: drop the decimal when it's a whole number."""
    return str(int(v)) if float(v).is_integer() else f"{v:.1f}"


def _pairs(spec: dict, cap: int) -> list[tuple[str, float]]:
    """(escaped-label, numeric-value) pairs, capped. Raises on missing/bad data."""
    out: list[tuple[str, float]] = []
    for d in (spec.get("data") or [])[:cap]:
        out.append((_esc(d["label"]), float(d["value"])))
    if not out:
        raise ValueError("chart has no data points")
    return out


def _caption(spec: dict) -> str:
    """The visible honesty stamp under every visual."""
    src = str(spec.get("source") or "illustrative").lower()
    base = (
        "Figures compiled from the sources cited below."
        if src == "real"
        else "Illustrative figures for explanation — representative, not measured."
    )
    note = spec.get("caption")
    return f"{_esc(note)} · {base}" if note else base


def _wrap(spec: dict, inner: str, max_width: int) -> str:
    """Title (optional) + the visual + the honesty caption, in one container."""
    parts = ['<div class="bk-chart" style="margin:1.6em 0;">']
    title = spec.get("title")
    if title:
        parts.append(
            f'<div style="font-weight:600;color:{_INK};margin-bottom:.5em;'
            f'font-size:1.02em;">{_esc(title)}</div>'
        )
    parts.append(
        f'<div style="max-width:{max_width}px;">{inner}</div>'
    )
    parts.append(
        f'<p style="font-size:.8em;color:{_MUTED};margin:.5em 0 0;">{_caption(spec)}</p>'
    )
    parts.append("</div>")
    return "".join(parts)


def _svg_open(w: int, h: int) -> str:
    return (
        f'<svg viewBox="0 0 {w} {h}" width="100%" preserveAspectRatio="xMidYMid meet" '
        f'role="img" style="display:block;width:100%;height:auto;font-family:inherit;">'
    )


def _render_bar(spec: dict) -> str:
    pairs = _pairs(spec, _MAX_POINTS)
    maxv = max(v for _, v in pairs)
    if maxv <= 0:
        raise ValueError("bar chart needs a positive value")
    unit = _esc(spec.get("unit") or "")
    w, row, top = 600, 46, 6
    tx, tw = 4, 600 - 8
    h = top + len(pairs) * row
    out = [_svg_open(w, h)]
    for i, (lab, v) in enumerate(pairs):
        y = top + i * row
        fill_w = tw * (v / maxv)
        color = _PALETTE[i % len(_PALETTE)]
        val = _fmt(v) + (f" {unit}" if unit else "")
        out.append(f'<text x="{tx}" y="{y + 15}" font-size="13" fill="{_INK}">{lab}</text>')
        out.append(f'<rect x="{tx}" y="{y + 22}" width="{tw}" height="16" rx="4" fill="{_TRACK}"/>')
        out.append(
            f'<rect x="{tx}" y="{y + 22}" width="{fill_w:.1f}" height="16" rx="4" fill="{color}"/>'
        )
        if fill_w > tw * 0.82:   # label fits inside a long bar
            out.append(
                f'<text x="{tx + fill_w - 6:.1f}" y="{y + 34}" font-size="12" fill="#fff" '
                f'text-anchor="end">{val}</text>'
            )
        else:                    # label sits just past the bar end
            out.append(
                f'<text x="{tx + fill_w + 6:.1f}" y="{y + 34}" font-size="12" '
                f'fill="{_INK}">{val}</text>'
            )
    out.append("</svg>")
    return _wrap(spec, "".join(out), w)


def _render_line(spec: dict) -> str:
    pairs = _pairs(spec, _MAX_LINE_POINTS)
    labels = [lab for lab, _ in pairs]
    vals = [v for _, v in pairs]
    w, h = 600, 240
    pad_l, pad_r, pad_t, pad_b = 44, 16, 16, 40
    plot_w, plot_h = w - pad_l - pad_r, h - pad_t - pad_b
    vmin, vmax = min(vals), max(vals)
    if vmax == vmin:
        vmax = vmin + 1
    n = len(vals)
    base = pad_t + plot_h
    color = _PALETTE[0]

    def xf(i: int) -> float:
        return pad_l + (plot_w * i / (n - 1) if n > 1 else plot_w / 2)

    def yf(v: float) -> float:
        return pad_t + plot_h * (1 - (v - vmin) / (vmax - vmin))

    out = [_svg_open(w, h)]
    out.append(
        f'<line x1="{pad_l}" y1="{base}" x2="{w - pad_r}" y2="{base}" '
        f'stroke="{_TRACK}" stroke-width="1"/>'
    )
    pts = " ".join(f"{xf(i):.1f},{yf(v):.1f}" for i, v in enumerate(vals))
    out.append(f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="2.5"/>')
    for i, v in enumerate(vals):
        x, y = xf(i), yf(v)
        out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.5" fill="{color}"/>')
        out.append(
            f'<text x="{x:.1f}" y="{base + 16}" font-size="11" fill="{_MUTED}" '
            f'text-anchor="middle">{labels[i]}</text>'
        )
        out.append(
            f'<text x="{x:.1f}" y="{y - 8:.1f}" font-size="11" fill="{_INK}" '
            f'text-anchor="middle">{_fmt(v)}</text>'
        )
    out.append("</svg>")
    return _wrap(spec, "".join(out), w)


def _render_donut(spec: dict) -> str:
    pairs = [(lab, v) for lab, v in _pairs(spec, _MAX_POINTS) if v > 0]
    total = sum(v for _, v in pairs)
    if total <= 0:
        raise ValueError("donut needs a positive total")
    cx, cy, r, sw = 110, 110, 80, 34
    circ = 2 * math.pi * r
    w, h = 600, 220
    out = [_svg_open(w, h)]
    out.append(
        f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{_TRACK}" '
        f'stroke-width="{sw}"/>'
    )
    cum = 0.0
    legend: list[str] = []
    for i, (lab, v) in enumerate(pairs):
        frac = v / total
        start = -90 + 360 * cum
        dash = frac * circ
        color = _PALETTE[i % len(_PALETTE)]
        out.append(
            f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{color}" '
            f'stroke-width="{sw}" stroke-dasharray="{dash:.2f} {circ - dash:.2f}" '
            f'transform="rotate({start:.2f} {cx} {cy})"/>'
        )
        cum += frac
        ly = 26 + i * 28
        legend.append(f'<rect x="240" y="{ly}" width="14" height="14" rx="3" fill="{color}"/>')
        legend.append(
            f'<text x="262" y="{ly + 12}" font-size="13" fill="{_INK}">'
            f'{lab} — {round(frac * 100)}%</text>'
        )
    out.extend(legend)
    out.append("</svg>")
    return _wrap(spec, "".join(out), w)


def _render_stats(spec: dict) -> str:
    items = (spec.get("data") or [])[:_MAX_STATS]
    if not items:
        raise ValueError("stats needs at least one item")
    cards = []
    for d in items:
        val, lab = _esc(d["value"]), _esc(d["label"])
        cards.append(
            f'<div style="flex:1 1 130px;min-width:130px;border:1px solid {_TRACK};'
            f'border-radius:10px;padding:14px 16px;">'
            f'<div style="font-size:1.7em;font-weight:700;color:{_INK};'
            f'line-height:1.1;">{val}</div>'
            f'<div style="font-size:.82em;color:{_MUTED};margin-top:4px;">{lab}</div></div>'
        )
    inner = '<div style="display:flex;flex-wrap:wrap;gap:12px;">' + "".join(cards) + "</div>"
    return _wrap(spec, inner, 600)


_RENDERERS = {
    "bar": _render_bar,
    "line": _render_line,
    "donut": _render_donut,
    "stats": _render_stats,
}


def _render_one(spec: dict) -> str:
    kind = str(spec.get("kind") or "bar").lower()
    renderer = _RENDERERS.get(kind)
    if renderer is None:
        raise ValueError(f"unknown chart kind {kind!r}")
    return renderer(spec)


def render_charts(html_body: str, max_charts: int = MAX_CHARTS) -> str:
    """Replace every ``[[CHART]]...[[/CHART]]`` marker with rendered inline HTML.

    Malformed/unsupported markers are dropped (replaced with nothing) so a bad
    chart never ships broken markup. Caps the number of visuals per post.
    """
    if not html_body or "[[CHART]]" not in html_body:
        return html_body
    count = 0

    def _repl(m: re.Match[str]) -> str:
        nonlocal count
        if count >= max_charts:
            return ""
        raw = _FENCE_RE.sub("", m.group(1).strip())
        try:
            spec = json.loads(raw)
            if not isinstance(spec, dict):
                raise ValueError("chart spec is not an object")
            rendered = _render_one(spec)
        except Exception as e:  # noqa: BLE001 — any bad chart is dropped, not fatal
            logger.warning("Dropping malformed chart marker: %s", e)
            return ""
        count += 1
        return rendered

    return _MARKER_RE.sub(_repl, html_body)
