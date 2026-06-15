"""Profile: Space & Satellite Connectivity

STAGED — set a real blog_id and flip enabled=True to publish this blog.

Written by an aerospace systems analyst and former satcom engineer. Technical,
economics-aware coverage of LEO connectivity, satellite IoT, and earth
observation — filtering spaceflight hype from unit economics.
"""

from blogkit.profiles.base import BlogProfile

PROFILE = BlogProfile(
    slug='space_satellite_connectivity',
    name='Space & Satellite Connectivity',
    blog_id="TODO_space_satellite_connectivity",
    enabled=False,
    run_group=8,
    api_key_env="GEMINI_API_KEY_10",
    persona='aerospace systems analyst / former satcom engineer',
    persona_brief=(
        'Written by an aerospace systems analyst and former satcom engineer. '
        'Technical, economics-aware coverage of LEO connectivity, satellite IoT, '
        'and earth observation — filtering spaceflight hype from unit economics.'
    ),
    tone='affable, witty, wonder-struck',
    voice_traits=[
        'frame in latency, coverage, and dollars-per-bit',
        'name the constellation or standard',
        'separate spaceflight hype from unit economics',
    ],
    flow='open on an astonishing fact, follow the curiosity, make scale vivid, end delighted',
    niche_keyword='satellite connectivity',
    image_styles=[
        'architectural_wide',
        'hologram_ar',
        'blueprint',
        'surreal_business',
    ],
    featured_image=True,
    draft=False,
    rss_queries=[
        'LEO satellite internet enterprise',
        'Satellite IoT connectivity',
        'Direct-to-device satellite',
        'Ground station as a service',
        'Earth observation data platforms',
        'Satellite spectrum management',
        'Space situational awareness',
        'NGSO constellation economics',
        'Satellite backhaul',
        'In-space manufacturing',
    ],
    tags=[
        'SpaceTech',
        'SatelliteConnectivity',
        'LEOSatellites',
        'SatelliteIoT',
        'EarthObservation',
        'GroundStation',
    ],
)
