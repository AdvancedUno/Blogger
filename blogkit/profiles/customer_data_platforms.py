"""Profile: Customer Data Platforms

STAGED — set a real blog_id and flip enabled=True to publish this blog.

Authored by a martech data architect who has stood up CDPs and identity graphs
across retail and B2B SaaS. Unfiltered teardowns of composable vs packaged
stacks and what actually drives activation.
"""

from blogkit.profiles.base import BlogProfile

PROFILE = BlogProfile(
    slug='customer_data_platforms',
    name='Customer Data Platforms',
    blog_id="TODO_customer_data_platforms",
    enabled=False,
    run_group=5,
    api_key_env="GEMINI_API_KEY_2",
    persona='martech data architect',
    persona_brief=(
        'Authored by a martech data architect who has stood up CDPs and identity '
        'graphs across retail and B2B SaaS. Unfiltered teardowns of composable vs '
        'packaged stacks and what actually drives activation.'
    ),
    tone='curious, counterintuitive, lightly theatrical',
    voice_traits=[
        'distinguish composable vs packaged honestly',
        'tie data plumbing to activation outcomes',
        'name identity-resolution tradeoffs',
    ],
    flow='open on an odd anecdote, pose the puzzle, reveal the hidden variable, then the rule',
    niche_keyword='customer data platform',
    image_styles=[
        'data_flow',
        'blueprint',
        'isometric_3d',
        'glassmorphism',
    ],
    featured_image=True,
    draft=False,
    rss_queries=[
        'Composable CDP vs packaged',
        'Customer data platform architecture',
        'Identity resolution software',
        'Reverse ETL activation',
        'Real-time personalization engine',
        'Zero-party data strategy',
        'Customer 360 data platform',
        'CDP vs CRM vs DMP',
        'Customer data governance',
        'CDP implementation cost',
    ],
    tags=[
        'CustomerDataPlatform',
        'CDP',
        'MarTech',
        'IdentityResolution',
        'CustomerData',
        'DataActivation',
    ],
)
