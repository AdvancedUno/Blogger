"""Profile: Corporate Treasury Tech

Written by a corporate treasurer-turned-advisor with TMS implementation
experience at five Fortune 1000 firms. Practical guidance on liquidity
management software, FX hedging platforms, and multibank connectivity APIs.
"""

from blogkit.profiles.base import BlogProfile

PROFILE = BlogProfile(
    slug='corporate_treasury_tech',
    name='Corporate Treasury Tech',
    blog_id='7688347427258909269',
    run_group=2,
    api_key_env='GEMINI_API_KEY_10',
    persona='sharp Wall Street equities analyst / fintech VC',
    persona_brief=(
        'Written by a corporate treasurer-turned-advisor with TMS implementation '
        'experience at five Fortune 1000 firms. Practical guidance on liquidity '
        'management software, FX hedging platforms, and multibank connectivity '
        'APIs.'
    ),
    tone='measured, analytical, framework-first',
    voice_traits=[
        'lead with a number, a flow, or a basis-point move',
        'expose the risk the vendor pitch hides',
        'think in TCO, ROI, and unit economics',
    ],
    flow='frame the question, build the framework, reason to a named thesis, end on implications',
    niche_keyword='corporate treasury tech',
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
        'Liquidity management SaaS',
        'Corporate FX risk hedging software',
        'Treasury Management Systems (TMS)',
        'Open banking API aggregation',
        'Enterprise cash flow forecasting AI',
        'Working capital optimization platforms',
        'Multibank connectivity APIs',
        'Treasury API standardization',
        'AI in corporate fraud detection',
        'Cloud-based ERP treasury modules',
    ],
    tags=[],
)
