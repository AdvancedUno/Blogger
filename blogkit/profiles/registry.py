"""Profile discovery: import every ``blogkit.profiles.<slug>`` module and collect
its ``PROFILE``. Lets you add a blog just by adding a module.
"""

from __future__ import annotations

import importlib
import pkgutil

from blogkit import profiles as _profiles_pkg
from blogkit.profiles.base import BlogProfile

_RESERVED = {"base", "registry"}
_cache: dict[str, BlogProfile] = {}


def _load() -> dict[str, BlogProfile]:
    if _cache:
        return _cache
    for mod in pkgutil.iter_modules(_profiles_pkg.__path__):
        if mod.name in _RESERVED or mod.name.startswith("_"):
            continue
        module = importlib.import_module(f"blogkit.profiles.{mod.name}")
        profile = getattr(module, "PROFILE", None)
        if not isinstance(profile, BlogProfile):
            raise TypeError(
                f"blogkit.profiles.{mod.name} has no module-level PROFILE: BlogProfile"
            )
        if profile.slug in _cache:
            raise ValueError(f"duplicate profile slug: {profile.slug!r}")
        _cache[profile.slug] = profile
    return _cache


def all_profiles() -> list[BlogProfile]:
    """Every registered profile, sorted by run_group then slug."""
    return sorted(_load().values(), key=lambda p: (p.run_group, p.slug))


def get_profile(slug: str) -> BlogProfile:
    profiles = _load()
    if slug not in profiles:
        raise KeyError(f"unknown blog slug {slug!r}; available: {sorted(profiles)}")
    return profiles[slug]


def by_group(group: int) -> list[BlogProfile]:
    return [p for p in all_profiles() if p.run_group == group]


def runnable(profiles: list[BlogProfile], disabled: set[str] | None = None) -> list[BlogProfile]:
    """Filter to blogs the pipeline should actually post to: enabled, and not
    in the runtime `disabled` slug set (BLOGKIT_DISABLE)."""
    dis = disabled or set()
    return [p for p in profiles if p.enabled and p.slug not in dis]
