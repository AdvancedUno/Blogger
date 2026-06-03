"""Profile: Supply Chain Visibility

Authored by a Global VP of Supply Chain Operations who has rolled out control-
tower platforms across consumer-goods and industrial OEMs. Unfiltered
teardowns of freight-API integrations, MEIO algorithms, and 3PL platform
economics.
"""

from blogkit.profiles.base import BlogProfile

PROFILE = BlogProfile(
    slug='supply_chain_visibility',
    name='Supply Chain Visibility',
    blog_id='8479732647594489026',
    run_group=4,
    api_key_env='GEMINI_API_KEY_6',
    persona='Global VP of Operations',
    persona_brief=(
        'Authored by a Global VP of Supply Chain Operations who has rolled out '
        'control-tower platforms across consumer-goods and industrial OEMs. '
        'Unfiltered teardowns of freight-API integrations, MEIO algorithms, and '
        '3PL platform economics.'
    ),
    niche_keyword='supply chain visibility',
    image_styles=[
        'architectural_wide',
        'isometric_3d',
        'data_flow',
        'low_poly',
    ],
    featured_image=True,
    draft=False,
    rss_queries=[
        'Supply chain control tower software',
        'Freight forwarding API integration',
        'Predictive logistics AI',
        'Cold chain IoT tracking',
        'Blockchain supply chain traceability',
        'Enterprise inventory optimization algorithms',
        '3PL logistics digital transformation',
        'Multi-echelon inventory optimization (MEIO)',
        'Real-time ocean freight tracking',
        'Supply chain risk management software',
    ],
    tags=[],
)
