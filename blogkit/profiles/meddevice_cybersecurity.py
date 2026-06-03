"""Profile: MedDevice Cybersecurity

Written by a hospital CISO with hands-on IoMT remediation experience across
legacy and connected device fleets. Direct guidance on FDA software
compliance, SBOM management, and ransomware defense for clinical networks.
"""

from blogkit.profiles.base import BlogProfile

PROFILE = BlogProfile(
    slug='meddevice_cybersecurity',
    name='MedDevice Cybersecurity',
    blog_id='3888183183588974870',
    run_group=3,
    api_key_env='GEMINI_API_KEY_3',
    persona='veteran CISO / Cyber Intelligence Director',
    persona_brief=(
        'Written by a hospital CISO with hands-on IoMT remediation experience '
        'across legacy and connected device fleets. Direct guidance on FDA '
        'software compliance, SBOM management, and ransomware defense for '
        'clinical networks.'
    ),
    niche_keyword='meddevice cybersecurity',
    image_styles=[
        'macro_chip',
        'server_room',
        'blueprint',
        'double_exposure',
        'surreal_business',
    ],
    featured_image=True,
    draft=False,
    rss_queries=[
        'Internet of Medical Things (IoMT) security',
        'FDA medical device software compliance',
        'Hospital network threat detection',
        'Legacy medical equipment patching',
        'MedTech vulnerability scanning',
        'Medical device SBOM (Software Bill of Materials)',
        'Zero trust in hospital IT',
        'Ransomware defense for healthcare',
        'Wearable medical device encryption',
        'Connected pacemaker cybersecurity',
    ],
    tags=[],
)
