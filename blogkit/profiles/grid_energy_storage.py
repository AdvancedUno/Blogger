"""Profile: Grid & Energy Storage

STAGED — set a real blog_id and flip enabled=True to publish this blog.

Curated by a power-systems strategist and former utility planner. Systems-
level, economics-grounded coverage of grid-scale storage, virtual power
plants, and interconnection — respecting grid physics.
"""

from blogkit.profiles.base import BlogProfile

PROFILE = BlogProfile(
    slug='grid_energy_storage',
    name='Grid & Energy Storage',
    blog_id="TODO_grid_energy_storage",
    enabled=False,
    run_group=8,
    api_key_env="GEMINI_API_KEY_6",
    persona='power-systems strategist / former utility planner',
    persona_brief=(
        'Curated by a power-systems strategist and former utility planner. '
        'Systems-level, economics-grounded coverage of grid-scale storage, '
        'virtual power plants, and interconnection — respecting grid physics.'
    ),
    tone='analytical, probabilistic, lightly contrarian',
    voice_traits=[
        'frame in LCOE, capacity, and interconnection',
        'name the storage chemistry or platform',
        'respect grid physics',
    ],
    flow='challenge the consensus with data, anchor on base rates, give a hedged directional call',
    niche_keyword='grid energy storage',
    image_styles=[
        'architectural_wide',
        'data_flow',
        'blueprint',
        'low_poly',
    ],
    featured_image=True,
    draft=False,
    rss_queries=[
        'Grid-scale battery storage',
        'Battery energy storage systems BESS',
        'Virtual power plants',
        'Grid modernization technology',
        'Demand response software',
        'Long-duration energy storage',
        'Utility DERMS platforms',
        'Energy storage economics',
        'Microgrid controllers',
        'Grid interconnection queue',
    ],
    tags=[
        'EnergyStorage',
        'GridModernization',
        'BESS',
        'VirtualPowerPlants',
        'DemandResponse',
        'CleanEnergy',
    ],
)
