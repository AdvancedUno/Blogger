"""Profile: Industrial Edge AI

Led by a Global VP of Operations who has automated discrete manufacturing
across three continents. Real-world analysis of Industrial IoT cybersecurity,
predictive maintenance ROI, and 5G private network deployment economics.
"""

from blogkit.profiles.base import BlogProfile

PROFILE = BlogProfile(
    slug='industrial_edge_ai',
    name='Industrial Edge AI',
    blog_id='45872662805561713',
    run_group=1,
    api_key_env='GEMINI_API_KEY_4',
    persona='Enterprise CTO / Lead Systems Architect',
    persona_brief=(
        'Led by a Global VP of Operations who has automated discrete '
        'manufacturing across three continents. Real-world analysis of Industrial '
        'IoT cybersecurity, predictive maintenance ROI, and 5G private network '
        'deployment economics.'
    ),
    niche_keyword='industrial edge ai',
    image_styles=[
        'macro_chip',
        'server_room',
        'blueprint',
        'isometric_3d',
        'data_flow',
        'hologram_ar',
        'low_poly',
    ],
    featured_image=True,
    draft=False,
    rss_queries=[
        'Edge computing hardware for manufacturing',
        'Industrial IoT (IIoT) cybersecurity',
        'SCADA system modernization',
        'Computer vision in quality control',
        'Predictive maintenance AI algorithms',
        '5G private networks for factories',
        'Edge AI latency reduction techniques',
        'Digital twin factory simulation',
        'Automated guided vehicles (AGV) in manufacturing',
        'Edge machine learning model deployment',
    ],
    tags=[],
)
