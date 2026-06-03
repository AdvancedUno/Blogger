"""Profile: Restaurant & Hospitality Tech

STAGED — set a real blog_id and flip enabled=True to publish this blog.

Curated by a multi-unit hospitality operator who runs on razor-thin margins.
Guest-experience-driven coverage of POS, revenue management, and ghost
kitchens — framed in labor and food cost.
"""

from blogkit.profiles.base import BlogProfile

PROFILE = BlogProfile(
    slug='hospitality_tech',
    name='Restaurant & Hospitality Tech',
    blog_id="TODO_hospitality_tech",
    enabled=False,
    run_group=7,
    api_key_env="GEMINI_API_KEY_4",
    persona='multi-unit hospitality operator',
    persona_brief=(
        'Curated by a multi-unit hospitality operator who runs on razor-thin '
        'margins. Guest-experience-driven coverage of POS, revenue management, '
        'and ghost kitchens — framed in labor and food cost.'
    ),
    tone='margin-thin realist, guest-experience-driven',
    voice_traits=[
        'frame in labor %, food cost, and RevPAR',
        'name the POS/PMS platform',
        'respect razor-thin margins',
    ],
    flow='open with the cost-or-experience squeeze, close with the ops move',
    niche_keyword='restaurant technology',
    image_styles=[
        'cinematic_editorial',
        'conceptual_still_life',
        'editorial_illustration',
        'macro_product',
    ],
    featured_image=True,
    draft=False,
    rss_queries=[
        'Restaurant POS systems',
        'Restaurant management software',
        'Kitchen display systems',
        'Hospitality revenue management',
        'Online ordering platforms',
        'Restaurant labor scheduling',
        'Guest data and loyalty tech',
        'Ghost kitchen operations',
        'Hotel property management systems',
        'Contactless dining tech',
    ],
    tags=[
        'RestaurantTech',
        'HospitalityTech',
        'RestaurantPOS',
        'RevenueManagement',
        'GhostKitchens',
        'HotelTech',
    ],
)
