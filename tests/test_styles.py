"""The named style catalog is well-formed."""

from __future__ import annotations

from blogkit.core.styles import ALL_STYLE_NAMES, STYLE_PRESETS


def test_catalog_nonempty_and_strings():
    assert len(STYLE_PRESETS) >= 6
    assert all(isinstance(k, str) and k for k in STYLE_PRESETS)
    assert all(isinstance(v, str) and v.strip() for v in STYLE_PRESETS.values())


def test_all_style_names_matches_keys():
    assert set(ALL_STYLE_NAMES) == set(STYLE_PRESETS)
