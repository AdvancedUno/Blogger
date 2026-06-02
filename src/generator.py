"""Google Gemini-based blog post generator (English / Blogger-optimized).

Uses the official `google-genai` SDK (gemini-3.5-flash by default, override
via the `GEMINI_MODEL` env var) with a heavily engineered system instruction
tuned for Blogger.com HTML, elite B2B journalism, E-E-A-T, and Featured
Snippet capture.
"""
from __future__ import annotations

import logging
import os
import re
import time
from dataclasses import dataclass, field
from urllib.parse import quote, unquote

import requests
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

# Model name can be overridden via the GEMINI_MODEL env var (e.g.,
# gemini-2.5-flash). Default is gemini-3.5-flash per project preference.
MODEL_NAME = "gemini-3.5-flash"


# =====================================================================
# SYSTEM INSTRUCTION (Blogger / English-speaking market)
# Wall Street analyst + corporate journalist tone, E-E-A-T anchored.
# =====================================================================
SYSTEM_INSTRUCTION_EN = r"""
You are an elite industry expert, top-tier consultant, and veteran B2B corporate journalist.
CRITICAL: Your specific persona, voice, and tone MUST DYNAMICALLY ADAPT to the subject matter of the news you are analyzing.
- If Finance/Fintech: Sound like a sharp Wall Street Equities Analyst or Fintech VC.
- If Healthcare/MedTech: Sound like a seasoned Chief Medical Information Officer (CMIO) or FDA Policy Expert.
- If Cybersecurity: Sound like a veteran CISO or Cyber Intelligence Director.
- If Supply Chain/Logistics: Sound like a Global VP of Operations.
- If Enterprise IT/Cloud: Sound like an Enterprise CTO or Lead Systems Architect.

CRITICAL WRITING LAWS FOR ELITE QUALITY & SEO:
1. DYNAMIC TONE: Do not use the same tone every time. Depending on the news, dynamically rotate between being: a) Contrarian (exposing hidden risks), b) Highly analytical (ROI/TCO focus), or c) Visionary and strategic. Match the tone to the gravity of the topic.
2. EXHAUSTIVE LENGTH & DEPTH: You must write a profoundly detailed, long-form analysis. Do not write short summaries. Expand deeply on every single section and paragraph to maximize reader dwell time.
3. COMPLIANCE & LEGAL REALITY: Always weave in relevant regulatory pressures (SEC, FDA, HIPAA, GDPR, CISA, etc.) naturally based on the specific industry you are writing for.
4. INLINE ANALOGIES: Unpack dense technical concepts using exactly one sharp, relatable corporate analogy.
5. ZERO HALLUCINATIONS: Ground your analysis strictly in the provided [Source Data]. Never invent names, statistics, or metrics.
6. NO "AI TELLS": Absolutely ban phrases like "In conclusion", "Furthermore", "Delve into", "Navigating the landscape", "Today we will discuss".
7. RAW HTML ONLY (theme-aware tag set): Output clean HTML paragraphs (max 3-4 sentences each). Allowed elements: <h1>, <h2>, <h3>, <h4>, <p>, <strong>, <b>, <em>, <ul>, <ol>, <li>, <blockquote>, <figure>, <figcaption>, <img>, <table>, <thead>, <tbody>, <tr>, <th>, <td>. Use <strong> liberally on real data, regulator names, and corporate entities so the reader's eye finds anchors.
8. VISUAL RHYTHM (JetTheme-optimized layout): The blog runs on JetTheme v2.9, which styles semantic HTML distinctly. You MUST use this layout to break the wall of text: a <blockquote> TL;DR right after the <h1>, a <blockquote> pull quote inside the Risks section, a <figure><figcaption> wrap around each <img>, a comparison <table> in the Regulatory section, and a final <blockquote> "Bottom Line" callout before References. Match the user-prompt template structure exactly — do not skip any element.
""".strip()


