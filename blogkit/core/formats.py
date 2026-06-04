"""Per-blog post layout presets.

Every blog used to render the same hardcoded skeleton (an "Executive Briefing"
with a "TL;DR" box). That made 40 blogs read like one template. This module
defines a small set of distinct *post formats* — each a different section
structure, summary-callout label, and editorial framing — and assigns each blog
a theme-appropriate one via ``FORMAT_BY_SLUG``.

A format only describes the BODY skeleton (the HTML after the ``<h1>``). The
shared lead-in (task line + Source Data + the TITLE/TAGS/--- parser header +
``<h1>``) lives here too and is reused by every format, so the downstream parser
contract never changes regardless of which layout a blog uses.

No format uses the label "TL;DR" — each has its own summary-box heading.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PostFormat:
    """One reusable post layout."""

    name: str
    descriptor: str       # fills "...a strictly factual {descriptor} based on..."
    summary_label: str    # heading inside the top callout box (never "TL;DR")
    body: str             # HTML skeleton AFTER the <h1>


DEFAULT_FORMAT = "briefing"


# Lead-in shared by every format. We build the final prompt with str.replace()
# (not str.format) so braces that may appear inside the news context never raise.
_PROMPT_PRE = (
    "Conduct a deeply researched, analytical, and strictly factual {descriptor} "
    'based on the following news signals regarding: "{keyword}"'
)

_PROMPT_MID = """You MUST follow this exact HTML structure to provide maximum clarity and visual rhythm on JetTheme v2.9. Do not skip any element — the <blockquote> and <table> wrappers carry distinct theme styling that turns a wall of text into a scannable editorial layout. This blog is text-only: do NOT emit any <img>, <figure>, or <figcaption> tags.

CRITICAL — HEADINGS ARE PURPOSES, NOT TEXT TO COPY: the bracketed text in every <h2>, <h3>, and bold list label below describes what that section must accomplish. Replace each bracketed [...] with your OWN vivid, specific, magazine-style heading that advances the story and names the concrete thing (e.g. not "Risks & Bottlenecks" but "The Broken Pipes in the Utility Data Layer"). Never output the bracketed instruction itself, and never fall back on a generic, templated label. The ONLY headings you must keep verbatim are "Frequently Asked Questions" and the closing references heading.

The first 3 lines below (TITLE / TAGS / ---) are required for downstream parsing. The TITLE line text MUST match the <h1> text exactly.

