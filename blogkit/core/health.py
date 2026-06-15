"""Preflight checks (`blogkit doctor`): validate that everything a real run
needs is present *before* burning Gemini/HF quota — catches the "missing secret
/ expired token" class of failure early.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from blogkit.profiles.registry import all_profiles


@dataclass
class Check:
    name: str
    ok: bool
    detail: str = ""


def _set(name: str) -> bool:
    return bool(os.environ.get(name))


def _adc_well_known_path() -> str:
    """Path to the Application Default Credentials file written by
    `gcloud auth application-default login`."""
    cfg = os.environ.get("CLOUDSDK_CONFIG")
    if cfg:
        return os.path.join(cfg, "application_default_credentials.json")
    if os.name == "nt":
        return os.path.join(os.environ.get("APPDATA", ""), "gcloud",
                            "application_default_credentials.json")
    return os.path.join(os.path.expanduser("~"), ".config", "gcloud",
                        "application_default_credentials.json")


def _vertex_creds_available() -> bool:
    """True when Vertex can authenticate by any supported path: an inline SA
    key, an explicit credential file, the CI Workload-Identity file, or a local
    `gcloud auth application-default login` (ADC well-known file)."""
    for var in ("GCP_SA_KEY", "GOOGLE_APPLICATION_CREDENTIALS", "GOOGLE_GHA_CREDS_PATH"):
        if _set(var):
            return True
    try:
        return os.path.isfile(_adc_well_known_path())
    except OSError:  # pragma: no cover - defensive
        return False


def check_environment(*, publish_method: str = "api", need_image: bool = True) -> list[Check]:
    """Return a list of pass/fail checks for the given run shape."""
    checks: list[Check] = []

    # Profiles load + validate.
    try:
        profs = all_profiles()
        checks.append(Check("profiles", bool(profs), f"{len(profs)} loaded & valid"))
    except Exception as e:  # pragma: no cover - defensive
        checks.append(Check("profiles", False, f"load error: {e}"))
        profs = []

    # Gemini key: the universal GEMINI_API_KEY fallback, or every per-blog key.
    if _set("GEMINI_API_KEY"):
        checks.append(Check("gemini_key", True, "GEMINI_API_KEY set (fallback)"))
    else:
        missing = sorted({p.api_key_env for p in profs if not _set(p.api_key_env)})
        checks.append(Check(
            "gemini_key", not missing,
            "all per-blog keys set" if not missing
            else f"no GEMINI_API_KEY and missing: {', '.join(missing)}",
        ))

    # Publish transport.
    if publish_method == "email":
        transport = ("SMTP_USER", "SMTP_PASSWORD", "BLOGGER_SECRET_EMAIL")
    else:
        transport = ("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GOOGLE_REFRESH_TOKEN")
    for v in transport:
        checks.append(Check(v, _set(v)))

    # Featured image. The generation engine depends on IMAGE_PROVIDER; hosting
    # (ASSETS_REPO_PAT) is required either way.
    if need_image:
        provider = (os.environ.get("IMAGE_PROVIDER") or "hf").strip().lower()
        if provider == "vertex":
            has_creds = _vertex_creds_available()
            checks.append(Check(
                "vertex_credentials", has_creds,
                "keyless ADC / Workload Identity or GCP_SA_KEY available" if has_creds
                else "run `gcloud auth application-default login` locally, or set "
                     "up Workload Identity (CI) / GCP_SA_KEY",
            ))
            has_project = (
                _set("GCP_PROJECT") or _set("GOOGLE_CLOUD_PROJECT") or _set("GCP_SA_KEY")
            )
            checks.append(Check(
                "vertex_project", has_project,
                "GCP_PROJECT / GOOGLE_CLOUD_PROJECT set (or carried by the key)" if has_project
                else "set GCP_PROJECT (the auth action exports it automatically in CI)",
            ))
        else:
            checks.append(Check("HF_API_TOKEN", _set("HF_API_TOKEN")))
        checks.append(Check("ASSETS_REPO_PAT", _set("ASSETS_REPO_PAT")))

    return checks


def all_ok(checks: list[Check]) -> bool:
    return all(c.ok for c in checks)


def format_checks(checks: list[Check]) -> str:
    lines = []
    for c in checks:
        mark = "PASS" if c.ok else "FAIL"
        suffix = f" — {c.detail}" if c.detail else ""
        lines.append(f"  [{mark}] {c.name}{suffix}")
    return "\n".join(lines)