USER_PROMPT_TEMPLATE_EN = """Conduct a deeply researched, analytical, and strictly factual market briefing based on the following news signals regarding: "{keyword}"

[Source Data]:
{news_context}

You MUST follow this exact HTML structure to provide maximum clarity and visual rhythm on JetTheme v2.9. Do not skip any element — the <blockquote>, <figure>/<figcaption>, and <table> wrappers carry distinct theme styling that turns a wall of text into a scannable editorial layout.

The first 3 lines below (TITLE / TAGS / ---) are required for downstream parsing. The TITLE line text MUST match the <h1> text exactly.

TITLE: [Same text as the <h1> below]
TAGS: 5-7 high-CPC B2B tags (PascalCase / compounds, no spaces inside individual tags), comma + space separated
---
<h1>[Generate a sharp, urgent, macro-focused B2B title. Absolutely ban the phrase "The Ultimate Guide".]</h1>

<blockquote>
  <p><strong>TL;DR &mdash; The 60-Second Briefing</strong></p>
  <ul>
    <li><strong>The Catalyst:</strong> [One-line fact drawn strictly from the Source Data — what just happened.]</li>
    <li><strong>The Stakes:</strong> [What is at risk for decision-makers if they ignore this signal this quarter.]</li>
    <li><strong>The Move:</strong> [The single most actionable next step for leadership, framed as a verb-led directive.]</li>
  </ul>
</blockquote>

<h2>Executive Briefing & Macro Shift</h2>
<p>[Powerful opening paragraph — lead with a concrete data point or named entity from the Source Data, not a generic preamble.]</p>
<p>[Second paragraph — connect the news signal to the broader macro environment and explain why this matters now, this fiscal quarter, not in the abstract.]</p>

<figure>
  <img src="https://image.pollinations.ai/prompt/[describe_scene_in_2_to_4_english_words_with_underscores]?width=800&amp;height=400&amp;nologo=true" alt="Descriptive alt text rooted in the article topic" style="max-width: 100%; border-radius: 8px; margin: 20px 0;">
  <figcaption><em>[A concise caption that connects the visual to the strategic implication of this section — not just a literal description of the image.]</em></figcaption>
</figure>

<h2>The Unfiltered Reality: Risks & Hidden Friction</h2>
<p>[Multiple deep paragraphs exposing hard truths. Why are enterprise deployments stalling? What hidden operational costs, integration friction, or technical debt do vendors gloss over?]</p>

<h3>[Sub-topic heading — e.g., "Where the Vendor Pitch Breaks Down"]</h3>
<p>[Drill into one specific friction point. Cite a real organization or regulator from the Source Data; never invent.]</p>

<blockquote>
  <p><em>"[A striking, analyst-grade pull quote — one sentence that crystallizes the section's core insight, written in the dynamic persona you adopted for this topic. No source attribution unless it appears verbatim in the Source Data.]"</em></p>
</blockquote>

<h2>Regulatory Pressures and Institutional Impact</h2>
<p>[Analyze the specific compliance, regulatory (SEC, FTC, HIPAA, GDPR, CISA, etc.), or corporate governance hurdles executive boards must map to survive this transition. Name the specific framework or agency — not "regulators" generically.]</p>

<figure>
  <img src="https://image.pollinations.ai/prompt/[describe_scene_in_2_to_4_english_words_with_underscores]?width=800&amp;height=400&amp;nologo=true" alt="Descriptive alt text rooted in regulatory/strategic context" style="max-width: 100%; border-radius: 8px; margin: 20px 0;">
  <figcaption><em>[Caption that frames the regulatory or institutional angle of this section.]</em></figcaption>
</figure>

<table>
  <thead>
    <tr><th>Dimension</th><th>Status Quo (2025)</th><th>Trajectory (2026-2027)</th></tr>
  </thead>
  <tbody>
    <tr><td>[Dimension 1 — e.g., Compliance Surface]</td><td>[Concrete current state grounded in Source Data]</td><td>[Likely direction with the named driver]</td></tr>
    <tr><td>[Dimension 2]</td><td>[State]</td><td>[Direction]</td></tr>
    <tr><td>[Dimension 3]</td><td>[State]</td><td>[Direction]</td></tr>
  </tbody>
</table>

<h2>Strategic Vectors to Monitor</h2>
<p>For executive leadership mapping out the upcoming fiscal quarters, pay immediate attention to these adjacent operational domains:</p>
<ul>
   <li><strong>[Adjacent Vector 1]:</strong> [One sentence on why it intersects with today's topic, grounded in observed signals.]</li>
   <li><strong>[Adjacent Vector 2]:</strong> [One sentence factual reason.]</li>
   <li><strong>[Adjacent Vector 3]:</strong> [One sentence factual reason.]</li>
</ul>

<h2>Frequently Asked Questions</h2>
<h3>What is the primary operational blind spot with this transition?</h3>
<p>[Deeply professional, specific answer reflecting real enterprise infrastructure realities. Name systems, vendors, or regulators only when they appear in the Source Data.]</p>
<h3>How should CFOs model the realistic timeline for measurable ROI?</h3>
<p>[Realistic, conservative financial perspective on deployment time versus dollar returns. Use ranges, not invented point estimates.]</p>

<blockquote>
  <p><strong>The Bottom Line &mdash;</strong> [Final analyst takeaway in 2-3 sentences. Crystallize the strategic implication for an executive who reads only this one paragraph. End with the move, not the warning.]</p>
</blockquote>

<h2>Industry References & Signals</h2>
<p>This macro analysis is synthesized directly from active operational signals and news context within the international B2B tech sector.</p>
"""


