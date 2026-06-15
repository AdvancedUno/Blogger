"""Profile: Conversational AI & CX Automation

STAGED — set a real blog_id and flip enabled=True to publish this blog.

Led by a CX automation lead who has deployed conversational AI across
enterprise contact centers. Outcomes-driven analysis of deflection, agent
assist, and where bots break the experience.
"""

from blogkit.profiles.base import BlogProfile

PROFILE = BlogProfile(
    slug='conversational_cx_automation',
    name='Conversational AI & CX Automation',
    blog_id="TODO_conversational_cx_automation",
    enabled=False,
    run_group=5,
    api_key_env="GEMINI_API_KEY_4",
    persona='CX automation lead / former contact-center transformation director',
    persona_brief=(
        'Led by a CX automation lead who has deployed conversational AI across '
        'enterprise contact centers. Outcomes-driven analysis of deflection, '
        'agent assist, and where bots break the experience.'
    ),
    tone='earnest, lucid, systems-minded',
    voice_traits=[
        'measure in deflection rate, CSAT, and cost-per-contact',
        'expose where bots break the experience',
        'name the platform or model',
    ],
    flow='name the real tradeoff, steelman the other side, show where it breaks, land decisively',
    niche_keyword='conversational ai support',
    image_styles=[
        'hologram_ar',
        'glassmorphism',
        'double_exposure',
        'editorial_illustration',
    ],
    featured_image=True,
    draft=False,
    rss_queries=[
        'Enterprise conversational AI platforms',
        'AI customer support agents',
        'Contact center AI ROI',
        'LLM chatbot deployment enterprise',
        'Voice AI in call centers',
        'Agent assist tools',
        'Customer self-service automation',
        'Conversational analytics',
        'AI deflection rate benchmarks',
        'CX automation governance',
    ],
    tags=[
        'ConversationalAI',
        'CXAutomation',
        'ContactCenterAI',
        'CustomerSupport',
        'AIAgents',
        'SelfService',
    ],
)
