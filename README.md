# blogkit

Automated, profile-driven multi-blog content pipeline:
**fetch news → generate an analytical post (Gemini) → generate a featured image
(Hugging Face FLUX, hosted on GitHub + jsDelivr) → publish to Blogger.**

One shared, tested engine; each blog is a small editable profile. Adding a blog
is dropping in a profile module — no engine changes.

## Architecture

```
blogkit/
  core/
    fetcher.py      Google News RSS (keyword roulette + fallback)
    sourcetext.py   best-effort full-text grounding: resolves Google News links
                    to the publisher article and feeds real article text to the
                    model (instead of headline stubs)
    generator.py    Gemini text; shared SEO prompt + per-blog persona voice-lock
    imager.py       image gen (HF FLUX or Vertex Imagen) -> GitHub Contents API -> jsDelivr CDN URL
    publisher.py    Blogger v3 REST API + Mail2Blogger SMTP fallback
    pipeline.py     run_profile(): fetch -> generate -> image -> publish
    styles.py       16 named image-style presets (the catalog)
  profiles/
    base.py         BlogProfile (pydantic, validated at load)
    registry.py     auto-discovers profile modules
    <slug>.py       one profile per blog (persona, queries, styles, toggles)
  cli.py            `python -m blogkit ...`
tools/generate_profiles.py   bootstrap profiles from config.yaml + build_themes
tests/              pytest suite (ruff + mypy + pytest in CI)
pyproject.toml      package + deps + tool config
```

The engine is profile-driven: `core/pipeline.run_profile(profile, publish_method)`
reads everything it needs from a `BlogProfile`.

## Install

```bash
pip install -e ".[dev]"     # package + ruff/mypy/pytest
```

## Usage

```bash
python -m blogkit list                      # show all blog profiles
python -m blogkit doctor                     # preflight: validate secrets/config
python -m blogkit run --blog zero_trust_enterprise
python -m blogkit run --group 2             # all blogs in run_group 2
python -m blogkit run --all                 # every blog (default)
python -m blogkit run --all --dry-run        # generate + assemble, do NOT publish
python -m blogkit run --group 2 --publish-method email   # 429-day fallback
python -m blogkit selftest-image --blog zero_trust_enterprise  # image path only
```

**Content integrity & SEO (automatic):** a cross-blog de-dup ledger skips source
articles already used network-wide (duplicate-content guard), each post gets
JSON-LD (Article + FAQPage) and a real "Sources" citation list, and each blog
carries its own tone/voice/flow. Before generation, source links are resolved to
the real publisher articles and ~1,100 chars of actual article text replace the
Google News headline stubs (core/sourcetext.py — the model grounds claims in
real reporting, not twelve words). Per piece, the structure plan also rotates
the **headline shape** (flat claim / question / number / how / tension — no
default "Topic: Subtitle" colon titles), occasionally closes on a question to
the reader (comment engagement), and leans ~40% of posts evergreen so search
traffic compounds. The pre-publish quality gate rejects thin/near-duplicate
posts AND machine-fingerprint slips: AI-tell phrases, "it's not X, it's Y"
negative parallelism, and em-dash overuse. A run posts a digest to
`RUN_WEBHOOK_URL` (Discord/Slack) if set.

## Adding / customizing a blog

Create `blogkit/profiles/<slug>.py`:

```python
from blogkit.profiles.base import BlogProfile

PROFILE = BlogProfile(
    slug="my_new_blog",
    name="My New Blog",
    blog_id="1234567890",
    run_group=1,
    api_key_env="GEMINI_API_KEY_1",
    persona="veteran CISO / Cyber Intelligence Director",
    persona_brief="One-paragraph editorial bio that grounds the voice.",
    niche_keyword="zero trust security",
    image_styles=["macro_chip", "server_room", "blueprint"],  # names from styles.py
    rss_queries=["Zero Trust Network Access", "SASE rollout", ...],
    featured_image=True,
    draft=False,
)
```