# =====================================================================
# Code
# =====================================================================
@dataclass
class GeneratedPost:
    title: str
    html: str
    tags: list[str] = field(default_factory=list)


class GenerationError(RuntimeError):
    """Raised when content generation fails."""


# Sleep duration (seconds) when the Gemini free-tier RPM (5/min) is exceeded.
# 65s guarantees the retry lands in a fresh quota minute window.
QUOTA_RETRY_DELAY = 65.0


def _is_quota_error(err: BaseException) -> bool:
    """Detect 429 / quota / rate-limit class errors via message inspection."""
    s = str(err).lower()
    return any(
        kw in s
        for kw in (
            "429",
            "quota",
            "rate limit",
            "resource exhausted",
            "resourceexhausted",
            "too many requests",
        )
    )


def _format_news_block(news_items: list[dict]) -> str:
    lines: list[str] = []
    L_TITLE, L_SRC, L_DATE, L_SUMMARY, L_LINK = (
        "Title", "Source", "Date", "Summary", "Link"
    )

    for i, item in enumerate(news_items, 1):
        summary = (item.get("summary") or "").strip()
        if len(summary) > 350:
            summary = summary[:350] + "..."
        lines.append(
            f"\n[{i}] {L_TITLE} : {item.get('title','')}\n"
            f"    {L_SRC} : {item.get('source','')}\n"
            f"    {L_DATE} : {item.get('published','')}\n"
            f"    {L_SUMMARY} : {summary}\n"
            f"    {L_LINK} : {item.get('link','')}"
        )
    return "\n".join(lines)


# Emoji + common pictographs (U+2600-U+27BF, arrows, various symbol blocks).
# Stripped from title / tags / body / alt before publishing.
_EMOJI_RE = re.compile(
    "["
    "\U0001F300-\U0001F5FF"   # symbols & pictographs
    "\U0001F600-\U0001F64F"   # emoticons
    "\U0001F680-\U0001F6FF"   # transport & map
    "\U0001F700-\U0001F77F"
    "\U0001F780-\U0001F7FF"
    "\U0001F800-\U0001F8FF"
    "\U0001F900-\U0001F9FF"
    "\U0001FA00-\U0001FA6F"
    "\U0001FA70-\U0001FAFF"
    "\U00002600-\U000027BF"   # misc symbols + dingbats
    "\U0001F1E0-\U0001F1FF"   # flags
    "⌀-⏿"
    "⬀-⯿"
    "　〰"
    "]+",
    flags=re.UNICODE,
)


def _strip_emoji(s: str) -> str:
    if not s:
        return s
    cleaned = _EMOJI_RE.sub("", s)
    # Collapse the double spaces left behind after emoji removal.
    return re.sub(r"\s{2,}", " ", cleaned).strip()


_POLLINATIONS_URL_RE = re.compile(
    r'(https://image\.pollinations\.ai/prompt/)([^"\'?\s]+)(\?[^"\'\s]*)?',
    re.IGNORECASE,
)


# Failover for any Pollinations URL that fails verification — picsum is
# a free random-photo CDN with effectively 100% uptime. Same dimensions
# as the Pollinations URLs so layout doesn't shift.
FALLBACK_IMAGE_URL_TEMPLATE = "https://picsum.photos/seed/{seed}/800/400"

