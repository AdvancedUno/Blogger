"""Profile: Commercial PropTech

Led by a former portfolio manager at a top-tier REIT who now advises PropTech
founders. Sharp analysis of lease admin automation, tenant experience
platforms, and the ROI math behind smart-HVAC investments.
"""

from blogkit.profiles.base import BlogProfile

PROFILE = BlogProfile(
    slug='commercial_proptech',
    name='Commercial PropTech',
    blog_id='4874722713493494332',
    run_group=3,
    api_key_env='GEMINI_API_KEY_4',
    persona='commercial real estate / PropTech strategist',
    persona_brief=(
        'Led by a former portfolio manager at a top-tier REIT who now advises '
        'PropTech founders. Sharp analysis of lease admin automation, tenant '
        'experience platforms, and the ROI math behind smart-HVAC investments.'
    ),
    niche_keyword='commercial proptech',
    image_styles=[
        'architectural_wide',
        'low_poly',
        'isometric_3d',
        'conceptual_still_life',
    ],
    featured_image=True,
    draft=False,
    rss_queries=[
        'Commercial real estate portfolio SaaS',
        'Tenant experience mobile apps',
        'Lease administration software automation',
        'Digital twin building tech',
        'Smart HVAC AI optimization',
        'Commercial property access control systems',
        'Real estate ESG reporting software',
        'Space utilization analytics IoT',
        'Commercial real estate debt management software',
        'Proptech ROI for property managers',
    ],
    tags=[],
)
