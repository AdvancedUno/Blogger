"""The per-blog profile schema.

A ``BlogProfile`` is the single source of truth for one blog: its identity,
editorial voice, source queries, image identity, and publish settings. Profiles
are validated at load time (pydantic), so a malformed blog fails fast instead of
producing a broken post.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

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
    niche_keyword: str = "business"
    rss_queries: list[str] = Field(min_length=1)
    tags: list[str] = Field(default_factory=list)

    # --- visual identity ---
    featured_image: bool = True
    # Names from STYLE_PRESETS. Empty list = the blog may use the whole catalog.
    image_styles: list[str] = Field(default_factory=list)

    # --- publish ---
    draft: bool = False

    @field_validator("blog_id")
    @classmethod
    def _blog_id_real(cls, v: str) -> str:
        if not v or v.startswith("["):
            raise ValueError(f"blog_id is missing or a placeholder: {v!r}")
        return v

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
