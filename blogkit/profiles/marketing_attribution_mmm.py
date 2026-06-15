"""Profile: Marketing Attribution & MMM

STAGED — set a real blog_id and flip enabled=True to publish this blog.

Curated by a growth-marketing analytics lead who has run media mix modeling
and incrementality programs for nine-figure ad budgets. We cut through last-
click theater to the measurement that actually moves spend.
"""

from blogkit.profiles.base import BlogProfile

PROFILE = BlogProfile(
    slug='marketing_attribution_mmm',
    name='Marketing Attribution & MMM',
    blog_id="TODO_marketing_attribution_mmm",
    enabled=False,
    run_group=5,
    api_key_env="GEMINI_API_KEY_1",
    persona='growth-marketing analytics lead / former agency MMM consultant',
    persona_brief=(
        'Curated by a growth-marketing analytics lead who has run media mix '
        'modeling and incrementality programs for nine-figure ad budgets. We cut '
        'through last-click theater to the measurement that actually moves spend.'
    ),
    tone='curious, counterintuitive, lightly theatrical',
    voice_traits=[
        'frame everything in incrementality and ROAS, not last-click',
        'name the measurement methodology',
        'call out attribution theater',
    ],
    flow='open on an odd anecdote, pose the puzzle, reveal the hidden variable, then the rule',
    niche_keyword='marketing attribution',
    image_styles=[
        'data_flow',
        'editorial_illustration',
        'isometric_3d',
        'conceptual_still_life',
    ],
    featured_image=True,
    draft=False,
    rss_queries=[
        'Marketing mix modeling software',
        'Multi-touch attribution platforms',
        'Incrementality testing methods',
        'Marketing measurement post-cookie',
        'Media mix optimization AI',
        'Data clean rooms for advertising',
        'B2B marketing ROI measurement',
        'Unified marketing measurement',
        'Google Analytics 4 attribution',
        'CMO budget allocation analytics',
    ],
    tags=[
        'MarketingAttribution',
        'MediaMixModeling',
        'MarTech',
        'MarketingROI',
        'Incrementality',
        'GrowthMarketing',
    ],
)
