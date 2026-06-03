"""Profile: Programmatic AdTech & Privacy

STAGED — set a real blog_id and flip enabled=True to publish this blog.

Curated by an ad-tech strategist and former DSP product lead. We follow the ad
dollar through retail media, CTV, and the cookieless transition without the
signal-loss hysteria.
"""

from blogkit.profiles.base import BlogProfile

PROFILE = BlogProfile(
    slug='programmatic_adtech_privacy',
    name='Programmatic AdTech & Privacy',
    blog_id="TODO_programmatic_adtech_privacy",
    enabled=False,
    run_group=5,
    api_key_env="GEMINI_API_KEY_5",
    persona='ad-tech strategist / former DSP product lead',
    persona_brief=(
        'Curated by an ad-tech strategist and former DSP product lead. We follow '
        'the ad dollar through retail media, CTV, and the cookieless transition '
        'without the signal-loss hysteria.'
    ),
    tone='sharp, follow-the-spend, privacy-realist',
    voice_traits=[
        'follow the ad dollar and the take rate',
        'name the privacy regulation or standard',
        'separate signal-loss hype from reality',
    ],
    flow='open with the signal-loss catalyst, end with the budget-shift move',
    niche_keyword='programmatic advertising',
    image_styles=[
        'data_flow',
        'surreal_business',
        'editorial_illustration',
        'glassmorphism',
    ],
    featured_image=True,
    draft=False,
    rss_queries=[
        'Programmatic advertising trends',
        'Privacy Sandbox impact',
        'Retail media networks',
        'Contextual targeting comeback',
        'Server-side ad tracking',
        'CTV advertising platforms',
        'Ad fraud detection',
        'First-party data advertising',
        'Header bidding optimization',
        'Cookieless targeting strategy',
    ],
    tags=[
        'AdTech',
        'ProgrammaticAdvertising',
        'RetailMedia',
        'PrivacySandbox',
        'CTVAdvertising',
        'FirstPartyData',
    ],
)
