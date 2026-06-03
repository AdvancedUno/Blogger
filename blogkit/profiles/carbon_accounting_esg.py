"""Profile: Carbon Accounting & ESG Software

STAGED — set a real blog_id and flip enabled=True to publish this blog.

Written by a sustainability controller who builds audit-ready emissions data
systems. Rigorous, greenwashing-allergic coverage of Scope 3, CSRD, and the
GHG Protocol — demanding auditable numbers over estimates.
"""

from blogkit.profiles.base import BlogProfile

PROFILE = BlogProfile(
    slug='carbon_accounting_esg',
    name='Carbon Accounting & ESG Software',
    blog_id="TODO_carbon_accounting_esg",
    enabled=False,
    run_group=8,
    api_key_env="GEMINI_API_KEY_8",
    persona='sustainability controller / ESG data lead',
    persona_brief=(
        'Written by a sustainability controller who builds audit-ready emissions '
        'data systems. Rigorous, greenwashing-allergic coverage of Scope 3, CSRD, '
        'and the GHG Protocol — demanding auditable numbers over estimates.'
    ),
    tone='rigorous, audit-ready, greenwashing-allergic',
    voice_traits=[
        'name the framework (GHG Protocol, CSRD, SBTi)',
        'demand auditable data, not estimates',
        'expose Scope 3 data gaps',
    ],
    flow='open with the disclosure-mandate pressure, close with the data-system fix',
    niche_keyword='carbon accounting software',
    image_styles=[
        'editorial_illustration',
        'conceptual_still_life',
        'data_flow',
        'papercraft',
    ],
    featured_image=True,
    draft=False,
    rss_queries=[
        'Carbon accounting software',
        'Scope 3 emissions tracking',
        'ESG reporting platforms',
        'CSRD compliance software',
        'GHG Protocol software',
        'Supply chain emissions data',
        'Science-based targets software',
        'Carbon data management',
        'Climate disclosure regulations',
        'Sustainability data automation',
    ],
    tags=[
        'CarbonAccounting',
        'ESGReporting',
        'Scope3Emissions',
        'CSRD',
        'Sustainability',
        'ClimateDisclosure',
    ],
)
