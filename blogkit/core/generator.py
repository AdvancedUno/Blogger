"""Google Gemini-based blog post generator (English / Blogger-optimized).

Uses the official `google-genai` SDK (gemini-3.5-flash by default, override
via the `GEMINI_MODEL` env var) with a heavily engineered system instruction
tuned for Blogger.com HTML, elite B2B journalism, E-E-A-T, and Featured
Snippet capture.
"""
from __future__ import annotations

import hashlib
import logging
import os
import re
import time
from dataclasses import dataclass, field

from blogkit.core.archetypes import build_archetype_directive, get_archetype
from blogkit.core.formats import build_user_prompt, get_format

logger = logging.getLogger(__name__)

# Rotating editorial lens — picked deterministically per piece so the network
# doesn't read like the same template 20 times (originality / helpful-content).
EDITORIAL_ANGLES = [
    "a contrarian investigation that challenges the prevailing consensus",
    "a forward-looking forecast of where this trend heads over the next 4-8 fiscal quarters",
    "a myth-busting analysis that dismantles the misconceptions executives hold",
    "an operator's playbook centered on concrete, sequenced implementation steps",
    "a follow-the-money breakdown of who captures the value and who quietly loses",
    "a post-mortem lens on why deployments stall and what the failure modes teach",
]


def _pick_angle(seed_text: str) -> str:
    h = int(hashlib.sha256(seed_text.encode("utf-8")).hexdigest(), 16)
    return EDITORIAL_ANGLES[h % len(EDITORIAL_ANGLES)]

