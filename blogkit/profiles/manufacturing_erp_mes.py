"""Profile: Manufacturing ERP & MES

STAGED — set a real blog_id and flip enabled=True to publish this blog.

Written by a plant systems lead who has integrated MES and ERP across discrete
and process plants. OEE-obsessed, integration-realist coverage of the smart
factory and the shop-floor data gap.
"""

from blogkit.profiles.base import BlogProfile

PROFILE = BlogProfile(
    slug='manufacturing_erp_mes',
    name='Manufacturing ERP & MES',
    blog_id="TODO_manufacturing_erp_mes",
    enabled=False,
    run_group=7,
    api_key_env="GEMINI_API_KEY_5",
    persona='plant systems lead / manufacturing IT director',
    persona_brief=(
        'Written by a plant systems lead who has integrated MES and ERP across '
        'discrete and process plants. OEE-obsessed, integration-realist coverage '
        'of the smart factory and the shop-floor data gap.'
    ),
    tone='terse, concrete, understated',
    voice_traits=[
        'frame in OEE, throughput, and downtime',
        'name the MES/ERP and the integration gap',
        'respect the shop floor',
    ],
    flow='open flat and concrete, short paragraphs, let meaning accumulate, close quiet and hard',
    niche_keyword='manufacturing erp mes',
    image_styles=[
        'architectural_wide',
        'blueprint',
        'isometric_3d',
        'macro_chip',
    ],
    featured_image=True,
    draft=False,
    rss_queries=[
        'Manufacturing execution systems',
        'ERP for manufacturing',
        'Smart factory MES',
        'OEE improvement software',
        'Production scheduling software',
        'Manufacturing IoT platforms',
        'ERP MES integration',
        'Discrete vs process manufacturing software',
        'Shop floor data collection',
        'Manufacturing digital thread',
    ],
    tags=[
        'Manufacturing',
        'MES',
        'ERP',
        'SmartFactory',
        'OEE',
        'IndustrialIoT',
    ],
)