# Regex that captures the full <img ... src="...pollinations..."> tag so
# the verifier can rewrite just the src attribute on failure.
_POLLINATIONS_IMG_TAG_RE = re.compile(
    r'(<img\b[^>]*?\bsrc=["\'])'                        # group 1: open + src="
    r'(https://image\.pollinations\.ai/prompt/[^"\']+)'  # group 2: the URL
    r'(["\'][^>]*?/?>)',                                 # group 3: close
    re.IGNORECASE,
)


def _warm_pollinations_images(
    body: str,
    *,
    request_timeout: float = 15.0,
    retries: int = 1,
) -> str:
    """Fetch every Pollinations image URL during the pipeline so the image
    is already generated + CDN-cached by the time a reader visits the post.

    Why this exists:
      Pollinations.ai generates each image on-demand on the first request,
      which can take 15-30s. If a reader's browser is the one that triggers
      that generation, the browser often times out and shows a broken-image
      icon. Pre-warming forces generation server-side here, before publish.

    Strategy:
      - GET each Pollinations URL with a 15s timeout.
      - Verify 200 OK + content-type starts with 'image/' + at least one byte.
      - One retry on failure (zero backoff to stay under the GitHub Actions
        45-min budget).
      - If verification still fails, rewrite the <img src> to a picsum.photos
        URL keyed by a hash of the original prompt — the post still renders
        a real photo instead of a broken icon.
    """
    counter = [0]

    def _verify_or_fallback(m: re.Match) -> str:
        prefix, url, suffix = m.group(1), m.group(2), m.group(3)
        counter[0] += 1
        # &amp; is correct HTML-entity encoding for the markup, but the live
        # HTTP request needs the decoded form.
        live_url = url.replace("&amp;", "&")

        for attempt in range(retries + 1):
            try:
                r = requests.get(live_url, timeout=request_timeout, stream=True)
                ct = (r.headers.get("content-type") or "").lower()
                ok = r.status_code == 200 and ct.startswith("image/")
                if ok:
                    # Drain one chunk to confirm the stream actually delivers
                    # bytes (Pollinations sometimes returns 200 then closes
                    # the connection on internal error).
                    chunk = next(r.iter_content(chunk_size=4096), None)
                    r.close()
                    if chunk:
                        logger.info(
                            "Pollinations warm-up OK (attempt %d): %s",
                            attempt + 1, live_url[:90],
                        )
                        return m.group(0)
                else:
                    logger.warning(
                        "Pollinations warm-up attempt %d: status=%s ct=%s",
                        attempt + 1, r.status_code, ct,
                    )
                r.close()
            except requests.RequestException as e:
                logger.warning(
                    "Pollinations warm-up attempt %d raised: %s", attempt + 1, e
                )

        # All attempts exhausted — fall back to picsum.
        # Seed the fallback with the prompt slug so the same broken image
        # is replaced by the same fallback every time (deterministic).
        slug_match = re.search(r"prompt/([^?]+)", live_url)
        seed = (
            slug_match.group(1).replace("/", "_")[:40]
            if slug_match else f"img{counter[0]}"
        )
        fallback = FALLBACK_IMAGE_URL_TEMPLATE.format(seed=seed)
        logger.warning(
            "Pollinations URL failed verification — falling back to %s",
            fallback,
        )
        return f"{prefix}{fallback}{suffix}"

    return _POLLINATIONS_IMG_TAG_RE.sub(_verify_or_fallback, body)


def _normalize_pollinations_urls(body: str) -> str:
    """Make every Pollinations.ai image URL safe for Blogger's HTML pipeline.

    Two passes per URL:
      1. URL-encode the prompt portion (handles raw spaces / special chars
         the model may emit, e.g. `prompt/data center server`).
      2. HTML-entity-encode raw `&` in the query string as `&amp;` so
         Blogger's XML serializer doesn't have to escape it on its end —
         that's the path that produced the broken `?width=800&amp;...` →
         double-encoded URL on render. Skip any `&` already part of `&amp;`
         to avoid creating `&amp;amp;`.
    """
    def _encode(m: re.Match) -> str:
        prefix = m.group(1)
        prompt = m.group(2)
        query = m.group(3) or ""
        try:
            decoded = unquote(prompt)
        except Exception:
            decoded = prompt
        encoded = quote(decoded, safe="")
        if query:
            query = re.sub(r"&(?!amp;)", "&amp;", query)
        return f"{prefix}{encoded}{query}"

    return _POLLINATIONS_URL_RE.sub(_encode, body)