# Model name can be overridden via the GEMINI_MODEL env var (e.g.,
# gemini-2.5-flash). Default is gemini-3.5-flash per project preference.
MODEL_NAME = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash")


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
1. DYNAMIC TONE & COMMITTED ANGLE: Do not use the same tone every time. Rotate between being a) Contrarian (exposing hidden risks), b) Highly analytical (ROI/TCO focus), or c) Visionary and strategic, matching the gravity of the topic. When an EDITORIAL ANGLE is specified in the user prompt, fully commit to it — in the headline and throughout — instead of retreating into a neutral, balanced summary.
2. DEPTH WITH SUBSTANCE (target ~1,300-1,800 words): Write a profoundly detailed long-form analysis that earns the reader's time. Every paragraph must add a new fact, implication, or decision — never padding, restatement, or filler to hit a length. Depth means more distinct insights, not more words around the same point.
3. COMPLIANCE & LEGAL REALITY: Weave in the relevant regulatory pressures (SEC, FDA, HIPAA, GDPR, CISA, etc.) naturally, named specifically for the industry at hand — never "regulators" in the abstract.
4. INLINE ANALOGIES: Unpack dense technical concepts using exactly one sharp, relatable corporate analogy.
5. ZERO HALLUCINATIONS & ATTRIBUTION: Ground every claim strictly in the provided [Source Data]. Never invent names, statistics, dates, or metrics. When you cite a figure or event, make clear it comes from the reporting — do not fabricate precision.
6. NO "AI TELLS" — WRITE LIKE A HUMAN: Absolutely ban these and their cousins: "In conclusion", "Furthermore", "Moreover", "Additionally", "Delve into", "Navigating the landscape", "In today's fast-paced world", "It's important to note", "ever-evolving", "game-changer", "unlock", "deep dive", "tapestry", "seamless", "robust" (as filler), "leverage" (as a verb-filler), "Today we will discuss". Also avoid the tell-tale AI rhythm of uniform paragraph blocks and perfectly balanced both-sides hedging. Write as the specific named human author defined in the HUMAN AUTHOR PERSONA block below — with their point of view, their cadence, and a real opinion — not as a neutral assistant summarizing a topic.
7. SEO TITLE DISCIPLINE: The <h1> / TITLE is the single biggest SERP-click lever. Keep it <= 60 characters (hard max 65). FRONT-LOAD the primary keyword/topic in the first 2-4 words. Add one concrete hook — a number, a year, a dollar figure, or a sharp verb. Match real search intent; never clickbait; never the phrase "The Ultimate Guide".
8. SNIPPET-WORTHY OPENING & KEYWORD PLACEMENT: The first <p> after the <h1>/summary callout must work as a standalone ~150-character meta description — compelling, specific, and self-contained (it becomes the SERP snippet). Use the primary topic phrase naturally within the first 100 words and in at least one <h2>. Never keyword-stuff.
9. E-E-A-T & SPECIFICITY: Demonstrate first-hand operator experience and judgment. Always prefer a specific named entity, real figure, or date from the Source Data over a vague generality. Concrete beats comprehensive.
10. RAW HTML ONLY (theme-aware tag set): Output clean HTML paragraphs (max 3-4 sentences each). Allowed elements: <h1>, <h2>, <h3>, <h4>, <p>, <strong>, <b>, <em>, <ul>, <ol>, <li>, <blockquote>, <table>, <thead>, <tbody>, <tr>, <th>, <td>. Do NOT emit any <img>, <figure>, or <figcaption> tags — this blog is text-only. Use <strong> liberally on real data, regulator names, and corporate entities so the reader's eye finds anchors.
11. LAYOUT BACKBONE, HUMAN VOICE (JetTheme v2.9): The template is your structural backbone, not a script to parrot. KEEP these load-bearing elements exactly: the opening <blockquote> summary callout (use the EXACT heading label the template gives it — NEVER the word "TL;DR"), the "<h2>Frequently Asked Questions</h2>" heading verbatim with each Q&A as <h3>question</h3><p>answer</p>, a closing <blockquote> callout, and the "...References..." <h2> at the end. WITHIN that backbone, write every other <h2>/<h3> subhead in your own author's voice (not the bracketed placeholder labels), vary paragraph length deliberately, and let your archetype shape the prose so it reads like a specific human — not a uniform, templated page. Use a <blockquote> pull quote mid-article and, where the template includes one, a comparison <table>.
""".strip()


@dataclass
class Voice:
    """Per-blog editorial identity injected into the shared prompt as a voice
    lock. All fields optional — an empty Voice falls back to the base prompt's
    dynamic adaptation."""

    persona: str = ""
    persona_brief: str = ""
    tone: str = ""
    voice_traits: list[str] = field(default_factory=list)
    flow: str = ""
    banned_phrases: list[str] = field(default_factory=list)

    def is_empty(self) -> bool:
        return not any(
            [self.persona, self.persona_brief, self.tone,
             self.voice_traits, self.flow, self.banned_phrases]
        )


def _compose_system_instruction(
    voice: Voice | None,
    blog_name: str,
    override: str | None,
    archetype_directive: str = "",
) -> str:
    """Build the effective system instruction: a full per-blog override if
    supplied, else the shared base + the human author-archetype block (who is
    writing) + an optional per-blog voice lock built from whichever Voice fields
    are set (how this specific publication sounds).
    """
    if override:
        return override

    parts = [SYSTEM_INSTRUCTION_EN]
    if archetype_directive:
        parts.append(archetype_directive)
    if voice is None or voice.is_empty():
        return "\n\n".join(parts)

    lines = [
        "PRIMARY VOICE LOCK — THIS PUBLICATION ONLY:",
        f'You are the lead writer for "{blog_name}". Sustain this exact voice end to end.',
    ]
    if voice.persona:
        lines.append(f"- Persona: {voice.persona}.")
    if voice.tone:
        lines.append(f"- Tone: {voice.tone}.")
    if voice.voice_traits:
        lines.append("- Style directives: " + "; ".join(voice.voice_traits) + ".")
    if voice.flow:
        lines.append(f"- Flow & pacing: {voice.flow}.")
    if voice.persona_brief:
        lines.append(
            "- Author/editorial context (grounds expertise and diction; never "
            f"quote verbatim): {voice.persona_brief}"
        )
    if voice.banned_phrases:
        bans = ", ".join(f'"{p}"' for p in voice.banned_phrases)
        lines.append(f"- Additionally ban these phrases entirely: {bans}.")
    lines.append(
        "Where this specific voice, the author persona, and the generic "
        "adaptation list conflict, the author persona and this voice win."
    )
    parts.append("\n".join(lines))
    return "\n\n".join(parts)


# The user-prompt structure now lives in core/formats.py — each blog renders a
# theme-appropriate layout (briefing / playbook / deep_dive / buyers_guide /
# market_outlook) instead of one shared skeleton. See build_user_prompt().


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


# Matches "TL;DR", "TLDR", "TL; DR", "tl;dr", etc. — the label the user never
# wants to see. Replaced with the active format's summary heading.
_TLDR_RE = re.compile(r"TL\s*;?\s*DR", re.IGNORECASE)


def _scrub_tldr(html: str, label: str) -> str:
    """Replace any literal TL;DR label with the format's summary heading."""
    return _TLDR_RE.sub(label, html)


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
    if len(title) > 65:
        logger.warning(
            "Title is %d chars (>65) — may truncate in Google SERPs: %r",
            len(title), title,
        )

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
        html_match = re.search(r"<(?:h1|h2|h3|p|ul|ol)\b", rest)
        body = rest[html_match.start():] if html_match else rest

    # Strip residual code fences and any emoji from the body.
    body = re.sub(r"^```(?:html|HTML)?\s*\n", "", body)
    body = re.sub(r"\n```\s*$", "", body)
    body = _strip_emoji(body)

    # 4) Minimum structural validation (text-only blog — no image checks)
    if "<h2" not in body:
        raise GenerationError("<h2> heading missing from generated HTML")

    # Soft-checks (warnings only — do not block publish). Format-agnostic so
    # they hold across every layout in core/formats.py.
    # References section: any h2/h3 whose text contains "references".
    refs_pattern = r"<h[23][^>]*>[^<]*references?[^<]*</h[23]>"
    # FAQ section (every format carries one) — good for long-tail + schema.
    faq_pattern = r"<h2[^>]*>[^<]*frequently\s+asked\s+questions[^<]*</h2>"
    # A summary callout near the top — every format opens with a <blockquote>.
    summary_pattern = r"<blockquote"

    if not re.search(refs_pattern, body, flags=re.IGNORECASE):
        logger.warning("'References' section missing — possible SEO rule miss")

    if not re.search(faq_pattern, body, flags=re.IGNORECASE):
        logger.warning("FAQ section heading not detected — possible structural rule miss")

    if not re.search(summary_pattern, body[:800], flags=re.IGNORECASE):
        logger.warning("Top summary callout (<blockquote>) not detected near the opening")

    return GeneratedPost(title=title, html=body, tags=tags)