The registry discovers it automatically; it's validated at load (real `blog_id`,
known style names, ≥1 query). Run `python -m blogkit run --blog my_new_blog`.

To go fully custom, a profile can later carry its own full prompt override
(hook already present in `generator.generate_post(system_instruction=...)`).

## Environment / secrets (GitHub Actions)

| Var | Purpose |
|---|---|
| `GEMINI_API_KEY`, `GEMINI_API_KEY_1..10` | Gemini text (per-blog routing) |
| `GEMINI_MODEL` | optional model override |
| `GOOGLE_CLIENT_ID/SECRET`, `GOOGLE_REFRESH_TOKEN` | Blogger v3 API auth |
| `HF_API_TOKEN` | hf image provider: Hugging Face image gen (Inference Providers permission) |
| `ASSETS_REPO_PAT` | fine-grained PAT, `contents:write` on the image-hosting repo (both providers) |
| `SMTP_USER`, `SMTP_PASSWORD`, `BLOGGER_SECRET_EMAIL` | email fallback |
| `RUN_WEBHOOK_URL` | optional — per-run digest to Discord/Slack |
| `GSC_CLIENT_ID/SECRET/REFRESH_TOKEN` | optional — Search Console feedback (webmasters.readonly scope); falls back to `GOOGLE_*` |

Repository **variables** (Settings → Secrets and variables → Actions → *Variables*,
not Secrets — so the workflow can branch on them):

| Var | Purpose |
|---|---|
| `IMAGE_PROVIDER` | image engine: empty/`hf` (default, free) or `vertex` (Google Cloud Imagen, paid) |
| `GCP_PROJECT` | vertex: project id (the auth step also exports it automatically in CI) |
| `VERTEX_LOCATION` | vertex: region (default `us-central1`) |
| `VERTEX_IMAGE_MODEL` | vertex: model id (default `imagen-4.0-fast-generate-001`) |

Vertex **secrets** (only when `IMAGE_PROVIDER=vertex`):

| Secret | Purpose |
|---|---|
| `GCP_WIF_PROVIDER` | Workload Identity provider resource (`projects/NUM/locations/global/workloadIdentityPools/POOL/providers/PROV`) |
| `GCP_SERVICE_ACCOUNT` | service-account email the workflow impersonates |
| `GCP_SA_KEY` | optional — inline SA JSON, only if your org permits long-lived keys |

Images are generated once at publish time and embedded as an immutable jsDelivr
CDN URL (real `https`, so Blogger homepage thumbnails work; bodies stay light).

**Image provider:** `IMAGE_PROVIDER` empty/`hf` (default) uses Hugging Face
FLUX.1-schnell (free, rate-limited). `IMAGE_PROVIDER=vertex` uses Google Cloud
Vertex AI Imagen (bills GCP credits, no cold-start, higher quality). Switching is
a one-line variable change — hosting and everything downstream are identical.

**Vertex auth is keyless** (works with "Secure by Default" orgs that block SA
keys): locally, `gcloud auth application-default login` + `GCP_PROJECT`; in CI,
Workload Identity Federation via the `google-github-actions/auth` step already
wired into the workflows (needs `id-token: write`, granted at the job level).
Verify either path with `python -m blogkit selftest-image` (respects
`IMAGE_PROVIDER`).

## Workflows

- `.github/workflows/ci.yml` — ruff + mypy + pytest on push/PR.
- `.github/workflows/daily_blogger.yml` — scheduled `python -m blogkit run`.
- `.github/workflows/email_fallback_run.yml` — manual email-fallback run.

**AdSense setup:** `python setup_pages.py` creates About/Contact/Privacy/Terms
pages on every blog; `python setup_pages.py --ads-txt pub-XXXX` prints the
ads.txt line to paste into each blog's custom ads.txt.

**Analytics feedback (opt-in):** set a profile's `analytics_site` to its Search
Console property URL; with GSC creds present, the keyword roulette is biased
toward themes already earning clicks/impressions.

`config.yaml` is retained only as the bootstrap source for
`tools/generate_profiles.py`; it is no longer read at runtime.