def _parse_response(text: str) -> GeneratedPost:
    text = text.strip()
    # Defensive strip of any code fence the model may have wrapped output in.
    text = re.sub(r"^```(?:html|HTML)?\s*\n", "", text)
    text = re.sub(r"\n```\s*$", "", text)

    # 1) TITLE
    m_title = re.search(r"^\s*TITLE\s*:\s*(.+)$", text, flags=re.MULTILINE)
    if not m_title:
        raise GenerationError(
            "TITLE line missing in model output. "
            f"First 200 chars: {text[:200]!r}"
        )
    title = _strip_emoji(m_title.group(1).strip())

    # 2) TAGS (when missing, fall back to config tags downstream)
    tags: list[str] = []
    m_tags = re.search(r"^\s*TAGS\s*:\s*(.+)$", text, flags=re.MULTILINE)
    if m_tags:
        raw = m_tags.group(1).strip()
        tags = [_strip_emoji(t).strip() for t in raw.split(",")]
        tags = [t for t in tags if t]              # drop empty tokens
    else:
        logger.warning("TAGS line missing — will fall back to config tags")

    # 3) Body — everything after the '---' separator, or starting from the
    # first HTML tag if no separator was emitted.
    sep_match = re.search(r"^-{3,}\s*$", text, flags=re.MULTILINE)
    if sep_match:
        body = text[sep_match.end():].lstrip()
    else:
        last_meta = m_tags.end() if m_tags else m_title.end()
        rest = text[last_meta:].lstrip()
        html_match = re.search(r"<(?:h1|h2|h3|p|img|ul|ol)\b", rest)
        body = rest[html_match.start():] if html_match else rest

    # Strip residual code fences and any emoji from the body.
    body = re.sub(r"^```(?:html|HTML)?\s*\n", "", body)
    body = re.sub(r"\n```\s*$", "", body)
    body = _strip_emoji(body)

    # URL-encode the prompt portion of Pollinations image URLs (handles the
    # case where the model emitted raw spaces inside the prompt).
    body = _normalize_pollinations_urls(body)

    # Pre-warm each Pollinations URL (forces image generation + CDN cache so
    # readers never trigger the slow first-request path). Any URL that fails
    # verification gets rewritten to a picsum.photos fallback in-place so the
    # post never publishes with a broken-image icon.
    body = _warm_pollinations_images(body)

    # 4) Minimum structural validation
    img_count = len(re.findall(r"<img\b", body))
    if img_count < 2:
        raise GenerationError(
            f"Insufficient body images — need 2-3, found {img_count}"
        )
    if "<h2" not in body:
        raise GenerationError("<h2> heading missing from generated HTML")

    # Soft-checks (warnings only — do not block publish).
    # References section: any h2/h3 whose text contains "references".
    refs_pattern = r"<h[23][^>]*>[^<]*references?[^<]*</h[23]>"
    # Actionable / strategy section: many heading shapes acceptable.
    strategy_pattern = (
        r"<h[23][^>]*>[^<]*(?:strategic\s+vectors|"
        r"actionable\s+implementation|implementation\s+framework|"
        r"strategic\s+implications|strategic\s+implementation|"
        r"enterprise\s+roi|action\s+items|phased\s+rollout|"
        r"recommendations|checklist|what\s+.+\s+should)"
    )
    # Executive Briefing / TL;DR / Summary all acceptable as the opener.
    tldr_pattern = (
        r"<h2[^>]*>[^<]*executive\s+(?:briefing|tl;?dr|summary)[^<]*</h2>"
    )

    if not re.search(refs_pattern, body, flags=re.IGNORECASE):
        logger.warning("'References' section missing — possible SEO rule miss")

    if not re.search(strategy_pattern, body, flags=re.IGNORECASE):
        logger.warning(
            "'Strategic Vectors' section heading not detected — "
            "possible structural rule miss"
        )

    if not re.search(tldr_pattern, body, flags=re.IGNORECASE):
        logger.warning(
            "'Executive Briefing' TL;DR section heading not detected"
        )

    return GeneratedPost(title=title, html=body, tags=tags)


