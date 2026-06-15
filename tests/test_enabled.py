"""enabled flag + staged-blog validation + runnable() filtering."""

from __future__ import annotations

import pytest

from blogkit.profiles.base import BlogProfile
from blogkit.profiles.registry import runnable


def _profile(slug, **kw):
    base = dict(slug=slug, name=slug, blog_id="123", run_group=1,
                persona="x", rss_queries=["q"])
    base.update(kw)
    return BlogProfile(**base)


def test_enabled_defaults_true():
    assert _profile("a").enabled is True


def test_staged_blog_may_have_todo_blog_id_when_disabled():
    p = _profile("staged", enabled=False, blog_id="TODO_staged")
    assert p.enabled is False and p.blog_id == "TODO_staged"


def test_enabled_blog_rejects_placeholder_blog_id():
    with pytest.raises(ValueError):
        _profile("bad", enabled=True, blog_id="TODO_bad")
    with pytest.raises(ValueError):
        _profile("bad2", enabled=True, blog_id="[unset]")


def test_runnable_filters_disabled_and_blocklist():
    on = _profile("on")
    off = _profile("off", enabled=False, blog_id="TODO_off")
    blocked = _profile("blocked")
    out = runnable([on, off, blocked], disabled={"blocked"})
    assert out == [on]
