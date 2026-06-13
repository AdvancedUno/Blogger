# Improvements & Future Steps

Editorial/engineering review, 2026-06-12. State at time of writing: 40 profiles
(20 enabled, 4 run groups), source-text grounding + headline rotation +
AI-fingerprint gate just landed. Tests 158 passing.

Priorities: **P0** = do before/with the next few scheduled runs. **P1** = next
2-4 weeks. **P2** = after traffic data exists. Each item lists why it matters
and the concrete first step.

---

## P0 — operational correctness

### 1. Raise the daily workflow timeout
Source-text grounding adds up to ~45s per blog. Worst case for 20 enabled
blogs: 20 × (45s enrich + ~15s generate + 30s inter-site sleep) ≈ **30+ min
beyond the old baseline**, against a 70-minute `timeout-minutes` in
`daily_blogger.yml`. A few 65s Gemini quota retries on top and the run gets
auto-cancelled mid-network, publishing some blogs and not others.
**Step:** bump `timeout-minutes: 70` → `120`. One line, zero risk.

### 2. Activate the dormant `site_url` / `analytics_site` fields (currently 0/20)
Two shipped features are running at zero activation because no profile fills
these fields:
- `site_url` empty → every post omits the WebSite + Organization +
  BreadcrumbList JSON-LD nodes (`core/seo.py` builds them only when a URL is
  known).
- `analytics_site` empty → the Search Console feedback loop
  (`core/analytics.py`, keyword roulette biased toward queries already earning
  impressions) is dormant on every blog.

**Step:** fill both fields on the 20 enabled profiles. The URLs don't need to
be typed by hand: the Blogger API returns each blog's URL
(`blogs.get(blogId)`), so `python -m blogkit doctor` (or a one-off
`tools/fill_site_urls.py`) can fetch and print ready-to-paste profile patches.
Then register each property in Search Console (one-time manual step) so
`analytics_site` has data to read.

### 3. Watch the first enriched scheduled runs
`sourcetext.py`'s new-token resolver uses an unofficial Google endpoint
(`batchexecute`). It degrades silently by design — which also means it can
*break* silently and quietly return the network to headline-only grounding.
**Step:** see P1-4 (digest observability). Until that lands, skim the Actions
log for the `Pulled full article text for N/M sources` line for a few days.
Healthy is N≥3 of 6 on most blogs.

---

## P1 — quality flywheel & de-fingerprinting

### 4. Run-digest observability for the new quality machinery
The webhook digest (`core/notify.py`) reports only ok/fail per blog. The three
numbers that now matter most are invisible: **enrichment rate** (sourcetext
health), **quality-gate rejection rate** (prompt drift), and **which gate rule**
fired. A week of silent gate rejections = a week of missed posts; a silent
enrichment collapse = quality regression with no alarm.
**Step:** thread `(enriched_n, total_n)` and the gate's reason string into
`run_profile`'s return info (the strings already exist), and add a one-line
summary to `format_digest`, e.g. `grounding 14/20 blogs ≥3 sources; gate
rejected 1 (em-dash overuse)`.

### 5. Break the metronomic publishing cadence
All 20 blogs publish at exactly 14:00 UTC, every day, forever. A perfectly
periodic archive across a 20-blog network is a programmatic signature visible
to anyone (or any classifier) that sorts by timestamp — and post-per-day-
forever is the textbook profile of scaled content.
**Step:** deterministic per-blog jitter, seeded from `slug + date`:
(a) each blog *skips* ~1-2 days per week (`hash(slug+date) % 7 < 2 → skip`),
(b) per-blog sleep offset spreads publishes over a ~2-hour window instead of a
burst. Both are ~15 lines in `cli.py`/`pipeline.py`, no infra change. Bonus:
fewer posts/day also eases daily Blogger write quotas and Gemini free-tier
pressure.

### 6. Numeric-claim cross-check (anti-hallucination backstop)
Grounded source text reduced hallucination pressure, but nothing *verifies*
that figures in the post trace to the sources. The craft laws ask the model to
flag invented numbers as illustrative; there is no enforcement.
**Step:** in `core/quality.py`, extract salient numerals from the post
(dollar amounts, percentages, 4+ digit figures) and check each appears in the
concatenated source summaries OR sits within ~12 words of an illustrative
marker ("representative", "typical", "illustrative", "on the order of",
"might", "consider a"). Start as a **logged warning only** for 2 weeks to
calibrate false-positive rate, then promote to a gate rule.

