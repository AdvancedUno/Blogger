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


# --- provider selection ----------------------------------------------------

def test_active_provider_defaults_to_hf(monkeypatch):
    monkeypatch.delenv("IMAGE_PROVIDER", raising=False)
    assert imager.active_provider() == "hf"
    monkeypatch.setenv("IMAGE_PROVIDER", "  VERTEX ")
    assert imager.active_provider() == "vertex"


def test_generate_png_dispatches_to_vertex(monkeypatch):
    monkeypatch.setenv("IMAGE_PROVIDER", "vertex")
    called = {}

    def fake_vertex(prompt, seed):
        called["vertex"] = (prompt, seed)
        return b"PNG"

    monkeypatch.setattr(imager, "_vertex_generate_png", fake_vertex)
    monkeypatch.setattr(imager, "_hf_generate_png",
                        lambda *a, **k: pytest.fail("HF must not be called"))
    assert imager._generate_png("a prompt", 7) == b"PNG"
    assert called["vertex"] == ("a prompt", 7)


def test_generate_png_dispatches_to_hf_by_default(monkeypatch):
    monkeypatch.delenv("IMAGE_PROVIDER", raising=False)
    monkeypatch.setenv("HF_API_TOKEN", "tok")
    monkeypatch.setattr(imager, "_hf_generate_png",
                        lambda prompt, seed, hf_token: b"HFPNG")
    assert imager._generate_png("p", 3) == b"HFPNG"


def test_generate_png_hf_requires_token(monkeypatch):
    monkeypatch.delenv("IMAGE_PROVIDER", raising=False)
    monkeypatch.delenv("HF_API_TOKEN", raising=False)
    with pytest.raises(ValueError, match="HF_API_TOKEN"):
        imager._generate_png("p", 1)


# --- vertex config + endpoint ----------------------------------------------

def test_vertex_config_defaults_and_overrides(monkeypatch):
    for v in ("GCP_PROJECT", "GOOGLE_CLOUD_PROJECT", "VERTEX_LOCATION", "VERTEX_IMAGE_MODEL"):
        monkeypatch.delenv(v, raising=False)
    project, location, model = imager._vertex_config()
    assert project == ""
    assert location == imager.VERTEX_LOCATION_DEFAULT
    assert model == imager.VERTEX_IMAGE_MODEL_DEFAULT

    monkeypatch.setenv("GCP_PROJECT", "my-proj")
    monkeypatch.setenv("VERTEX_LOCATION", "europe-west4")
    monkeypatch.setenv("VERTEX_IMAGE_MODEL", "imagen-4.0-ultra-generate-001")
    assert imager._vertex_config() == (
        "my-proj", "europe-west4", "imagen-4.0-ultra-generate-001",
    )


def test_resolve_gcp_project_prefers_env_then_fallback(monkeypatch):
    for v in ("GCP_PROJECT", "GOOGLE_CLOUD_PROJECT"):
        monkeypatch.delenv(v, raising=False)
    # Neither env set -> the credential/SA fallback wins (keyless path).
    assert imager._resolve_gcp_project("from-creds") == "from-creds"
    # GOOGLE_CLOUD_PROJECT (exported by gcloud / the auth action) is honored.
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "from-gcloud")
    assert imager._resolve_gcp_project("from-creds") == "from-gcloud"
    # Explicit GCP_PROJECT takes top priority.
    monkeypatch.setenv("GCP_PROJECT", "explicit")
    assert imager._resolve_gcp_project("from-creds") == "explicit"


def test_vertex_endpoint_format():
    url = imager._vertex_endpoint("proj", "us-central1", "imagen-4.0-fast-generate-001")
    assert url == (
        "https://us-central1-aiplatform.googleapis.com/v1/projects/proj/"
        "locations/us-central1/publishers/google/models/"
        "imagen-4.0-fast-generate-001:predict"
    )


def test_vertex_generate_png_parses_base64(monkeypatch):
    import base64 as _b64

    raw = b"\x89PNG real-ish bytes"
    monkeypatch.setattr(imager, "_vertex_access_token", lambda: ("tok", "proj"))
    monkeypatch.setattr(imager, "_vertex_config",
                        lambda: ("proj", "us-central1", "imagen-4.0-fast-generate-001"))

    class FakeResp:
        def raise_for_status(self): pass
        def json(self):
            return {"predictions": [{
                "bytesBase64Encoded": _b64.b64encode(raw).decode(),
                "mimeType": "image/png",
            }]}

    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["url"], captured["json"] = url, json
        return FakeResp()

    monkeypatch.setattr(imager.requests, "post", fake_post)
    out = imager._vertex_generate_png("a prompt", seed=123)
    assert out == raw
    assert captured["json"]["instances"][0]["prompt"] == "a prompt"
    assert captured["json"]["parameters"]["aspectRatio"] == "16:9"
    # Reproducible seed -> watermark must be disabled.
    assert captured["json"]["parameters"]["addWatermark"] is False
    assert "predict" in captured["url"]


def test_vertex_generate_png_returns_none_when_filtered(monkeypatch):
    monkeypatch.setattr(imager, "_vertex_access_token", lambda: ("tok", "proj"))
    monkeypatch.setattr(imager, "_vertex_config",
                        lambda: ("proj", "us-central1", "m"))

    class FakeResp:
        def raise_for_status(self): pass
        def json(self):
            return {"predictions": [{"raiFilteredReason": "blocked"}]}

    monkeypatch.setattr(imager.requests, "post",
                        lambda *a, **k: FakeResp())
    assert imager._vertex_generate_png("p", 1) is None


def test_warm_up_is_noop_for_vertex(monkeypatch):
    monkeypatch.setenv("IMAGE_PROVIDER", "vertex")
    monkeypatch.setattr(imager, "_hf_generate_png",
                        lambda *a, **k: pytest.fail("must not warm up HF for vertex"))
    imager.warm_up_image_model()  # should simply return