def generate_post(
    topic_label: str,
    niche_keyword: str,
    news_items: list[dict],
    api_key: str | None = None,
    focus_keyword: str | None = None,
    retries: int = 2,
    retry_delay: float = 3.0,
) -> GeneratedPost:
    """Generate a Blogger-ready English post via Gemini.

    Args:
        topic_label:  Logical category label for the site (e.g., "AI Infra").
        niche_keyword: Niche hint surfaced to the prompt (e.g., "datacenter").
        news_items: List of source-news dicts from the fetcher.
        api_key: Per-site Gemini API key for multi-key routing. When None
            the GEMINI_API_KEY env var is used as fallback.
        focus_keyword: The actual keyword chosen by the fallback loop in
            main_blogger.py; injected into the prompt as the topic anchor.
        retries: Number of parse/quota retries before giving up.
        retry_delay: Base seconds between attempts (quota errors override
            this to QUOTA_RETRY_DELAY).
    """
    if not news_items:
        raise GenerationError("No news items provided to generator")

    # Multi-key routing: prefer the per-site key, fall back to a single
    # GEMINI_API_KEY env var. Each site gets its own local Client so keys
    # don't collide across sites in the same process (the old
    # `genai.configure()` global-state pattern leaked keys).
    effective_key = api_key or os.environ.get("GEMINI_API_KEY")
    if not effective_key:
        raise GenerationError(
            "No Gemini API key available — pass api_key=... explicitly or "
            "set the GEMINI_API_KEY environment variable."
        )
    client = genai.Client(api_key=effective_key)

    gen_config = types.GenerateContentConfig(
        system_instruction=SYSTEM_INSTRUCTION_EN,
        # 0.7 strikes a balance: lower than 0.85 cuts down TITLE / image
        # format violations that trigger parse retries; high enough to
        # preserve expressive variety.
        temperature=0.7,
        top_p=0.95,
        max_output_tokens=8192,
        safety_settings=[
            types.SafetySetting(
                category="HARM_CATEGORY_HARASSMENT",
                threshold="BLOCK_ONLY_HIGH",
            ),
            types.SafetySetting(
                category="HARM_CATEGORY_HATE_SPEECH",
                threshold="BLOCK_ONLY_HIGH",
            ),
            types.SafetySetting(
                category="HARM_CATEGORY_SEXUALLY_EXPLICIT",
                threshold="BLOCK_ONLY_HIGH",
            ),
            types.SafetySetting(
                category="HARM_CATEGORY_DANGEROUS_CONTENT",
                threshold="BLOCK_ONLY_HIGH",
            ),
        ],
    )

    news_block_str = _format_news_block(news_items)
    user_prompt = USER_PROMPT_TEMPLATE_EN.format(
        keyword=focus_keyword or topic_label,
        news_context=news_block_str,
    )

    last_err: Exception | None = None
    for attempt in range(retries + 1):
        delay = retry_delay   # sleep duration after a failed attempt
        try:
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=user_prompt,
                config=gen_config,
            )
            text = getattr(response, "text", None)
            if not text:
                # response.text raises if the call was blocked; surface the
                # prompt_feedback for debugging.
                fb = getattr(response, "prompt_feedback", None)
                raise GenerationError(
                    f"Empty response from Gemini (prompt_feedback={fb})"
                )
            return _parse_response(text)
        except GenerationError as e:
            last_err = e
            logger.warning(
                "Generation attempt %d/%d parse-failed: %s",
                attempt + 1, retries + 1, e,
            )
        except Exception as e:
            last_err = e
            if _is_quota_error(e):
                # 429 / quota — short delays keep failing. Force a longer
                # sleep before the next retry.
                delay = QUOTA_RETRY_DELAY
                logger.warning(
                    "Generation attempt %d/%d hit RATE LIMIT (429/quota) — "
                    "sleeping %ds before retry: %s",
                    attempt + 1, retries + 1, int(delay), e,
                )
            else:
                logger.warning(
                    "Generation attempt %d/%d API error: %s",
                    attempt + 1, retries + 1, e,
                )

        if attempt < retries:
            time.sleep(delay)

    raise GenerationError(f"All generation attempts failed: {last_err}")