### 7. Contextual internal links (not just the footer list)
"Related from this blog" is a footer list — crawlable, but weak. The strongest
cheap on-page SEO lever still unused is **in-body contextual links with
descriptive anchors** to the blog's own prior posts.
**Step:** the ledger already stores each blog's recent (title, url). After
generation, scan the post body for the first natural occurrence of a
significant keyword overlap with a prior post's title and wrap it in a link
(max 1-2 per post, never inside headings/blockquotes). Pure HTML transform in
`core/enrich.py`, fully testable.

### 8. Hub-and-spoke evergreen pillars
Every post is news-seeded; the ~40% evergreen *lean* helps decay but the
network still has no cornerstone pages for its head terms ("what is carbon
accounting software", "kubernetes cost allocation guide"). Hubs that spokes
link to are how small sites consolidate topical authority.
**Step:** per blog, one pillar post per month: a `pillar` format whose topic
comes from the profile's `niche_keyword` rather than the news roulette, and
whose URL the contextual-linking pass (item 7) then prefers as a link target.

---

## P2 — after traffic data exists

### 9. Close the loop on headline shapes and formats
Headline shapes and formats rotate blind. Once Search Console properties are
registered (P0-2), CTR-by-page is available — and the ledger knows which
shape/format every post used (record `headline_style` + format name at publish
time; two fields in `Ledger.record`, do this **now** so the data exists later).
**Step (later):** monthly job correlates GSC CTR with shape/format per blog
and tilts the rotation weights toward winners. Keep every shape ≥10% so the
archive never re-converges on one pattern.

### 10. Model-as-judge second pass on gate-failures only
The quality gate is heuristic (counts, density, Jaccard). A cheap second
Gemini call with a scoring rubric (specificity, information gain, voice match)
would catch what counters can't — but burning free-tier quota on every post is
wasteful.
**Step:** run the judge **only** when a post fails the gate (decide
regenerate-vs-drop) or on a ~10% random sample (weekly editorial report to the
digest webhook). Strictly bounded extra quota.

### 11. Topic-list refresh cadence
`rss_queries` are static snapshots of mid-2026 vocabulary. B2B niches rotate
vocabulary every couple of quarters; stale queries quietly degrade the news
pool until blogs start skipping.
**Step:** quarterly, run a small script that takes each blog's GSC top queries
plus its existing list, asks Gemini for 5 candidate additions/retirements per
blog, and opens a PR (human reviews; queries stay curated, not auto-mutated).

### 12. AdSense readiness checklist (manual, once per blog)
Before applying per blog: ~30+ indexed posts, filled About/Contact/Privacy
pages (`setup_pages.py` exists — verify it ran on all 20), custom `ads.txt`
in place, Search Console verified, and **3+ months of archive** on that blog.
Apply with the oldest, highest-traffic blogs first; a rejection on a thin blog
creates review friction for the rest of the account. Don't batch-apply.

---

## Explicitly not worth doing

- **Fabricated named human authors for E-E-A-T.** Organization bylines are
  honest and safe; invented persons with fake bios are the exact pattern
  Google's site-reputation work targets. Revisit only if a real author joins.
- **Hard subscribe CTAs / popups.** Blogger has no native email capture worth
  gating content for; the reader-question close already does the engagement
  work without the boilerplate smell.
- **Auto-regeneration loops on gate failure** (beyond one judge-arbitrated
  retry). Multiplies quota burn and tends to converge on blander prose that
  games the counters.
- **More blogs.** 20 dormant profiles already exist; activating them before
  the flywheel (P0-2, P1-4) runs would multiply scaled-content risk with zero
  feedback. Quality per blog, then breadth.

## Metrics that decide everything above

| Metric | Source | Healthy signal |
|---|---|---|
| Source-grounding rate | run digest (P1-4) | ≥3/6 sources enriched on most blogs |
| Gate rejection rate | run digest (P1-4) | <5% of generations, stable |
| Indexed pages / blog | Search Console | steadily rising, no mass de-indexing |
| CTR by headline shape | GSC + ledger (P2-9) | shapes differentiate; rotate toward winners |
| Returning-visitor share | (optional) Blogger stats | rising = the voice work is landing |
