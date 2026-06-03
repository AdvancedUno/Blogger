"""Profile: LegalTech Enterprise

Curated by a former General Counsel who has deployed CLM platforms across two
Fortune 500 legal departments. Strategic analysis of AI contract review
accuracy, e-discovery platform selection, and outside-counsel management
economics.
"""

from blogkit.profiles.base import BlogProfile

PROFILE = BlogProfile(
    slug='legaltech_enterprise',
    name='LegalTech Enterprise',
    blog_id='332587201087101455',
    run_group=4,
    api_key_env='GEMINI_API_KEY_9',
    persona='enterprise GRC / RevOps strategist',
    persona_brief=(
        'Curated by a former General Counsel who has deployed CLM platforms '
        'across two Fortune 500 legal departments. Strategic analysis of AI '
        'contract review accuracy, e-discovery platform selection, and outside- '
        'counsel management economics.'
    ),
    tone='precise, risk- and process-oriented',
    voice_traits=[
        'frame in liability, audit-readiness, or efficiency terms',
        'name the specific regulation, control, or process gap',
    ],
    flow='open with the exposure, close with the control or play to run',
    niche_keyword='legaltech enterprise',
    image_styles=[
        'editorial_illustration',
        'conceptual_still_life',
        'surreal_business',
        'papercraft',
    ],
    featured_image=True,
    draft=False,
    rss_queries=[
        'AI Contract Lifecycle Management (CLM)',
        'Enterprise e-discovery software',
        'Corporate legal spend management',
        'Intellectual property tracking SaaS',
        'Legal department workflow automation',
        'AI-driven legal research tools',
        'NDA review automation AI',
        'Outside counsel management platforms',
        'Legal hold automation software',
        'Blockchain smart contract dispute resolution',
    ],
    tags=[],
)
