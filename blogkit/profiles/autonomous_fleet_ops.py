"""Profile: Autonomous Fleet Ops

Written by a former director of fleet operations at a top-3 logistics company
who specializes in warehouse robotics ROI. Hard data on AGV/AMR economics,
last-mile routing AI, and commercial EV charging-API integration patterns.
"""

from blogkit.profiles.base import BlogProfile

PROFILE = BlogProfile(
    slug='autonomous_fleet_ops',
    name='Autonomous Fleet Ops',
    blog_id='3825945251873096901',
    run_group=4,
    api_key_env='GEMINI_API_KEY_7',
    persona='Global VP of Operations',
    persona_brief=(
        'Written by a former director of fleet operations at a top-3 logistics '
        'company who specializes in warehouse robotics ROI. Hard data on AGV/AMR '
        'economics, last-mile routing AI, and commercial EV charging-API '
        'integration patterns.'
    ),
    niche_keyword='autonomous fleet ops',
    image_styles=[
        'architectural_wide',
        'isometric_3d',
        'data_flow',
        'low_poly',
    ],
    featured_image=True,
    draft=False,
    rss_queries=[
        'Warehouse robotics management software',
        'Commercial EV fleet charging APIs',
        'Last-mile delivery routing AI',
        'Heavy duty autonomous trucking tech',
        'Fleet telematics and predictive maintenance',
        'Drone delivery regulatory compliance',
        'Fleet fuel management SaaS',
        'Autonomous forklift ROI',
        'Supply chain yard management systems (YMS)',
        'Commercial vehicle AI dashcams',
    ],
    tags=[],
)
