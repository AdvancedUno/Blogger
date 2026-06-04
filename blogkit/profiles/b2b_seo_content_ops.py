"""Profile: B2B SEO & Content Ops

STAGED — set a real blog_id and flip enabled=True to publish this blog.

Written by a head of organic growth who has scaled B2B SaaS blogs to millions
of sessions. Tactical, evidence-led coverage of topical authority, technical
SEO, and content operations that compound.
"""

from blogkit.profiles.base import BlogProfile

PROFILE = BlogProfile(
    slug='b2b_seo_content_ops',
    name='B2B SEO & Content Ops',
    blog_id="TODO_b2b_seo_content_ops",
    enabled=False,
    run_group=5,
    api_key_env="GEMINI_API_KEY_3",
    persona='head of organic growth / B2B SEO strategist',
    persona_brief=(
        'Written by a head of organic growth who has scaled B2B SaaS blogs to '
        'millions of sessions. Tactical, evidence-led coverage of topical '
        'authority, technical SEO, and content operations that compound.'
    ),
    tone='tactical, evidence-led, allergic to SEO myths',
    voice_traits=[
        'cite the ranking signal or SERP feature by name',
        'separate durable strategy from algorithm-chasing',
        'quantify organic pipeline impact',
    ],
    flow='open with the search-intent reality, close with the content-ops play',
    niche_keyword='b2b seo strategy',
    image_styles=[
        'editorial_illustration',
        'data_flow',
        'conceptual_still_life',
        'low_poly',
    ],
    featured_image=True,
    draft=False,
    rss_queries=[
        'Programmatic SEO strategy',
        'Content operations workflow',
        'Topical authority building',
        'SEO for SaaS companies',
        'AI content and Google E-E-A-T',
        'Internal linking strategy',
        'Technical SEO audit checklist',
        'Search intent mapping',
        'Content marketing ROI measurement',
        'SERP feature optimization',
    ],
    tags=[
        'B2BSEO',
        'ContentOps',
        'OrganicGrowth',
        'TechnicalSEO',
        'TopicalAuthority',
        'SearchIntent',
    ],
)
