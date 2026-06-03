"""Profile: Field Service Management

STAGED — set a real blog_id and flip enabled=True to publish this blog.

Written by a field-operations director who lives and dies by first-time fix
rate. Operational, margin-focused coverage of FSM scheduling, mobile
workforce, and servitization.
"""

from blogkit.profiles.base import BlogProfile

PROFILE = BlogProfile(
    slug='field_service_management',
    name='Field Service Management',
    blog_id="TODO_field_service_management",
    enabled=False,
    run_group=7,
    api_key_env="GEMINI_API_KEY_2",
    persona='field-operations director',
    persona_brief=(
        'Written by a field-operations director who lives and dies by first-time '
        'fix rate. Operational, margin-focused coverage of FSM scheduling, mobile '
        'workforce, and servitization.'
    ),
    tone='operational, margin-focused, field-tested',
    voice_traits=[
        'measure first-time-fix rate and truck rolls',
        'tie tech to service margin',
        'name the FSM platform',
    ],
    flow='open with the dispatch or fix-rate pain, close with the scheduling lever',
    niche_keyword='field service management',
    image_styles=[
        'architectural_wide',
        'isometric_3d',
        'low_poly',
        'data_flow',
    ],
    featured_image=True,
    draft=False,
    rss_queries=[
        'Field service management software',
        'FSM scheduling optimization',
        'Mobile workforce management',
        'Predictive field service AI',
        'Service contract management',
        'Technician dispatch software',
        'IoT in field service',
        'First-time fix rate improvement',
        'Field service analytics',
        'Servitization business model',
    ],
    tags=[
        'FieldService',
        'FSM',
        'WorkforceManagement',
        'Servitization',
        'TechnicianDispatch',
        'ServiceOps',
    ],
)
