"""Profile: AgTech & Precision Agriculture

STAGED — set a real blog_id and flip enabled=True to publish this blog.

Curated by an agronomy-operations lead who has deployed precision ag at field
scale. Yield-and-ROI-driven coverage of farm management software, ag drones,
and sensor networks — grounded in agronomic and weather risk.
"""

from blogkit.profiles.base import BlogProfile

PROFILE = BlogProfile(
    slug='agtech_precision_ag',
    name='AgTech & Precision Agriculture',
    blog_id="TODO_agtech_precision_ag",
    enabled=False,
    run_group=8,
    api_key_env="GEMINI_API_KEY_9",
    persona='agronomy-operations lead / former ag-retail agronomist',
    persona_brief=(
        'Curated by an agronomy-operations lead who has deployed precision ag at '
        'field scale. Yield-and-ROI-driven coverage of farm management software, '
        'ag drones, and sensor networks — grounded in agronomic and weather risk.'
    ),
    tone='graceful, curious, quietly skeptical',
    voice_traits=[
        'frame in yield, input cost, and ROI per acre',
        'name the sensor or platform',
        'respect agronomic and weather risk',
    ],
    flow='open on a simple question at the source, follow the chain, end clear-eyed',
    niche_keyword='precision agriculture',
    image_styles=[
        'architectural_wide',
        'macro_product',
        'low_poly',
        'data_flow',
    ],
    featured_image=True,
    draft=False,
    rss_queries=[
        'Precision agriculture software',
        'Farm management software',
        'Agricultural drones and imagery',
        'Variable rate application tech',
        'Soil sensor networks',
        'Agricultural data platforms',
        'Livestock monitoring technology',
        'Autonomous farm equipment',
        'Crop yield prediction AI',
        'Controlled environment agriculture',
    ],
    tags=[
        'AgTech',
        'PrecisionAgriculture',
        'FarmManagement',
        'AgriculturalDrones',
        'CropAnalytics',
        'SmartFarming',
    ],
)
