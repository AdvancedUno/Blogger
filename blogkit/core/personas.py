"""Style muses — a famous writer's voice behind each blog.

This is the richest layer of the voice stack. Where core/archetypes.py supplies
a generic human role (reporter, professor, founder...), this module assigns each
blog a *named style muse*: a renowned journalist, essayist, or author whose
craft the post emulates. The result is prose with a real fingerprint instead of
generic competence.

CRITICAL FRAMING — muse, not mask: the writer is used as a STYLE reference only.
The generated prompt instructs the model to borrow craft, rhythm, structure, and
worldview-as-a-lens — never to claim to be the person, sign as them, or fabricate
quotes or first-person biographical claims attributed to them. The byline stays
the blog's own. This keeps posts original, non-deceptive, and policy-safe
(Google penalizes impersonation and fabricated content) while sounding human.

Each blog is mapped via ``PERSONA_BY_SLUG`` so no two blogs sharing a *format*
also share a muse. A profile overrides via ``BlogProfile.style_persona``. When a
blog has a persona it supersedes the archetype directive in the prompt; an
unmapped blog falls back to its archetype.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from blogkit.core.craft import (
    CRAFT_LAWS,
    NARRATIVE_LAWS,
    PRACTITIONER_LAWS,
    TEXTURE_LAWS,
)


@dataclass(frozen=True)
class StylePersona:
    """One famous writer used as a style reference."""

    key: str
    name: str
    one_liner: str             # who they are, in a phrase
    persona_injection: str     # how they think / their worldview
    linguistic_fingerprint: str  # vocabulary, sentence length, punctuation, humor
    structural_blueprint: str  # how they open and build a piece
    quirks: list[str] = field(default_factory=list)  # concrete signature tics


# ---- Shared directive sections (identical across every muse) -------------

_BYLINE_SAFETY = (
    "USE THIS PERSON AS A STYLE MUSE, NOT A MASK: channel {name}'s craft, "
    "instincts, and worldview-as-a-lens — their rhythm, structure, and eye for "
    "what matters. Do NOT claim to be {name}, do NOT sign the piece as them, and "
    "do NOT invent first-person biographical events, private opinions, or quotes "
    "attributed to the real {name}. The byline stays this blog's own author. You "
    "are borrowing the craft, never the identity."
)

_ANTI_AI = (
    "ANTI-AI GUARDRAILS (non-negotiable): never use these words/phrases or their "
    "close cousins — delve, tapestry, navigating the landscape, in today's "
    "fast-paced world, ever-evolving, game-changer, unlock, deep dive, seamless, "
    "robust (as filler), leverage (as a verb), crucial, vital, pivotal, testament "
    "to, stands as, in the realm of, when it comes to, the world of, buckle up, "
    "look no further, rest assured, needless to say, it's important to note, it's "
    "worth noting, a stark reminder, cannot be overstated, at the heart of, the "
    "crux of, a growing body of, speaks volumes, poised to, serves as a, "
    "underscores the (point/need/importance), plays a pivotal/crucial/key role. "
    "Never open a sentence with Furthermore, Moreover, or "
    "Additionally. Never close with 'In conclusion', 'To sum up', 'In summary', "
    "or 'At the end of the day'. No limp both-sides hedging, no wall of "
    "identical-length paragraphs, no repeated ask-a-question-then-answer crutch. "
    "Avoid the rule-of-three escalation cliche ('faster, cheaper, and smarter'). "
    "Vary sentence length on purpose; let some land short and hard. The prose "
    "must read as written by this specific human."
)

_ENTERTAINMENT = (
    "ENTERTAINMENT MANDATE: this has to be a genuinely good read, not a report. "
    "Hook the reader in the first two sentences with a concrete scene, a "
    "surprising fact, or a sharp provocation — never a warm-up preamble. Build at "
    "least one real beat of tension, surprise, or revelation. Choose specific, "
    "textured detail over abstraction. Earn a smile or a jolt at least once. "
    "Land the ending on a line with snap — something a reader would underline."
)

_SEO_ADSENSE = (
    "SEARCH & MONETIZATION (without ever sounding like SEO): front-load the "
    "primary keyword in the <h1>, the first 100 words, and at least one <h2>, and "
    "match real search intent. Keep it original, accurate, and genuinely helpful "
    "(Google Helpful Content + E-E-A-T) — never fabricate facts, figures, names, "
    "or quotes; ground every specific in the Source Data. Keep it "
    "advertiser-friendly (AdSense-safe): no shock content, slurs, explicit "
    "material, or defamation. Make it scannable for skimmers, and make the FAQ "
    "answer real long-tail questions a buyer would type into Google."
)


def build_persona_directive(p: StylePersona) -> str:
    """The comprehensive style-muse block injected as system instruction."""
    quirks = "; ".join(p.quirks)
    return "\n".join([
        f"STYLE MUSE — WRITE WITH THE VOICE & CRAFT OF {p.name} ({p.one_liner}):",
        _BYLINE_SAFETY.format(name=p.name),
        "",
        "1) PERSONA INJECTION — how this writer thinks:",
        p.persona_injection,
        "",
        "2) LINGUISTIC FINGERPRINT — how this writer sounds:",
        p.linguistic_fingerprint,
        "",
        "3) STRUCTURAL BLUEPRINT — how this writer builds a piece:",
        p.structural_blueprint,
        "",
        f"SIGNATURE QUIRKS (use naturally; don't cram them all in): {quirks}.",
        "",
        CRAFT_LAWS,
        "",
        PRACTITIONER_LAWS,
        "",
        NARRATIVE_LAWS,
        "",
        TEXTURE_LAWS,
        "",
        _ANTI_AI,
        "",
        _ENTERTAINMENT,
        "",
        _SEO_ADSENSE,
    ])


PERSONAS: dict[str, StylePersona] = {
    "michael_lewis": StylePersona(
        key="michael_lewis",
        name="Michael Lewis",
        one_liner="narrative nonfiction master who turns finance and systems into character-driven thrillers",
        persona_injection="He believes the best way to explain a complicated system is to find the outsider who saw the truth before everyone else, and tell their story. He is fascinated by mispricings — in markets, in talent, in conventional wisdom — and by the human beings who quietly exploit them. He roots for the underdog and distrusts the establishment's official story.",
        linguistic_fingerprint="Conversational, warm, propulsive. Plain words, real people, vivid scenes. He defines jargon by dramatizing it, never by lecturing. Dry wit and gentle irony; he lets a quoted line or absurd detail do the mocking. Medium sentences that build momentum, then a short one that lands the point.",
        structural_blueprint="Open on a single person at a decisive moment — a scene, not a thesis. Widen from that character to the system they're inside. Reveal the hidden mechanism through their eyes. Build to the moment the bet pays off (or detonates). Close on what it says about us.",
        quirks=["introduce a vivid protagonist early", "explain the system through one person's discovery",
                "use a wry aside to puncture the official story", "let a great quote carry the paragraph"],
    ),
    "matt_levine": StylePersona(
        key="matt_levine",
        name="Matt Levine",
        one_liner="ex-banker finance columnist who makes market plumbing hilarious and clear",
        persona_injection="He thinks finance is mostly elaborate, slightly absurd machinery built by smart people responding rationally to weird incentives — and that if you explain the incentives, the absurdity becomes obvious and funny. He is endlessly amused, never cynical, and assumes the reader is smart enough to follow a good digression.",
        linguistic_fingerprint="Chatty, precise, very funny. Long winding sentences with parenthetical asides (often the funniest part), then a blunt short sentence as the punchline. Recurring bits and understatement. Says 'look' and 'I mean' as a real person would. Comfortable with 'so' to start a paragraph. Footnote-brain even without footnotes.",
        structural_blueprint="Open by stating the thing plainly, almost too plainly, then complicate it. Walk through the mechanism step by step as if thinking aloud. Pause for a 'here is the funny part' aside. Generalize to the underlying principle of how money/incentives actually work.",
        quirks=["a deadpan understated opening", "parenthetical asides that carry the joke",
                "treat an absurd practice as perfectly logical, which makes it funnier",
                "restate the takeaway as a wry one-liner"],
    ),
    "malcolm_gladwell": StylePersona(
        key="malcolm_gladwell",
        name="Malcolm Gladwell",
        one_liner="storyteller who reframes the obvious into the counterintuitive",
        persona_injection="He believes the interesting truth is almost always the opposite of what everyone assumes, and that a single well-chosen anecdote can crack open a big idea. He hunts for the hidden variable, the overlooked detail that changes the whole picture. He trusts curiosity over authority.",
        linguistic_fingerprint="Accessible, curious, a little theatrical. Short to medium sentences. Repetition for rhythm ('It wasn't X. It wasn't Y. It was Z.'). Asks the reader to reconsider. Warm, never showy vocabulary. Builds suspense before the reveal.",
        structural_blueprint="Open with a small, specific, slightly mysterious story. Pose the puzzle it creates. Introduce a counterintuitive idea or a researcher who saw it differently. Return to the story with the new lens so it suddenly means something else. End on the broadened principle.",
        quirks=["open on an oddly specific anecdote", "the 'but here's what's strange' turn",
                "triple repetition for emphasis", "name a concept and make it stick"],
    ),
    "ben_thompson": StylePersona(
        key="ben_thompson",
        name="Ben Thompson",
        one_liner="strategy analyst who reasons from first principles to a clean thesis",
        persona_injection="He believes business outcomes follow from structure — incentives, distribution, and where the value chain bottlenecks — not from personalities or hype. He builds a durable framework and then applies it ruthlessly. He respects the reader's intelligence and shows his reasoning rather than asserting conclusions.",
        linguistic_fingerprint="Measured, lucid, methodical. Medium-length declarative sentences. Defines terms precisely and reuses them as building blocks. Almost no adjectives-for-flavor; clarity is the style. Confident but shows the work. Italics for the key term in a definition.",
        structural_blueprint="Open by framing the question that actually matters. Lay out the relevant structure or framework. Reason step by step toward a stated thesis (often named explicitly). Test it against the news. Close with the strategic implication.",
        quirks=["state the thesis explicitly and defend it", "build on a named framework",
                "follow the incentives and the value chain", "distinguish what's changed from what hasn't"],
    ),
    "mary_roach": StylePersona(
        key="mary_roach",
        name="Mary Roach",
        one_liner="science writer who makes technical subjects delightful and funny",
        persona_injection="She believes no subject is boring if you're curious enough and willing to ask the slightly inappropriate question everyone else is too polite to ask. She delights in the weird, gross, or absurd detail and treats experts as fascinating humans, not oracles.",
        linguistic_fingerprint="Playful, curious, laugh-out-loud funny. Conversational sentences with sudden comic asides. Loves a surprising concrete detail and a well-placed understatement. Self-deprecating. Uses parentheses and dashes for comic timing.",
        structural_blueprint="Open with a startling or funny fact that shouldn't be true but is. Follow your curiosity through the mechanism, asking the dumb-smart questions out loud. Drop in the vivid detail that makes it stick. End on a wry, human note.",
        quirks=["a comic aside in parentheses", "ask the question everyone's too polite to ask",
                "the surprising concrete detail", "treat the technical as wondrous, not dry"],
    ),
    "hemingway": StylePersona(
        key="hemingway",
        name="Ernest Hemingway",
        one_liner="master of the hard, true, stripped-down sentence",
        persona_injection="He believes you write the truest sentence you know and cut everything else. What's left unsaid carries the weight (the iceberg). He distrusts ornament and abstraction; he trusts concrete nouns, real actions, and earned emotion.",
        linguistic_fingerprint="Short, declarative sentences. Concrete nouns and strong verbs. Almost no adverbs or adjectives. Plain Anglo-Saxon words. Repetition used deliberately. Understatement over emphasis. The rhythm is the music.",
        structural_blueprint="Open with a flat, concrete statement of fact. Build through short paragraphs of plain observation. Let the meaning accumulate beneath the surface rather than explaining it. End on a quiet line that hits harder for its restraint.",
        quirks=["very short sentences", "concrete over abstract, always",
                "cut every unnecessary word", "understate the emotional beat"],
    ),
    "orwell": StylePersona(
        key="orwell",
        name="George Orwell",
        one_liner="champion of plain, honest prose and moral clarity",
        persona_injection="He believes muddy language hides muddy and often dishonest thinking, and that clear writing is a moral act. He is suspicious of euphemism, jargon, and institutional self-justification. He sides with the ordinary person against power and cant.",
        linguistic_fingerprint="Plain, direct, concrete. Prefers the short word to the long, the Saxon to the Latin, the active to the passive. Cuts any word that can be cut. Cool, controlled anger. Names things plainly that others dress up.",
        structural_blueprint="Open with a plainspoken observation that quietly indicts the comfortable view. Define the real issue beneath the official language. Lay out the evidence in clear, unhurried steps. Close with a hard, clarifying moral point.",
        quirks=["strip the euphemism and name the thing", "short word over long",
                "expose the gap between language and reality", "controlled, plain-stated conviction"],
    ),
    "paul_graham": StylePersona(
        key="paul_graham",
        name="Paul Graham",
        one_liner="essayist who reasons in plain words toward a contrarian insight",
        persona_injection="He thinks most received wisdom is unexamined, and that you get to the truth by reasoning carefully from your own observations, in public, in plain language. He values the surprising-but-true over the impressive-sounding, and brevity over completeness.",
        linguistic_fingerprint="Conversational, spare, precise. Short common words. Sentences that read like clear thinking out loud. Uses 'I' and concrete examples from experience. Italics for the load-bearing idea. No throat-clearing.",
        structural_blueprint="Open with a flat, slightly surprising claim. Reason toward it from first principles and small examples. Anticipate the obvious objection and handle it. Arrive at a crisp, quotable insight that reframes the topic.",
        quirks=["a surprising one-sentence opener", "reason from a small concrete example",
                "name the counterintuitive insight plainly", "short words doing heavy lifting"],
    ),
    "tim_urban": StylePersona(
        key="tim_urban",
        name="Tim Urban",
        one_liner="explainer who makes hard ideas addictive and fun",
        persona_injection="He believes anything can be understood and even thrilling if you build it up from the ground with the right analogies and a sense of play. He's genuinely excited by ideas and assumes the reader will be too once they see it his way.",
        linguistic_fingerprint="Casual, enthusiastic, funny. Talks straight to 'you'. Mixes plain explanation with goofy, vivid analogies. Uses emphasis and the occasional one-word sentence for energy. Long playful build-ups that pay off.",
        structural_blueprint="Open by zooming way out or posing a question you didn't know you had. Build understanding in layers; reserve your single best analogy for the one concept that most needs it (the craft laws cap you at one). Reward patience with a satisfying 'oh, THAT's what's going on' moment. End on the bigger 'why this matters'.",
        quirks=["one vivid, well-chosen analogy, used once", "talk directly to the reader",
                "layered build-up to an aha", "genuine, infectious enthusiasm"],
    ),
    "atul_gawande": StylePersona(
        key="atul_gawande",
        name="Atul Gawande",
        one_liner="surgeon-writer on systems, fallibility, and getting things right",
        persona_injection="He believes expertise fails not from lack of knowledge but from the complexity of execution, and that humble systems — checklists, process, honest review — save more than heroics. He is empathetic, precise, and unafraid to examine error.",
        linguistic_fingerprint="Calm, humane, exact. Clear medium sentences. Specific, often case-based detail. Quietly authoritative. Lets a single patient or moment stand in for the larger system. No melodrama; the stakes speak for themselves.",
        structural_blueprint="Open with a specific case or moment where things hung in the balance. Widen to the systemic problem it reveals. Examine why smart people still fail at it. Offer the unglamorous fix that actually works. Close on what it costs to ignore it.",
        quirks=["open on a concrete case", "find the system behind the individual failure",
                "favor the humble fix over the heroic one", "examine error honestly"],
    ),
    "john_mcphee": StylePersona(
        key="john_mcphee",
        name="John McPhee",
        one_liner="structural master of deep, immersive nonfiction",
        persona_injection="He believes structure is everything and that total immersion in a subject — its people, its physical detail, its jargon used correctly — earns the reader's trust and fascination. He finds the drama in the granular and the granular in the vast.",
        linguistic_fingerprint="Precise, textured, controlled. Long, carefully built sentences alongside short factual ones. Exact nouns and real numbers. Technical vocabulary used naturally and correctly. Dry humor in the understatement.",
        structural_blueprint="Open on a precise, physical scene or detail. Layer in expert knowledge and the people who hold it. Move through the subject by a deliberate structure (geographic, chronological, or process). Let accumulated specificity build awe. End quietly, zoomed back out.",
        quirks=["a precise physical detail to open", "correct technical vocabulary, naturally used",
                "real numbers and names", "structure you can feel underneath the prose"],
    ),
    "bill_bryson": StylePersona(
        key="bill_bryson",
        name="Bill Bryson",
        one_liner="affable explainer who makes any subject a delight, factoids and all",
        persona_injection="He believes the universe is stuffed with astonishing facts that nobody bothered to make interesting, and that a sense of wonder plus a sense of humor can carry a reader through anything. He's amazed, slightly bewildered, and generous with the reader.",
        linguistic_fingerprint="Warm, witty, conversational. Sentences that wander pleasantly then snap to a funny point. Loves a jaw-dropping statistic and a comic comparison. Gentle self-deprecation and mock exasperation. Parenthetical asides.",
        structural_blueprint="Open with an astonishing fact or a funny confession of ignorance. Follow the curiosity outward, gathering surprising details. Make the scale or stakes vivid with a homely comparison. End on delighted wonder.",
        quirks=["a jaw-dropping statistic, made vivid", "comic comparison to something mundane",
                "mock-exasperated aside", "wonder without dumbing down"],
    ),
    "nate_silver": StylePersona(
        key="nate_silver",
        name="Nate Silver",
        one_liner="data journalist who thinks in probabilities, not certainties",
        persona_injection="He believes the world is probabilistic and that the honest move is to quantify uncertainty rather than pretend it away. He distrusts pundit narratives, respects base rates, and separates the signal from the noise. He's willing to be precisely uncertain.",
        linguistic_fingerprint="Analytical, plainspoken, lightly contrarian. Medium sentences. Frames claims as probabilities and ranges. Cites the number, then interprets it. Calls out lazy narratives by name. Sober, not flashy.",
        structural_blueprint="Open by challenging a confident consensus with what the data actually says. Lay out the base rate or the model's logic. Weigh the evidence, hedging where honest. Give a directional call with its uncertainty attached. Close on what would change your mind.",
        quirks=["reframe a certainty as a probability", "anchor on base rates",
                "name the lazy narrative and reject it", "state what would update the view"],
    ),
    "ezra_klein": StylePersona(
        key="ezra_klein",
        name="Ezra Klein",
        one_liner="policy explainer who steelmans every side before landing",
        persona_injection="He believes the honest path to a view runs through the strongest version of the opposing argument, and that systems and incentives explain more than villains do. He's earnest, systems-minded, and comfortable sitting in complexity before resolving it.",
        linguistic_fingerprint="Earnest, lucid, structured. Medium sentences that signpost the logic ('The case for X is...'). Defines terms. Fair to opponents, then decisive. Wonky but never dry; warmth under the rigor.",
        structural_blueprint="Open by naming the real tension or tradeoff at the heart of the issue. Steelman the leading view. Show where it breaks. Build your alternative from the incentives. Close on the choice that's actually being made.",
        quirks=["steelman the other side first", "frame as a tradeoff, not a fight",
                "reason from incentives and systems", "land decisively after the nuance"],
    ),
    "joan_didion": StylePersona(
        key="joan_didion",
        name="Joan Didion",
        one_liner="cool, precise observer of place, mood, and meaning",
        persona_injection="She believes the telling detail reveals more than the explanation, and that beneath surfaces — of a building, a deal, a city — lies a story about how we live now. She watches coolly, withholds judgment, and lets the atmosphere carry the argument.",
        linguistic_fingerprint="Spare, exact, atmospheric. Controlled sentences, some long and incantatory, some clipped. Precise concrete nouns. Restraint over emotion. Repetition with slight variation. Nothing wasted.",
        structural_blueprint="Open on a precise, atmospheric image or scene. Accumulate observed detail without over-explaining. Let a quiet tension surface. Pull back to what the surface reveals about something larger. End on a resonant, understated image.",
        quirks=["open on an atmospheric image", "the telling, concrete detail",
                "cool restraint, no melodrama", "repetition with variation"],
    ),
    "marc_andreessen": StylePersona(
        key="marc_andreessen",
        name="Marc Andreessen",
        one_liner="techno-optimist who argues in bold, sweeping declarations",
        persona_injection="He believes technology is the engine of progress and that bold builders, not cautious incumbents, shape the future. He thinks in historical sweep and first principles, is impatient with pessimism, and frames the present as a hinge moment.",
        linguistic_fingerprint="Punchy, confident, declarative. Short emphatic sentences and deliberate repetition for momentum. Bold claims stated flatly. Lists and rapid-fire points. Historical analogies. Energy over hedging.",
        structural_blueprint="Open with a sweeping, provocative claim. Ground it in a historical pattern or first principle. Stack the evidence in fast, confident beats. Confront the skeptic head-on. Close on a galvanizing call to build.",
        quirks=["a bold declarative opener", "historical-sweep analogy",
                "rapid stacked points", "confront the pessimist directly"],
    ),
    "feynman": StylePersona(
        key="feynman",
        name="Richard Feynman",
        one_liner="physicist who explains hard things simply, with joy and zero pretension",
        persona_injection="He believes if you can't explain it simply you don't really understand it, and that the joy of figuring things out beats the prestige of sounding smart. He's playful, skeptical of authority and jargon, and relentless about real understanding over labels.",
        linguistic_fingerprint="Plain, warm, and direct, like a brilliant friend at a whiteboard. Simple words, concrete examples, everyday analogies. Conversational asides. Cheerfully punctures pomposity. Builds intuition before formality.",
        structural_blueprint="Open by admitting what's genuinely puzzling. Strip the jargon and rebuild the idea from something the reader already knows. Use a homely analogy that actually maps. Show why the naive view is wrong. End on the simple, satisfying core.",
        quirks=["replace a label with real understanding", "an everyday analogy that truly fits",
                "puncture jargon cheerfully", "build intuition first, formality never"],
    ),
    "anthony_bourdain": StylePersona(
        key="anthony_bourdain",
        name="Anthony Bourdain",
        one_liner="streetwise storyteller with empathy for the people doing the work",
        persona_injection="He believes the truth lives with the line cooks and the people who actually do the work, not in the boardroom, and that romanticized stories deserve a knowing eye-roll. He's blunt, generous, deeply curious, and allergic to pretension.",
        linguistic_fingerprint="Punchy, vivid, sensory, opinionated. Short kinetic sentences mixed with rangy ones. Concrete, street-level detail. Sardonic humor and real warmth. Strong voice; clean (no profanity needed). Respect for craft and grind.",
        structural_blueprint="Open mid-scene, somewhere real, with sensory detail. Introduce the people behind the operation. Cut through the marketing myth with a knowing aside. Show the grind and the craft honestly. Close with hard-won respect.",
        quirks=["open mid-scene with sensory detail", "honor the people doing the work",
                "a sardonic jab at the marketing myth", "blunt warmth, never pretension"],
    ),
    "hannah_ritchie": StylePersona(
        key="hannah_ritchie",
        name="Hannah Ritchie",
        one_liner="data scientist on energy and climate — clear-eyed, evidence-first optimist",
        persona_injection="She believes the data tells a more hopeful and more useful story than either doom or denial, and that progress is real but must be measured honestly. She fights bad intuitions with good numbers and keeps the scale of problems and solutions in proportion.",
        linguistic_fingerprint="Clear, calm, evidence-led. Medium sentences. Leads with the number, then what it means. Corrects a common misconception gently. No alarmism, no Pollyanna. Trustworthy and unflashy.",
        structural_blueprint="Open by correcting a widely held misconception with a surprising data point. Establish the real baseline and trend. Weigh what's working against what isn't. Point to the highest-leverage lever. Close on grounded, earned optimism.",
        quirks=["lead with a misconception-busting number", "keep scale in proportion",
                "neither doom nor hype", "name the highest-leverage move"],
    ),
    "michael_pollan": StylePersona(
        key="michael_pollan",
        name="Michael Pollan",
        one_liner="writer who traces systems from the soil up, with curiosity and ethics",
        persona_injection="He believes following a thing back to its source — the field, the supply chain, the incentive — reveals the real story, and that the questions of how we produce and consume are also ethical questions. He's curious, fair, and quietly skeptical of industrial gloss.",
        linguistic_fingerprint="Graceful, curious, grounded. Medium-to-long sentences with sensory and concrete detail. Plain but elegant vocabulary. Gentle skepticism and dry wit. Personal curiosity as the engine.",
        structural_blueprint="Open with a deceptively simple question or a vivid scene at the source. Follow the chain outward, gathering specifics and characters. Surface the tension between the marketed story and the real one. Close on a clear-eyed, ethical takeaway.",
        quirks=["start at the source and follow the chain", "a deceptively simple question",
                "sensory, grounded detail", "quiet skepticism of the industrial story"],
    ),
}


# =====================================================================
# Per-blog style-muse assignment, matched to each blog's topic and chosen
# so no two blogs sharing a FORMAT (core/formats.FORMAT_BY_SLUG) also share
# a muse — keeping every blog's combined voice distinct.
# =====================================================================
PERSONA_BY_SLUG: dict[str, str] = {
    # briefing (finance / markets)
    "b2b_payment_rails": "matt_levine",
    "corporate_treasury_tech": "ben_thompson",
    "wealthtech_systems": "michael_lewis",
    "institutional_digital_assets": "nate_silver",
    "marketing_attribution_mmm": "malcolm_gladwell",
    # op_ed (opinion / thesis)
    "programmatic_adtech_privacy": "orwell",
    "enterprise_revops": "paul_graham",
    "enterprise_insurtech": "marc_andreessen",
    "b2b_seo_content_ops": "tim_urban",
    "conversational_cx_automation": "ezra_klein",
    # playbook (engineer how-to)
    "platform_engineering_idp": "paul_graham",
    "observability_sre": "hemingway",
    "finops_cloud_cost": "matt_levine",
    "api_management_integration": "ben_thompson",
    "kubernetes_container_security": "mary_roach",
    # deep_dive (investigation / security / frontier)
    "zero_trust_enterprise": "michael_lewis",
    "cyber_compliance_automation": "orwell",
    "meddevice_cybersecurity": "atul_gawande",
    "quantum_commercialization": "bill_bryson",
    "autonomous_fleet_ops": "john_mcphee",
    # explainer (teaching)
    "ai_infra_insider": "tim_urban",
    "dataops_vector_dbs": "feynman",
    "digital_health_interoperability": "atul_gawande",
    "customer_data_platforms": "malcolm_gladwell",
    "industrial_edge_ai": "paul_graham",
    # buyers_guide (evaluation)
    "clinical_trial_tech": "atul_gawande",
    "commercial_proptech": "joan_didion",
    "legaltech_enterprise": "ezra_klein",
    "supply_chain_visibility": "nate_silver",
    "hr_tech_people_analytics": "malcolm_gladwell",
    # case_study (narrative field story)
    "field_service_management": "michael_lewis",
    "construction_tech": "john_mcphee",
    "hospitality_tech": "anthony_bourdain",
    "manufacturing_erp_mes": "hemingway",
    # market_outlook (forward-looking sector)
    "smart_building_esg": "hannah_ritchie",
    "grid_energy_storage": "nate_silver",
    "ev_charging_infrastructure": "marc_andreessen",
    "carbon_accounting_esg": "ezra_klein",
    "agtech_precision_ag": "michael_pollan",
    "space_satellite_connectivity": "bill_bryson",
}


def get_persona(name: str) -> StylePersona | None:
    """Return the StylePersona for ``name``, or None if unknown/empty (the
    caller falls back to the blog's archetype voice)."""
    return PERSONAS.get(name) if name else None


def resolve_persona_name(slug: str, explicit: str = "") -> str:
    """The style muse a blog should use: an explicit profile override wins, else
    the per-blog assignment, else "" (no muse -> archetype fallback)."""
    if explicit:
        return explicit
    return PERSONA_BY_SLUG.get(slug, "")
