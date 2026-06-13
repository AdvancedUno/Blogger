"""Tests for the doctor preflight and run-digest formatting."""

from __future__ import annotations

import pytest

from blogkit.core.health import Check, all_ok, check_environment, format_checks

ALL_ENV = [
    "GEMINI_API_KEY", "GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET",
    "GOOGLE_REFRESH_TOKEN", "HF_API_TOKEN", "ASSETS_REPO_PAT",
    "SMTP_USER", "SMTP_PASSWORD", "BLOGGER_SECRET_EMAIL",
    "IMAGE_PROVIDER", "GCP_SA_KEY", "GOOGLE_APPLICATION_CREDENTIALS",
    "GOOGLE_GHA_CREDS_PATH", "GCP_PROJECT", "GOOGLE_CLOUD_PROJECT", "CLOUDSDK_CONFIG",
]


@pytest.fixture
def clean_env(monkeypatch):
    for v in ALL_ENV:
        monkeypatch.delenv(v, raising=False)
    # also clear per-blog keys that could satisfy the gemini check
    for i in range(11):
        monkeypatch.delenv(f"GEMINI_API_KEY_{i}", raising=False)
    return monkeypatch


def test_all_fail_when_env_empty(clean_env):
    checks = check_environment(publish_method="api", need_image=True)
    assert not all_ok(checks)
    names = {c.name for c in checks if not c.ok}
    assert {"gemini_key", "GOOGLE_CLIENT_ID", "HF_API_TOKEN", "ASSETS_REPO_PAT"} <= names


def test_api_ready_with_required_env(clean_env):
    for v in ("GEMINI_API_KEY", "GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET",
              "GOOGLE_REFRESH_TOKEN", "HF_API_TOKEN", "ASSETS_REPO_PAT"):
        clean_env.setenv(v, "x")
    assert all_ok(check_environment(publish_method="api", need_image=True))


def test_email_mode_checks_smtp_not_oauth(clean_env):
    for v in ("GEMINI_API_KEY", "SMTP_USER", "SMTP_PASSWORD", "BLOGGER_SECRET_EMAIL"):
        clean_env.setenv(v, "x")
    checks = check_environment(publish_method="email", need_image=False)
    assert all_ok(checks)
    assert {c.name for c in checks} >= {"SMTP_USER", "BLOGGER_SECRET_EMAIL"}
    assert "GOOGLE_CLIENT_ID" not in {c.name for c in checks}


def test_no_image_skips_image_checks(clean_env):
    for v in ("GEMINI_API_KEY", "GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET",
              "GOOGLE_REFRESH_TOKEN"):
        clean_env.setenv(v, "x")
    checks = check_environment(publish_method="api", need_image=False)
    assert "HF_API_TOKEN" not in {c.name for c in checks}
    assert all_ok(checks)


def test_vertex_provider_checks_gcp_not_hf(clean_env):
    for v in ("GEMINI_API_KEY", "GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET",
              "GOOGLE_REFRESH_TOKEN", "ASSETS_REPO_PAT"):
        clean_env.setenv(v, "x")
    clean_env.setenv("IMAGE_PROVIDER", "vertex")
    clean_env.setenv("GCP_SA_KEY", '{"project_id":"p"}')
    checks = check_environment(publish_method="api", need_image=True)
    names = {c.name for c in checks}
    assert "vertex_credentials" in names and "vertex_project" in names
    assert "HF_API_TOKEN" not in names      # HF not required under vertex
    assert all_ok(checks)


def test_vertex_provider_fails_without_credentials(clean_env, tmp_path):
    for v in ("GEMINI_API_KEY", "GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET",
              "GOOGLE_REFRESH_TOKEN", "ASSETS_REPO_PAT"):
        clean_env.setenv(v, "x")
    for v in ("GCP_SA_KEY", "GOOGLE_APPLICATION_CREDENTIALS", "GOOGLE_GHA_CREDS_PATH",
              "GCP_PROJECT", "GOOGLE_CLOUD_PROJECT"):
        clean_env.delenv(v, raising=False)
    # Point ADC discovery at an empty dir so a real local
    # `gcloud auth application-default login` on the dev box can't make this pass.
    clean_env.setenv("CLOUDSDK_CONFIG", str(tmp_path))
    clean_env.setenv("IMAGE_PROVIDER", "vertex")
    checks = check_environment(publish_method="api", need_image=True)
    failing = {c.name for c in checks if not c.ok}
    assert {"vertex_credentials", "vertex_project"} <= failing


def test_vertex_credentials_detected_from_adc_file(clean_env, tmp_path):
    for v in ("GCP_SA_KEY", "GOOGLE_APPLICATION_CREDENTIALS", "GOOGLE_GHA_CREDS_PATH"):
        clean_env.delenv(v, raising=False)
    clean_env.setenv("CLOUDSDK_CONFIG", str(tmp_path))
    (tmp_path / "application_default_credentials.json").write_text("{}")
    clean_env.setenv("IMAGE_PROVIDER", "vertex")
    for v in ("GEMINI_API_KEY", "GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET",
              "GOOGLE_REFRESH_TOKEN", "ASSETS_REPO_PAT", "GCP_PROJECT"):
        clean_env.setenv(v, "x")
    checks = check_environment(publish_method="api", need_image=True)
    by_name = {c.name: c for c in checks}
    assert by_name["vertex_credentials"].ok      # ADC file recognized
    assert all_ok(checks)


def test_format_checks_renders():
    out = format_checks([Check("a", True, "ok"), Check("b", False)])
    assert "[PASS] a — ok" in out and "[FAIL] b" in out


def test_digest_format_and_send_noop(monkeypatch):
    from blogkit.core import notify
    text = notify.format_digest([("blog_a", True, "url"), ("blog_b", False, "err")])
    assert "1/2 OK" in text and "blog_a" in text and "blog_b" in text
    monkeypatch.delenv("RUN_WEBHOOK_URL", raising=False)
    assert notify.send_digest("hi") is False  # no webhook configured
