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

    # Featured image.
    if need_image:
        for v in ("HF_API_TOKEN", "ASSETS_REPO_PAT"):
            checks.append(Check(v, _set(v)))

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
