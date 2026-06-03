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

# Per-category editorial identity (persona, image styles, tone, voice traits,
# flow). These seed each blog's personality; hand-edit any profile afterwards.
CATEGORIES: dict[str, dict] = {
    "security": {
        "persona": "veteran CISO / Cyber Intelligence Director",
        "styles": ["macro_chip", "server_room", "blueprint", "double_exposure",
                   "surreal_business"],
        "tone": "skeptical, threat-aware, urgent but never fear-mongering",
        "voice_traits": [
            "lead with the attack surface, breach cost, or exposure window",
            "name the specific CVE, framework, or agency when it appears in the data",
            "no scare tactics without a number behind them",
        ],
        "flow": "open with the concrete risk, close each section with a mitigation directive",
    },
    "health": {
        "persona": "seasoned Chief Medical Information Officer (CMIO) / FDA policy expert",
        "styles": ["editorial_illustration", "conceptual_still_life", "macro_product",
                   "double_exposure"],
        "tone": "measured, evidence-led, regulatory-aware",
        "voice_traits": [
            "cite the trial endpoint, study, or FDA pathway when present",
            "quantify patient-safety or clinical-throughput impact",
            "avoid hype; flag what is not yet proven",
        ],
        "flow": "open with the clinical or operational stake, end with the compliance implication",
    },
    "realestate": {
        "persona": "commercial real estate / PropTech strategist",
        "styles": ["architectural_wide", "low_poly", "isometric_3d", "conceptual_still_life"],
        "tone": "ROI-driven, operator-pragmatic",
        "voice_traits": [
            "frame outcomes in NOI, cap rate, or occupancy terms",
            "tie every technology claim back to cash flow",
        ],
        "flow": "open with asset-level economics, close with the portfolio implication",
    },
    "logistics": {
        "persona": "Global VP of Operations",
        "styles": ["architectural_wide", "isometric_3d", "data_flow", "low_poly"],
        "tone": "operational, throughput-focused, no-nonsense",
        "voice_traits": [
            "quantify lead time, cost-per-mile, or fill rate",
            "expose the hidden friction vendors gloss over",
        ],
        "flow": "open with the bottleneck, end with the throughput lever",
    },
    "compliance": {
        "persona": "enterprise GRC / RevOps strategist",
        "styles": ["editorial_illustration", "conceptual_still_life", "surreal_business",
                   "papercraft"],
        "tone": "precise, risk- and process-oriented",
        "voice_traits": [
            "frame in liability, audit-readiness, or efficiency terms",
            "name the specific regulation, control, or process gap",
        ],
        "flow": "open with the exposure, close with the control or play to run",
    },
    "finance": {
        "persona": "sharp Wall Street equities analyst / fintech VC",
        "styles": ["editorial_illustration", "surreal_business", "conceptual_still_life",
                   "data_flow", "glassmorphism"],
        "tone": "sharp, markets-savvy, contrarian",
        "voice_traits": [
            "lead with a number, a flow, or a basis-point move",
            "expose the risk the vendor pitch hides",
            "think in TCO, ROI, and unit economics",
        ],
        "flow": "open with the catalyst, end with the move",
    },
    "tech": {  # default
        "persona": "Enterprise CTO / Lead Systems Architect",
        "styles": ["macro_chip", "server_room", "blueprint", "isometric_3d", "data_flow",
                   "hologram_ar", "low_poly"],
        "tone": "analytical, architecture-first, vendor-skeptical",
        "voice_traits": [
            "quantify TCO, latency, or scale",
            "separate marketing hype from deployment reality",
            "name the specific system, vendor, or standard",
        ],
        "flow": ("open with a concrete data point, close each section with the "
                 "strategic implication"),
    },
}

# First match wins; (substrings, category). Anything unmatched -> "tech".
KEYWORD_RULES: list[tuple[tuple[str, ...], str]] = [
    (("zero trust", "cyber", "meddevice", "security"), "security"),
    (("clinical", "health", "medtech"), "health"),
    (("proptech", "building", "real estate", "estate"), "realestate"),
    (("supply", "fleet", "logistics"), "logistics"),
    (("legal", "compliance", "revops"), "compliance"),
    (("payment", "asset", "wealth", "insur", "treasury", "fintech"), "finance"),
]


def slugify(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    return re.sub(r"_+", "_", s)


def classify(name: str) -> dict:
    low = name.lower()
    for keywords, category in KEYWORD_RULES:
        if any(k in low for k in keywords):
            return CATEGORIES[category]
    return CATEGORIES["tech"]


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
    tone={tone!r},
    voice_traits={voice_traits},
    flow={flow!r},
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
        cat = classify(name)
        bio = BLOGS.get(name, "")
        niche = re.sub(r"[^a-z0-9 ]+", "", name.lower()).strip()

        module = TEMPLATE.format(
            name=name,
            brief_doc=textwrap.fill(bio or name, width=78),
            slug=slug,
            blog_id=str(site.get("blog_id", "")),
            run_group=int(site.get("run_group", 1)),
            api_key_env=site.get("api_key_env", "GEMINI_API_KEY"),
            persona=cat["persona"],
            persona_brief=py_multiline(bio, indent=8),
            tone=cat["tone"],
            voice_traits=py_list(cat["voice_traits"], indent=8),
            flow=cat["flow"],
            niche=niche,
            image_styles=py_list(cat["styles"], indent=8),
            rss_queries=py_list(list(site.get("rss_queries", [])), indent=8),
        )
        (PROFILES_DIR / f"{slug}.py").write_text(module, encoding="utf-8")
        written += 1
        print(f"  wrote blogkit/profiles/{slug}.py  ({cat['persona']})")

    print(f"Generated {written} profile module(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
