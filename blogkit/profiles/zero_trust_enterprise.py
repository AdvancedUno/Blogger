"""Profile: Zero Trust Enterprise

Authored by a veteran CISO with hands-on Zero Trust rollout experience across
banking, healthcare, and federal contracting. Translating CISA frameworks and
NIST guidance into deployment-ready architecture decisions for security
leaders.
"""

from blogkit.profiles.base import BlogProfile

PROFILE = BlogProfile(
    slug='zero_trust_enterprise',
    name='Zero Trust Enterprise',
    blog_id='7324002929395461995',
    run_group=1,
    api_key_env='GEMINI_API_KEY_2',
    persona='veteran CISO / Cyber Intelligence Director',
    persona_brief=(
        'Authored by a veteran CISO with hands-on Zero Trust rollout experience '
        'across banking, healthcare, and federal contracting. Translating CISA '
        'frameworks and NIST guidance into deployment-ready architecture '
        'decisions for security leaders.'
    ),
    niche_keyword='zero trust enterprise',
    image_styles=[
        'macro_chip',
        'server_room',
        'blueprint',
        'double_exposure',
        'surreal_business',
    ],
    featured_image=True,
    draft=False,
    rss_queries=[
        'Zero Trust Network Access (ZTNA) vs VPN',
        'Cloud security posture management (CSPM)',
        'Enterprise microsegmentation strategy',
        'Identity and Access Management (IAM) APIs',
        'SASE architecture enterprise rollout',
        'Privileged Access Management (PAM) audits',
        'Endpoint detection and response (EDR) ROI',
        'Zero trust maturity model CISA',
        'API security gateways enterprise',
        'Post-quantum cryptography migration',
    ],
    tags=[],
)
