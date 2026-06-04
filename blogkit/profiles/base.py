"""The per-blog profile schema.

A ``BlogProfile`` is the single source of truth for one blog: its identity,
editorial voice, source queries, image identity, and publish settings. Profiles
are validated at load time (pydantic), so a malformed blog fails fast instead of
producing a broken post.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator, model_validator

from blogkit.core.styles import STYLE_PRESETS


class BlogProfile(BaseModel):
    """One blog's full configuration + customization surface."""

    model_config = {"frozen": True, "extra": "forbid"}

    # --- identity ---
    slug: str = Field(pattern=r"^[a-z0-9_]+$")
    name: str
    blog_id: str
    run_group: int = 1
    api_key_env: str = "GEMINI_API_KEY"

    # --- editorial voice ---
    persona: str
    persona_brief: str = ""
    # Per-blog personality knobs (all optional; empty = rely on the shared
    # prompt's dynamic adaptation). These sharpen each blog's distinct identity.
    tone: str = ""                                       # e.g. "contrarian, punchy"
    voice_traits: list[str] = Field(default_factory=list)  # concrete style directives
    flow: str = ""                                       # pacing / structure guidance
    banned_phrases: list[str] = Field(default_factory=list)  # extra per-blog bans
    niche_keyword: str = "business"
    rss_queries: list[str] = Field(min_length=1)
    tags: list[str] = Field(default_factory=list)

    # --- visual identity ---
    featured_image: bool = True
    # Names from STYLE_PRESETS. Empty list = the blog may use the whole catalog.
    image_styles: list[str] = Field(default_factory=list)

    # --- publish ---
    draft: bool = False
    # Pipeline on/off switch. Disabled blogs are skipped by `run --all` /
    # `--group` (and can also be toggled at runtime via BLOGKIT_DISABLE).
    # A disabled blog may be "staged" with a TODO blog_id until its Blogger
    # site exists; an *enabled* blog must have a real blog_id.
    enabled: bool = True

    # --- analytics feedback (opt-in) ---
    # Search Console property URL (e.g. "https://aiinfra.blogspot.com/"). When
    # set (and GSC creds available), the keyword roulette is biased toward
    # themes already earning impressions/clicks. Empty = feature dormant.
    analytics_site: str = ""

    @model_validator(mode="after")
    def _enabled_needs_real_blog_id(self) -> BlogProfile:
        # Staged (disabled) blogs may carry a placeholder/TODO id; an enabled
        # blog must point at a real Blogger blog_id.
        if self.enabled:
            bid = self.blog_id
            if not bid or bid.startswith("[") or bid.upper().startswith("TODO"):
                raise ValueError(
                    f"enabled blog {self.slug!r} needs a real blog_id (got {bid!r}); "
                    "set enabled=False to stage it without one"
                )
        return self

    @field_validator("image_styles")
    @classmethod
    def _styles_known(cls, v: list[str]) -> list[str]:
        unknown = [s for s in v if s not in STYLE_PRESETS]
        if unknown:
            raise ValueError(
                f"unknown image styles {unknown}; valid names: {sorted(STYLE_PRESETS)}"
            )
        return v

    def style_pool(self) -> list[str]:
        """Resolved preset strings this blog may draw from (all if none set)."""
        names = self.image_styles or list(STYLE_PRESETS)
        return [STYLE_PRESETS[n] for n in names]
