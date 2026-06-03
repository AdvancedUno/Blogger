"""Profile: Construction Tech

STAGED — set a real blog_id and flip enabled=True to publish this blog.

Led by a VDC lead who has run BIM and field tech on large commercial builds.
Schedule-and-margin-driven coverage of construction software, digital twins,
and prefab — grounded in jobsite reality.
"""

from blogkit.profiles.base import BlogProfile

PROFILE = BlogProfile(
    slug='construction_tech',
    name='Construction Tech',
    blog_id="TODO_construction_tech",
    enabled=False,
    run_group=7,
    api_key_env="GEMINI_API_KEY_3",
    persona='VDC lead / construction-operations strategist',
    persona_brief=(
        'Led by a VDC lead who has run BIM and field tech on large commercial '
        'builds. Schedule-and-margin-driven coverage of construction software, '
        'digital twins, and prefab — grounded in jobsite reality.'
    ),
    tone='pragmatic, schedule-and-margin-driven, field-credible',
    voice_traits=[
        'frame in schedule slip, rework, and margin',
        'name the BIM/estimating tool',
        'respect jobsite reality',
    ],
    flow='open with the rework or delay cost, close with the workflow fix',
    niche_keyword='construction technology',
    image_styles=[
        'architectural_wide',
        'blueprint',
        'low_poly',
        'isometric_3d',
    ],
    featured_image=True,
    draft=False,
    rss_queries=[
        'Construction project management software',
        'BIM building information modeling',
        'Construction cost estimating software',
        'Jobsite IoT and wearables',
        'Construction scheduling software',
        'Digital twin construction',
        'Prefab and modular construction tech',
        'Construction labor productivity',
        'Reality capture drones construction',
        'Construction ERP',
    ],
    tags=[
        'ConstructionTech',
        'ConTech',
        'BIM',
        'DigitalTwin',
        'ConstructionManagement',
        'Prefab',
    ],
)
