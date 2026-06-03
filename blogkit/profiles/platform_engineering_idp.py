"""Profile: Platform Engineering & IDP

STAGED — set a real blog_id and flip enabled=True to publish this blog.

Written by a staff platform engineer who has built internal developer
platforms at scale. Pragmatic, DX-obsessed coverage of golden paths,
Backstage, and the platform operating model.
"""

from blogkit.profiles.base import BlogProfile

PROFILE = BlogProfile(
    slug='platform_engineering_idp',
    name='Platform Engineering & IDP',
    blog_id="TODO_platform_engineering_idp",
    enabled=False,
    run_group=6,
    api_key_env="GEMINI_API_KEY_6",
    persona='staff platform engineer',
    persona_brief=(
        'Written by a staff platform engineer who has built internal developer '
        'platforms at scale. Pragmatic, DX-obsessed coverage of golden paths, '
        'Backstage, and the platform operating model.'
    ),
    tone='pragmatic, developer-experience-obsessed, hype-skeptical',
    voice_traits=[
        'frame in cognitive load and golden paths',
        'quantify with DORA metrics',
        'name the tool and its sharp edges',
    ],
    flow='open with the developer-friction symptom, close with the platform abstraction',
    niche_keyword='platform engineering',
    image_styles=[
        'blueprint',
        'isometric_3d',
        'server_room',
        'low_poly',
    ],
    featured_image=True,
    draft=False,
    rss_queries=[
        'Internal developer platform',
        'Platform engineering vs DevOps',
        'Backstage developer portal',
        'Golden paths developer experience',
        'IDP tooling comparison',
        'Self-service infrastructure',
        'Developer experience metrics',
        'Platform team operating model',
        'Kubernetes platform abstraction',
        'DORA metrics improvement',
    ],
    tags=[
        'PlatformEngineering',
        'InternalDeveloperPlatform',
        'DeveloperExperience',
        'DevOps',
        'GoldenPaths',
        'DORAMetrics',
    ],
)
