"""Pure-logic tests for the image module (no network calls)."""

from __future__ import annotations

import pytest

pytest.importorskip("requests")  # imager imports requests at module load

from blogkit.core import imager  # noqa: E402
from blogkit.core.styles import STYLE_PRESETS  # noqa: E402


def test_slugify():
    assert imager._slugify("Why CFOs Must Rethink RTP!") == "why-cfos-must-rethink-rtp"
    assert imager._slugify("") == "post"
    assert imager._slugify("***") == "post"
    assert len(imager._slugify("x" * 200)) <= 60


def test_prompt_is_deterministic_and_uses_pool():
    pool = ["STYLE_A unique-token-a", "STYLE_B unique-token-b"]
    p1, s1 = imager._build_image_prompt("Quantum Risk in 2026", pool)
    p2, s2 = imager._build_image_prompt("Quantum Risk in 2026", pool)
    assert (p1, s1) == (p2, s2)                      # deterministic
    assert any(tok in p1 for tok in ("unique-token-a", "unique-token-b"))
    assert "Quantum Risk in 2026" in p1
    assert 0 <= s1 < 2**32


def test_prompt_varies_across_titles():
    pool = list(STYLE_PRESETS.values())
    seeds = {imager._build_image_prompt(t, pool)[1]
             for t in ("Alpha One", "Beta Two", "Gamma Three", "Delta Four")}
    assert len(seeds) >= 3  # hashing should spread titles


def test_url_templates():
    assert imager.GITHUB_CONTENTS_API.format(repo="a/b", path="images/x.png").startswith(
        "https://api.github.com/repos/a/b/contents/"
    )
    assert imager.JSDELIVR_URL.format(repo="a/b", sha="deadbeef", path="images/x.png") == (
        "https://cdn.jsdelivr.net/gh/a/b@deadbeef/images/x.png"
    )
