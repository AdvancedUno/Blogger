"""Profile: Enterprise InsurTech

Led by an actuary turned product strategist who has launched commercial
property and casualty platforms across three major carriers. Hard data on AI
underwriting accuracy, parametric coverage structures, and embedded insurance
economics.
"""

from blogkit.profiles.base import BlogProfile

PROFILE = BlogProfile(
    slug='enterprise_insurtech',
    name='Enterprise InsurTech',
    blog_id='2936393655016922209',
    run_group=2,
    api_key_env='GEMINI_API_KEY_9',
    persona='sharp Wall Street equities analyst / fintech VC',
    persona_brief=(
        'Led by an actuary turned product strategist who has launched commercial '
        'property and casualty platforms across three major carriers. Hard data '
        'on AI underwriting accuracy, parametric coverage structures, and '
        'embedded insurance economics.'
    ),
    niche_keyword='enterprise insurtech',
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
        'Commercial fleet telematics insurance',
        'AI underwriting automation',
        'Property and casualty claims SaaS',
        'Parametric insurance smart contracts',
        'Enterprise cyber insurance risk modeling',
        'Insurtech API ecosystems',
        'Life insurance digital transformation',
        'Drones in property damage assessment',
        'Predictive modeling in insurance pricing',
        'Embedded insurance B2B partnerships',
    ],
    tags=[],
)
