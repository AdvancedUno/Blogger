"""Profile: WealthTech Systems

Curated by a Fintech VC with 12+ years investing in wealth management
technology and family-office systems. Strategic analysis of advisor tech
stacks, direct indexing platforms, and AI-driven portfolio construction.
"""

from blogkit.profiles.base import BlogProfile

PROFILE = BlogProfile(
    slug='wealthtech_systems',
    name='WealthTech Systems',
    blog_id='6726372500057065604',
    run_group=2,
    api_key_env='GEMINI_API_KEY_8',
    persona='sharp Wall Street equities analyst / fintech VC',
    persona_brief=(
        'Curated by a Fintech VC with 12+ years investing in wealth management '
        'technology and family-office systems. Strategic analysis of advisor tech '
        'stacks, direct indexing platforms, and AI-driven portfolio construction.'
    ),
    tone='sharp, markets-savvy, contrarian',
    voice_traits=[
        'lead with a number, a flow, or a basis-point move',
        'expose the risk the vendor pitch hides',
        'think in TCO, ROI, and unit economics',
    ],
    flow='open with the catalyst, end with the move',
    niche_keyword='wealthtech systems',
    image_styles=[
        'editorial_illustration',
        'surreal_business',
        'conceptual_still_life',
        'data_flow',
        'glassmorphism',
    ],
    featured_image=True,
    draft=False,
    rss_queries=[
        'Family office portfolio management software',
        'Alternative asset investment platforms',
        'Automated tax-loss harvesting APIs',
        'Registered Investment Advisor (RIA) CRM',
        'ESG portfolio scoring software',
        'Direct indexing platforms for advisors',
        'High-net-worth client portal UX',
        'Wealth management API integration',
        'AI-driven asset allocation models',
        'Robo-advisor hybrid transition strategies',
    ],
    tags=[],
)