def generate_post(
    topic_label: str,
    niche_keyword: str,
    news_items: list[dict],
    api_key: str | None = None,
    focus_keyword: str | None = None,
    voice: Voice | None = None,
    blog_name: str | None = None,
    system_instruction: str | None = None,
    post_format: str = "",
    author_archetype: str = "",
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
        post_format: Layout preset name (see core/formats.FORMATS). Empty or
            unknown falls back to the default ("briefing").
        author_archetype: Human author voice name (see core/archetypes). Empty
            or unknown falls back to the default archetype.
        retries: Number of parse/quota retries before giving up.
        retry_delay: Base seconds between attempts (quota errors override
            this to QUOTA_RETRY_DELAY).
    """
    # Imported lazily so the module's pure helpers (Voice, prompt composition,
    # response parsing) can be imported and unit-tested without the SDK present.
    from google import genai
    from google.genai import types

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

    archetype_directive = build_archetype_directive(get_archetype(author_archetype))
    effective_instruction = _compose_system_instruction(
        voice, blog_name or topic_label, system_instruction, archetype_directive,
    )

    gen_config = types.GenerateContentConfig(
        system_instruction=effective_instruction,
        # 0.7 strikes a balance: lower than 0.85 cuts down TITLE / image
        # format violations that trigger parse retries; high enough to
        # preserve expressive variety.
        temperature=0.7,
        top_p=0.95,
        max_output_tokens=8192,
        safety_settings=[
            types.SafetySetting(
                category=types.HarmCategory.HARM_CATEGORY_HARASSMENT,
                threshold=types.HarmBlockThreshold.BLOCK_ONLY_HIGH,
            ),
            types.SafetySetting(
                category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                threshold=types.HarmBlockThreshold.BLOCK_ONLY_HIGH,
            ),
            types.SafetySetting(
                category=types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
                threshold=types.HarmBlockThreshold.BLOCK_ONLY_HIGH,
            ),
            types.SafetySetting(
                category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                threshold=types.HarmBlockThreshold.BLOCK_ONLY_HIGH,
            ),
        ],
    )

    fmt = get_format(post_format)
    news_block_str = _format_news_block(news_items)
    angle = _pick_angle(
        (focus_keyword or topic_label) + (news_items[0].get("title", "") if news_items else "")
    )
    angle_directive = (
        f"EDITORIAL ANGLE FOR THIS PIECE: Frame the entire analysis as {angle}. "
        "Commit to this angle in the headline and throughout — do not retreat "
        "into a neutral, balanced summary.\n\n"
    )
    user_prompt = angle_directive + build_user_prompt(
        fmt, keyword=focus_keyword or topic_label, news_context=news_block_str,
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
            post = _parse_response(text)
            # Guardrail: if the model slipped a "TL;DR" label into the summary
            # box despite the per-format heading, swap it for the format's own
            # label so no post ever ships the phrase the user dislikes.
            post.html = _scrub_tldr(post.html, fmt.summary_label)
            return post
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