TITLE: [Same text as the <h1> below — <= 60 characters, primary keyword front-loaded]
TAGS: 5-7 high-CPC B2B tags (PascalCase / compounds, no spaces inside individual tags), comma + space separated
---
<h1>[<= 60 characters (hard max 65). Front-load the primary keyword/topic in the first 2-4 words, then add ONE concrete hook — a number, a year, a dollar figure, or a sharp verb. Sharp, search-intent-matching. Ban "The Ultimate Guide".]</h1>
"""


# =====================================================================
# Format bodies. Each opens with a summary callout (no "TL;DR"), runs a
# distinct set of sections, and carries the structural elements the JetTheme
# layout + SEO rules expect: a pull-quote <blockquote>, an FAQ, a closing
# verdict callout, and a "...References & Signals" heading. (A <table> appears
# only in buyers_guide + case_study.)
#
# IMPORTANT: section <h2>/<h3> titles and bold list labels are written as
# bracketed PURPOSES, not literal text. The shared lead-in (_PROMPT_MID) tells
# the model to replace each bracket with its own vivid, story-driven heading —
# this is what keeps 40 blogs from sharing the same templated subheadings
# (Law 1 in core/craft.py). The ONLY verbatim headings are "Frequently Asked
# Questions" (powers FAQPage schema) and the closing references heading.
# =====================================================================

_BRIEFING_BODY = """<blockquote>
  <p><strong>The 60-Second Briefing</strong></p>
  <ul>
    <li><strong>[2-3 word label for the trigger]:</strong> [One-line fact drawn strictly from the Source Data — what just happened.]</li>
    <li><strong>[2-3 word label for what's at risk]:</strong> [What decision-makers lose if they ignore this signal this quarter.]</li>
    <li><strong>[2-3 word label for the next step]:</strong> [The single most actionable next step for leadership, framed as a verb-led directive.]</li>
  </ul>
</blockquote>

<h2>[Original heading that opens the briefing with a contrarian read on what just happened]</h2>
<p>[Opening paragraph that doubles as the SERP snippet: ~150 characters, compelling and self-contained, leading with a concrete data point or named entity from the Source Data (not a generic preamble), and using the primary topic phrase naturally.]</p>
<p>[Second paragraph — connect the news signal to the broader macro environment and explain why this matters now, this fiscal quarter, not in the abstract.]</p>

<h2>[Original heading naming the specific hidden friction — not a generic "Risks" label]</h2>
<p>[Multiple deep paragraphs exposing hard truths. Why are enterprise deployments stalling? Name and contrast the real vendors, products, or standards involved. What hidden operational costs or integration friction do they gloss over?]</p>

<h3>[Original sub-heading naming where the vendor pitch breaks down]</h3>
<p>[Drill into one specific friction point with a gritty, anonymized case vignette — real operational texture, never tidy round numbers. Cite a real organization or regulator from the Source Data; never invent.]</p>

<blockquote>
  <p><em>"[A striking, analyst-grade pull quote — one sentence that crystallizes the section's core insight, in the persona you adopted. No attribution unless it appears verbatim in the Source Data.]"</em></p>
</blockquote>

<h2>[Original heading for the regulatory / governance pressure that actually bites]</h2>
<p>[Analyze the specific compliance, regulatory (SEC, FTC, HIPAA, GDPR, CISA, etc.), or governance hurdles boards must map. Name the specific framework or agency — not "regulators" generically.]</p>
<p>[A second paragraph tracing where each pressure stands now versus where it is heading, with the named driver — written as prose, not a chart.]</p>

<h2>[Original heading for the adjacent shifts leadership should watch]</h2>
<p>For leadership mapping the next few quarters, the adjacent moves that matter most:</p>
<ul>
   <li><strong>[Specific label]:</strong> [One sentence on why it intersects with today's topic, grounded in observed signals.]</li>
   <li><strong>[Specific label]:</strong> [One sentence factual reason.]</li>
   <li><strong>[Specific label]:</strong> [One sentence factual reason.]</li>
</ul>

<h2>Frequently Asked Questions</h2>
<h3>[An incident-grade question phrased like a real client escalation or production failure — not a theme restatement. E.g. what breaks operationally when this transition goes sideways mid-quarter.]</h3>
<p>[Deeply professional, specific answer reflecting real enterprise realities. Name systems, vendors, or regulators only when they appear in the Source Data.]</p>
<h3>[A second incident-grade question a CFO or operator would actually fire off — about cost overruns, audit-trail gaps, or a realistic ROI timeline under stress.]</h3>
<p>[Realistic, conservative financial perspective on deployment time versus dollar returns. Use ranges, not invented point estimates.]</p>

<blockquote>
  <p><strong>The Bottom Line &mdash;</strong> [Final analyst takeaway in 2-3 sentences, including the one caveat or dependency that could break the thesis. Crystallize the implication for an executive who reads only this paragraph. End with the move, not the warning.]</p>
</blockquote>

<h2>Industry References & Signals</h2>
<p>This macro analysis is synthesized directly from active operational signals and the reporting within the Source Data above.</p>
"""


_PLAYBOOK_BODY = """<blockquote>
  <p><strong>What You'll Walk Away With</strong></p>
  <ul>
    <li><strong>[Specific label for the pain]:</strong> [The operational pain this addresses, grounded in the Source Data.]</li>
    <li><strong>[Specific label for the fix]:</strong> [The architectural or operational pattern that resolves it.]</li>
    <li><strong>[Specific label for step one]:</strong> [The first concrete step a team should take this sprint.]</li>
  </ul>
</blockquote>

<h2>[Original heading naming the real 3 a.m. failure this solves]</h2>
<p>[Open on the real-world failure or friction this solves — snippet-worthy first sentence (~150 chars), led by a concrete signal or named tool from the Source Data.]</p>
<p>[Why this bites engineering teams now, at scale, this quarter.]</p>

<h2>[Original heading for how the mechanism actually works]</h2>
<p>[Explain the underlying mechanism plainly, without hand-waving. Name and contrast the real tools in this space. One sharp analogy is allowed.]</p>
<h3>[Original sub-heading for the component or stage you drill into]</h3>
<p>[Drill into one mechanism with a concrete example or named system from the Source Data; never invent.]</p>

<blockquote>
  <p><em>"[Engineer-grade pull quote that crystallizes the key technical insight — one sentence, opinionated.]"</em></p>
</blockquote>

<h2>[Original heading for the step-by-step implementation]</h2>
<p>[One-line lead-in to the sequenced steps below.]</p>
<ol>
  <li><strong>[Step 1 — verb-led]:</strong> [What to do, and the signal that tells you it worked.]</li>
  <li><strong>[Step 2]:</strong> [Concrete action grounded in real, named tooling.]</li>
  <li><strong>[Step 3]:</strong> [Concrete action.]</li>
  <li><strong>[Step 4]:</strong> [Concrete action.]</li>
</ol>

<h2>[Original heading naming the real tools and the trade-offs between them]</h2>
<ul>
  <li><strong>[Named tool / approach]:</strong> [Where it fits — and the cost or limit you accept for it.]</li>
  <li><strong>[Named tool / approach]:</strong> [Where it fits — and the catch.]</li>
  <li><strong>[Named tool / approach]:</strong> [Where it fits — and the catch.]</li>
</ul>

<h2>[Original heading for the ways teams get this wrong]</h2>
<ul>
  <li><strong>[Specific anti-pattern]:</strong> [Why it backfires in practice, with operational texture.]</li>
  <li><strong>[Specific anti-pattern]:</strong> [Why it backfires.]</li>
  <li><strong>[Specific anti-pattern]:</strong> [Why it backfires.]</li>
</ul>

<h2>Frequently Asked Questions</h2>
<h3>[A real long-tail question a practitioner would type into Google.]</h3>
<p>[Specific, hands-on answer. Name systems only when they appear in the Source Data.]</p>
<h3>[A second practitioner question — cost, scale, or migration.]</h3>
<p>[Realistic answer using ranges, not invented point estimates.]</p>

<blockquote>
  <p><strong>The Bottom Line &mdash;</strong> [2-3 sentence engineer's verdict: what to do first thing Monday, plus the one dependency or human factor that has to be true for it to work. End with the action.]</p>
</blockquote>

<h2>Engineering References & Signals</h2>
<p>This guide is synthesized directly from active engineering signals and the reporting within the Source Data above.</p>
"""


_DEEP_DIVE_BODY = """<blockquote>
  <p><strong>The Short Version</strong></p>
  <ul>
    <li><strong>[Specific label for the event]:</strong> [The event or finding, drawn strictly from the Source Data.]</li>
    <li><strong>[Specific label for the consequence]:</strong> [The second- and third-order consequence.]</li>
    <li><strong>[Specific label for who's exposed]:</strong> [Who or what is now at risk, concretely.]</li>
  </ul>
</blockquote>

<h2>[Original heading opening on what happened, with a contrarian read]</h2>
<p>[Snippet-worthy opening (~150 chars) grounded in a named entity or figure from the Source Data.]</p>
<p>[Connect the event to the broader shift underway — concrete, not abstract.]</p>

<h2>[Original heading for the technical reality under the hood]</h2>
<p>[Explain the mechanism, attack path, or architecture without hand-waving. Name and contrast the real tools, products, or standards at play.]</p>
<h3>[Original sub-heading for the one facet you drill into]</h3>
<p>[Drill into one facet with a gritty, anonymized case vignette; cite a real organization, CVE, or standard from the Source Data; never invent.]</p>

<blockquote>
  <p><em>"[Analyst-grade pull quote that names the uncomfortable truth — one sentence.]"</em></p>
</blockquote>

<h2>[Original heading naming exactly who is exposed and when]</h2>
<p>[Map who is exposed and under what conditions. Be specific about systems and triggers.]</p>

<h2>[Original heading for where the rules and standards stand]</h2>
<p>[Where the rules stand and where they're heading. Name the specific framework, standard, or agency from the Source Data — never "regulators" generically.]</p>
<ul>
  <li><strong>[Named standard / framework]:</strong> [Where it stands now versus where it's heading, with the named driver.]</li>
  <li><strong>[Named standard / framework]:</strong> [Now versus next.]</li>
  <li><strong>[Named standard / framework]:</strong> [Now versus next.]</li>
</ul>

<h2>[Original heading for the leading indicators to track]</h2>
<ul>
  <li><strong>[Specific signal]:</strong> [Why it is the leading indicator.]</li>
  <li><strong>[Specific signal]:</strong> [Why it matters.]</li>
  <li><strong>[Specific signal]:</strong> [Why it matters.]</li>
</ul>

<h2>Frequently Asked Questions</h2>
<h3>[A real long-tail question a specialist would Google.]</h3>
<p>[Specific, technically grounded answer.]</p>
<h3>[A second question — scope, timeline, or mitigation.]</h3>
<p>[Realistic answer using ranges, not invented point estimates.]</p>

<blockquote>
  <p><strong>The Bottom Line &mdash;</strong> [2-3 sentence verdict for a decision-maker who reads only this, including the dependency or friction that complicates it. End with the move.]</p>
</blockquote>

<h2>Industry References & Signals</h2>
<p>This analysis is synthesized directly from active operational signals and the reporting within the Source Data above.</p>
"""


_BUYERS_GUIDE_BODY = """<blockquote>
  <p><strong>Decision Snapshot</strong></p>
  <ul>
    <li><strong>[Specific label for the buyer]:</strong> [The team or role facing this decision.]</li>
    <li><strong>[Specific label for the catch]:</strong> [The non-obvious cost or constraint buyers miss.]</li>
    <li><strong>[Specific label for the move]:</strong> [The recommended next step, framed as a directive.]</li>
  </ul>
</blockquote>

<h2>[Original heading for the real business case, opened with a contrarian angle]</h2>
<p>[Snippet-worthy opening (~150 chars): the concrete problem this category solves, grounded in the Source Data.]</p>
<p>[Why it lands on the roadmap this quarter, not in the abstract.]</p>

<h2>[Original heading naming where this breaks down in the field]</h2>
<p>[The operational friction, hidden integration cost, or adoption failure vendors gloss over — told through a gritty, anonymized case vignette, not tidy numbers.]</p>
<h3>[Original sub-heading for the one failure mode you drill into]</h3>
<p>[Drill into one; name and contrast the real vendors involved; cite a real organization or regulator from the Source Data; never invent.]</p>

<blockquote>
  <p><em>"[Practitioner-grade pull quote that names what buyers later regret — one sentence.]"</em></p>
</blockquote>

<h2>[Original heading for how to actually evaluate the options]</h2>
<table>
  <thead>
    <tr><th>Criterion</th><th>What "Good" Looks Like</th><th>The Red Flag</th></tr>
  </thead>
  <tbody>
    <tr><td>[Criterion 1 — e.g., Integration depth]</td><td>[The bar to demand]</td><td>[The warning sign]</td></tr>
    <tr><td>[Criterion 2]</td><td>[The bar]</td><td>[The warning sign]</td></tr>
    <tr><td>[Criterion 3]</td><td>[The bar]</td><td>[The warning sign]</td></tr>
  </tbody>
</table>

<h2>[Original heading for the rollout sequence]</h2>
<ol>
  <li><strong>[Phase 1 — verb-led]:</strong> [What to do, and how to know it worked.]</li>
  <li><strong>[Phase 2]:</strong> [Concrete action.]</li>
  <li><strong>[Phase 3]:</strong> [Concrete action.]</li>
</ol>

<h2>Frequently Asked Questions</h2>
<h3>[A real buyer long-tail question — e.g., build vs. buy, or pricing model.]</h3>
<p>[Specific answer grounded in real category dynamics.]</p>
<h3>[A second buyer question — e.g., realistic timeline to ROI.]</h3>
<p>[Realistic answer using ranges, not invented point estimates.]</p>

<blockquote>
  <p><strong>The Bottom Line &mdash;</strong> [2-3 sentence buying verdict that still names the one condition under which you'd walk away. End with the move.]</p>
</blockquote>

<h2>Market References & Signals</h2>
<p>This guide is synthesized directly from active market signals and the reporting within the Source Data above.</p>
"""


_MARKET_OUTLOOK_BODY = """<blockquote>
  <p><strong>Where This Is Heading</strong></p>
  <ul>
    <li><strong>[Specific label for the shift]:</strong> [The shift now underway, drawn from the Source Data.]</li>
    <li><strong>[Specific label for who wins/loses]:</strong> [What is being won or lost, and by whom.]</li>
    <li><strong>[Specific label for what to track]:</strong> [The single metric or event to track next.]</li>
  </ul>
</blockquote>

<h2>[Original heading for the inflection, opened with a contrarian read]</h2>
<p>[Snippet-worthy opening (~150 chars) grounded in a concrete figure or entity from the Source Data.]</p>
<p>[Why the timing matters now — the catalyst, not a generic preamble.]</p>

<h2>[Original heading naming the forces actually reshaping the sector]</h2>
<p>[Lay out the structural drivers — technology, demand, cost curves, capital. Name and contrast the real players or projects, not abstractions.]</p>
<h3>[Original sub-heading for the one driver you drill into]</h3>
<p>[Drill into one driver with a gritty, anonymized vignette; cite a real project, company, or agency from the Source Data; never invent.]</p>

<blockquote>
  <p><em>"[Analyst-grade pull quote on where the sector is really heading — one sentence.]"</em></p>
</blockquote>

<h2>[Original heading for the capital, policy, and incentive levers]</h2>
<ul>
  <li><strong>[Named lever — policy / subsidy]:</strong> [Where it stands today and the trajectory, with the named driver.]</li>
  <li><strong>[Named lever — cost curve]:</strong> [Today versus the trajectory.]</li>
  <li><strong>[Named lever — demand]:</strong> [Today versus the trajectory.]</li>
</ul>

<h2>[Original heading naming the specific thing that could stall this — e.g. "The Broken Pipes in the Utility Data Layer", never "Risks & Bottlenecks"]</h2>
<ul>
  <li><strong>[Specific bottleneck]:</strong> [Why it could stall the trend, with operational texture.]</li>
  <li><strong>[Specific bottleneck]:</strong> [Why it could stall the trend.]</li>
  <li><strong>[Specific bottleneck]:</strong> [Why it could stall the trend.]</li>
</ul>

<h2>[Original heading for where the money is actually moving]</h2>
<p>[A concrete read on adjacent opportunities and who is positioning, grounded in observed signals and named players.]</p>

<h2>Frequently Asked Questions</h2>
<h3>[A real long-tail question an investor or operator would Google.]</h3>
<p>[Specific answer grounded in the sector's real dynamics.]</p>
<h3>[A second question — timing, policy risk, or unit economics.]</h3>
<p>[Realistic answer using ranges, not invented point estimates.]</p>

<blockquote>
  <p><strong>The Bottom Line &mdash;</strong> [2-3 sentence outlook that names the assumption your call depends on. End with the opportunity, not the warning.]</p>
</blockquote>

<h2>Sector References & Signals</h2>
<p>This outlook is synthesized directly from active sector signals and the reporting within the Source Data above.</p>
"""


_EXPLAINER_BODY = """<blockquote>
  <p><strong>The Quick Primer</strong></p>
  <ul>
    <li><strong>[Specific label for the definition]:</strong> [Plain-English definition grounded in the Source Data.]</li>
    <li><strong>[Specific label for why it matters]:</strong> [The practical reason a reader should care right now.]</li>
    <li><strong>[Specific label for the catch]:</strong> [The one nuance people most often get wrong.]</li>
  </ul>
</blockquote>

<h2>[Original heading that reframes the topic as a question worth answering]</h2>
<p>[Snippet-worthy opening (~150 chars): reframe the news as a question worth understanding, grounded in a concrete detail from the Source Data.]</p>
<p>[Establish the first principle everything else builds on. Define any term the first time it appears.]</p>

<h2>[Original heading for how the mechanism actually works]</h2>
<p>[Walk through the mechanism step by step, using exactly one analogy that genuinely fits. Name and contrast the real tools or standards where relevant.]</p>
<h3>[Original sub-heading for the part people find most confusing]</h3>
<p>[Clear up that specific confusion; cite a real system or standard from the Source Data; never invent.]</p>

<blockquote>
  <p><em>"[A clarifying one-liner that makes the whole idea finally click.]"</em></p>
</blockquote>

<h2>[Original heading for the worked example]</h2>
<p>[Make it concrete with a gritty, anonymized walk-through grounded in the Source Data — real operational texture, not tidy round numbers.]</p>
<ol>
  <li><strong>[Step 1]:</strong> [What happens, and why it matters.]</li>
  <li><strong>[Step 2]:</strong> [What happens, and why it matters.]</li>
  <li><strong>[Step 3]:</strong> [What happens, and why it matters.]</li>
</ol>

<h2>[Original heading naming the things people get wrong — never "Common Misconceptions" or "Myth 1/2/3"]</h2>
<ul>
  <li><strong>[The specific wrong belief]:</strong> [The reality.]</li>
  <li><strong>[The specific wrong belief]:</strong> [The reality.]</li>
  <li><strong>[The specific wrong belief]:</strong> [The reality.]</li>
</ul>

<h2>Frequently Asked Questions</h2>
<h3>[A real beginner-to-intermediate long-tail question.]</h3>
<p>[Clear, specific answer that actually teaches.]</p>
<h3>[A second question that clears up a common mix-up.]</h3>
<p>[Answer using ranges, not invented point estimates.]</p>

<blockquote>
  <p><strong>The Takeaway &mdash;</strong> [2-3 sentences that leave the reader genuinely understanding the idea, including the caveat that keeps it honest, not merely informed of it.]</p>
</blockquote>

<h2>References & Further Reading</h2>
<p>This explainer is synthesized directly from active reporting and the Source Data above.</p>
"""


_CASE_STUDY_BODY = """<blockquote>
  <p><strong>The Story in Brief</strong></p>
  <ul>
    <li><strong>[Specific label for the setup]:</strong> [Who and what, drawn from the Source Data.]</li>
    <li><strong>[Specific label for the turn]:</strong> [The decisive move or moment.]</li>
    <li><strong>[Specific label for the result]:</strong> [What changed, concretely.]</li>
  </ul>
</blockquote>

<h2>[Original heading that sets the scene with a telling detail]</h2>
<p>[Snippet-worthy opening (~150 chars): set the scene with a specific, telling detail from the Source Data — not a thesis.]</p>
<p>[Establish the stakes and the constraint the players were operating under, with gritty operational texture.]</p>

<h2>[Original heading for what they actually did]</h2>
<p>[Narrate the key decisions and moves, in order.]</p>
<h3>[Original sub-heading for the pivotal decision]</h3>
<p>[Drill into the turning point; attribute to named players or sources from the Source Data; never invent.]</p>

<blockquote>
  <p><em>"[A line that captures the lesson of the moment — quote-like, no attribution unless it appears verbatim in the Source Data.]"</em></p>
</blockquote>

<h2>[Original heading for the numbers that moved]</h2>
<table>
  <thead>
    <tr><th>Metric</th><th>Before</th><th>After</th></tr>
  </thead>
  <tbody>
    <tr><td>[Metric 1]</td><td>[Before state from Source Data]</td><td>[After state]</td></tr>
    <tr><td>[Metric 2]</td><td>[Before]</td><td>[After]</td></tr>
    <tr><td>[Metric 3]</td><td>[Before]</td><td>[After]</td></tr>
  </tbody>
</table>

<h2>[Original heading for where it nearly went wrong]</h2>
<p>[The friction, the near-miss, or the hidden cost — the part the press release left out.]</p>

<h2>[Original heading for what everyone else should take from this]</h2>
<ol>
  <li><strong>[Lesson 1 — verb-led]:</strong> [How to apply it.]</li>
  <li><strong>[Lesson 2]:</strong> [How to apply it.]</li>
  <li><strong>[Lesson 3]:</strong> [How to apply it.]</li>
</ol>

<h2>Frequently Asked Questions</h2>
<h3>[A real long-tail question about replicating this.]</h3>
<p>[Specific, grounded answer.]</p>
<h3>[A second question about cost, time, or risk.]</h3>
<p>[Answer using ranges, not invented point estimates.]</p>

<blockquote>
  <p><strong>The Bottom Line &mdash;</strong> [2-3 sentence takeaway: what a peer should copy, and what they should avoid.]</p>
</blockquote>

<h2>References & Signals</h2>
<p>This case study is synthesized directly from active reporting and the Source Data above.</p>
"""


_OP_ED_BODY = """<blockquote>
  <p><strong>The Argument in One Breath</strong></p>
  <ul>
    <li><strong>[Specific label for the claim]:</strong> [Your thesis, stated flatly.]</li>
    <li><strong>[Specific label for why it matters]:</strong> [Why it matters if you are right.]</li>
    <li><strong>[Specific label for the ask]:</strong> [What you want the reader to do or believe.]</li>
  </ul>
</blockquote>

<h2>[Original heading that plants your contrarian flag]</h2>
<p>[Snippet-worthy opening (~150 chars): plant your flag with a provocative, specific claim grounded in the Source Data.]</p>
<p>[Lay out the spine of the argument in a few sentences.]</p>

<h2>[Original heading for why the consensus is wrong]</h2>
<p>[Take apart the prevailing view. Be specific about who holds it and why it fails. Name real players where relevant.]</p>
<h3>[Original sub-heading for the strongest piece of your case]</h3>
<p>[Drive it home with a concrete fact, figure, or named example from the Source Data; never invent.]</p>

<blockquote>
  <p><em>"[Your sharpest line — the sentence you would want quoted back to you.]"</em></p>
</blockquote>

<h2>[Original heading for the strongest counterargument against you]</h2>
<p>[Steelman the other side honestly — then explain why it still does not hold. This is your self-correction: concede the real friction before you rebut it.]</p>

<h2>[Original heading for what follows if you're right]</h2>
<ul>
  <li><strong>[Specific consequence]:</strong> [What changes, and for whom.]</li>
  <li><strong>[Specific consequence]:</strong> [What changes.]</li>
  <li><strong>[Specific consequence]:</strong> [What changes.]</li>
</ul>

<h2>Frequently Asked Questions</h2>
<h3>[The pointed question a skeptical reader would fire back.]</h3>
<p>[A direct, honest answer.]</p>
<h3>[A second "but what about..." question.]</h3>
<p>[Answer using ranges, not invented point estimates.]</p>

<blockquote>
  <p><strong>Where I Land &mdash;</strong> [2-3 sentences restating the position with conviction. End on the line you want remembered.]</p>
</blockquote>

<h2>References & Signals</h2>
<p>This argument is grounded in active reporting and the Source Data above.</p>
"""


FORMATS: dict[str, PostFormat] = {
    "briefing": PostFormat(
        name="briefing",
        descriptor="market briefing",
        summary_label="The 60-Second Briefing",
        body=_BRIEFING_BODY,
    ),
    "playbook": PostFormat(
        name="playbook",
        descriptor="technical field guide",
        summary_label="What You'll Walk Away With",
        body=_PLAYBOOK_BODY,
    ),
    "deep_dive": PostFormat(
        name="deep_dive",
        descriptor="investigative analysis",
        summary_label="The Short Version",
        body=_DEEP_DIVE_BODY,
    ),
    "buyers_guide": PostFormat(
        name="buyers_guide",
        descriptor="buyer's decision guide",
        summary_label="Decision Snapshot",
        body=_BUYERS_GUIDE_BODY,
    ),
    "market_outlook": PostFormat(
        name="market_outlook",
        descriptor="market outlook",
        summary_label="Where This Is Heading",
        body=_MARKET_OUTLOOK_BODY,
    ),
    "explainer": PostFormat(
        name="explainer",
        descriptor="plain-English explainer",
        summary_label="The Quick Primer",
        body=_EXPLAINER_BODY,
    ),
    "case_study": PostFormat(
        name="case_study",
        descriptor="field case study",
        summary_label="The Story in Brief",
        body=_CASE_STUDY_BODY,
    ),
    "op_ed": PostFormat(
        name="op_ed",
        descriptor="argument-driven op-ed",
        summary_label="The Argument in One Breath",
        body=_OP_ED_BODY,
    ),
}


# =====================================================================
# Per-blog format assignment. Spread across all eight layouts so blogs differ
# structurally, matched to what each topic is best told as:
#   briefing       -> capital-markets / money-flow analysis
#   playbook       -> devtools / platform / cloud ops (hands-on)
#   deep_dive      -> security & frontier deep tech (investigation)
#   buyers_guide   -> category / vendor evaluation (buyer lens)
#   market_outlook -> energy / climate / infrastructure (forward-looking)
#   explainer      -> concept-heavy topics that reward teaching
#   case_study     -> operational verticals told as field stories
#   op_ed          -> debate-rich topics that reward a strong thesis
# A profile can override its assignment via BlogProfile.post_format.
# =====================================================================
FORMAT_BY_SLUG: dict[str, str] = {
    # --- briefing ---
    "b2b_payment_rails": "briefing",
    "corporate_treasury_tech": "briefing",
    "wealthtech_systems": "briefing",
    "institutional_digital_assets": "briefing",
    "marketing_attribution_mmm": "briefing",
    # --- op_ed ---
    "programmatic_adtech_privacy": "op_ed",
    "enterprise_revops": "op_ed",
    "enterprise_insurtech": "op_ed",
    "b2b_seo_content_ops": "op_ed",
    "conversational_cx_automation": "op_ed",
    # --- playbook ---
    "platform_engineering_idp": "playbook",
    "observability_sre": "playbook",
    "finops_cloud_cost": "playbook",
    "api_management_integration": "playbook",
    "kubernetes_container_security": "playbook",
    # --- deep_dive ---
    "zero_trust_enterprise": "deep_dive",
    "cyber_compliance_automation": "deep_dive",
    "meddevice_cybersecurity": "deep_dive",
    "quantum_commercialization": "deep_dive",
    "autonomous_fleet_ops": "deep_dive",
    # --- explainer ---
    "ai_infra_insider": "explainer",
    "dataops_vector_dbs": "explainer",
    "digital_health_interoperability": "explainer",
    "customer_data_platforms": "explainer",
    "industrial_edge_ai": "explainer",
    # --- buyers_guide ---
    "clinical_trial_tech": "buyers_guide",
    "commercial_proptech": "buyers_guide",
    "legaltech_enterprise": "buyers_guide",
    "supply_chain_visibility": "buyers_guide",
    "hr_tech_people_analytics": "buyers_guide",
    # --- case_study ---
    "field_service_management": "case_study",
    "construction_tech": "case_study",
    "hospitality_tech": "case_study",
    "manufacturing_erp_mes": "case_study",
    # --- market_outlook ---
    "smart_building_esg": "market_outlook",
    "grid_energy_storage": "market_outlook",
    "ev_charging_infrastructure": "market_outlook",
    "carbon_accounting_esg": "market_outlook",
    "agtech_precision_ag": "market_outlook",
    "space_satellite_connectivity": "market_outlook",
}


def get_format(name: str) -> PostFormat:
    """Return the PostFormat for ``name``; falls back to the default for an
    empty or unknown name (so a missing assignment never crashes a run)."""
    return FORMATS.get(name or DEFAULT_FORMAT, FORMATS[DEFAULT_FORMAT])


def resolve_format_name(slug: str, explicit: str = "") -> str:
    """The format a blog should use: an explicit profile override wins, else the
    theme-matched assignment, else the default."""
    if explicit:
        return explicit
    return FORMAT_BY_SLUG.get(slug, DEFAULT_FORMAT)


def build_user_prompt(fmt: PostFormat, keyword: str, news_context: str) -> str:
    """Assemble the full user prompt for one post from a format + inputs.

    Uses str.replace (not str.format) so any brace characters inside the news
    context are treated literally and never raise a formatting error.
    """
    pre = _PROMPT_PRE.replace("{descriptor}", fmt.descriptor).replace("{keyword}", keyword)
    return (
        pre
        + "\n\n[Source Data]:\n"
        + news_context.strip()
        + "\n\n"
        + _PROMPT_MID
        + "\n"
        + fmt.body.strip()
        + "\n"
    )
