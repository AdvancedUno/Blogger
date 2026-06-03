"""One-shot bootstrap: emit blogkit/profiles/<slug>.py for every blog.

Seeds each profile from data that already exists in the repo:
  - persona bio  <- build_themes.BLOGS
  - blog_id / run_group / api_key_env / rss_queries <- config.yaml
  - persona voice + image-style affinity <- keyword rules below

The generated modules are meant to be hand-edited afterwards — this just gives
every blog a sensible, on-theme starting point instead of 20 blank files.

Run from the repo root:  python tools/generate_profiles.py
"""

from __future__ import annotations

import re
import sys
import textwrap
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from build_themes import BLOGS  # noqa: E402  (persona bios, name -> bio)

PROFILES_DIR = ROOT / "blogkit" / "profiles"

# (substring matched against the blog name, persona voice, ordered style names).
# First match wins, so put the more specific rules first.
RULES: list[tuple[tuple[str, ...], str, list[str]]] = [
    (
        ("zero trust", "cyber", "meddevice", "security"),
        "veteran CISO / Cyber Intelligence Director",
        ["macro_chip", "server_room", "blueprint", "double_exposure", "surreal_business"],
    ),
    (
        ("clinical", "health", "medtech"),
        "seasoned Chief Medical Information Officer (CMIO) / FDA policy expert",
        ["editorial_illustration", "conceptual_still_life", "macro_product", "double_exposure"],
    ),
    (
        ("proptech", "building", "real estate", "estate"),
        "commercial real estate / PropTech strategist",
        ["architectural_wide", "low_poly", "isometric_3d", "conceptual_still_life"],
    ),
    (
        ("supply", "fleet", "logistics"),
        "Global VP of Operations",
        ["architectural_wide", "isometric_3d", "data_flow", "low_poly"],
    ),
    (
        ("legal", "compliance", "revops"),
        "enterprise GRC / RevOps strategist",
        ["editorial_illustration", "conceptual_still_life", "surreal_business", "papercraft"],
    ),
    (
        ("payment", "asset", "wealth", "insur", "treasury", "fintech"),
        "sharp Wall Street equities analyst / fintech VC",
        ["editorial_illustration", "surreal_business", "conceptual_still_life", "data_flow",
         "glassmorphism"],
    ),
]
# Default: enterprise tech / infrastructure.
DEFAULT_PERSONA = "Enterprise CTO / Lead Systems Architect"
DEFAULT_STYLES = ["macro_chip", "server_room", "blueprint", "isometric_3d", "data_flow",
                  "hologram_ar", "low_poly"]


def slugify(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    return re.sub(r"_+", "_", s)


def classify(name: str) -> tuple[str, list[str]]:
    low = name.lower()
    for keywords, persona, styles in RULES:
        if any(k in low for k in keywords):
            return persona, styles
    return DEFAULT_PERSONA, DEFAULT_STYLES


def py_multiline(value: str, indent: int) -> str:
    """Render a long string as a parenthesized, wrapped, implicitly-concatenated
    literal for readability in the generated module."""
    pad = " " * indent
    chunks = textwrap.wrap(value, width=72) or [""]
    if len(chunks) == 1:
        return repr(chunks[0])
    # Implicit string concatenation drops the line break, so keep a trailing
    # space on every chunk except the last to preserve word boundaries.
    chunks = [c + " " for c in chunks[:-1]] + [chunks[-1]]
    body = "\n".join(f"{pad}{c!r}" for c in chunks)
    return f"(\n{body}\n{' ' * (indent - 4)})"


def py_list(items: list[str], indent: int) -> str:
    if not items:
        return "[]"
    pad = " " * indent
    body = "\n".join(f"{pad}{item!r}," for item in items)
    return f"[\n{body}\n{' ' * (indent - 4)}]"


TEMPLATE = '''"""Profile: {name}

{brief_doc}
"""

from blogkit.profiles.base import BlogProfile

PROFILE = BlogProfile(
    slug={slug!r},
    name={name!r},
    blog_id={blog_id!r},
    run_group={run_group},
    api_key_env={api_key_env!r},
    persona={persona!r},
    persona_brief={persona_brief},
    niche_keyword={niche!r},
    image_styles={image_styles},
    featured_image=True,
    draft=False,
    rss_queries={rss_queries},
    tags=[],
)
'''


def main() -> int:
    cfg = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
    sites = cfg.get("blogger_sites") or []
    written = 0
    for site in sites:
        name = site["name"]
        slug = slugify(name)
        persona, styles = classify(name)
        bio = BLOGS.get(name, "")
        niche = re.sub(r"[^a-z0-9 ]+", "", name.lower()).strip()

        module = TEMPLATE.format(
            name=name,
            brief_doc=textwrap.fill(bio or name, width=78),
            slug=slug,
            blog_id=str(site.get("blog_id", "")),
            run_group=int(site.get("run_group", 1)),
            api_key_env=site.get("api_key_env", "GEMINI_API_KEY"),
            persona=persona,
            persona_brief=py_multiline(bio, indent=8),
            niche=niche,
            image_styles=py_list(styles, indent=8),
            rss_queries=py_list(list(site.get("rss_queries", [])), indent=8),
        )
        (PROFILES_DIR / f"{slug}.py").write_text(module, encoding="utf-8")
        written += 1
        print(f"  wrote blogkit/profiles/{slug}.py  ({persona})")

    print(f"Generated {written} profile module(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
