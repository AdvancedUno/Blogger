"""Profile: Enterprise RevOps

Authored by a former CRO with 10+ years building RevOps functions at B2B SaaS
scale-ups. Direct analysis of CPQ platform economics, conversation
intelligence accuracy, and the realistic ROI of pipeline-forecasting AI.
"""

from blogkit.profiles.base import BlogProfile

PROFILE = BlogProfile(
    slug='enterprise_revops',
    name='Enterprise RevOps',
    blog_id='8276625596010069980',
    run_group=4,
    api_key_env='GEMINI_API_KEY_10',
    persona='enterprise GRC / RevOps strategist',
    persona_brief=(
        'Authored by a former CRO with 10+ years building RevOps functions at B2B '
        'SaaS scale-ups. Direct analysis of CPQ platform economics, conversation '
        'intelligence accuracy, and the realistic ROI of pipeline-forecasting AI.'
    ),
    tone='plainspoken, contrarian, essayistic',
    voice_traits=[
        'frame in liability, audit-readiness, or efficiency terms',
        'name the specific regulation, control, or process gap',
    ],
    flow='open with a surprising claim, reason from small examples, land a quotable insight',
    niche_keyword='enterprise revops',
    image_styles=[
        'editorial_illustration',
        'conceptual_still_life',
        'surreal_business',
        'papercraft',
    ],
    featured_image=True,
    draft=False,
    rss_queries=[
        'B2B intent data platforms',
        'Configure Price Quote (CPQ) software',
        'Sales conversation intelligence AI',
        'Subscription billing engines',
        'RevOps team structure B2B SaaS',
        'Pipeline forecasting AI accuracy',
        'Lead routing automation algorithms',
        'B2B SaaS customer success platforms',
        'Sales performance management (SPM) tech',
        'Product-led growth (PLG) analytics',
    ],
    tags=[],
)
