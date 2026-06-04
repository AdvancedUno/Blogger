"""Profile: Clinical Trial Tech

Authored by a former Chief Medical Information Officer with DCT rollout
experience at three major sponsors. Realistic analysis of EDC system
migration, patient recruitment AI accuracy, and RWE data validation pipelines.
"""

from blogkit.profiles.base import BlogProfile

PROFILE = BlogProfile(
    slug='clinical_trial_tech',
    name='Clinical Trial Tech',
    blog_id='4562211352181339555',
    run_group=3,
    api_key_env='GEMINI_API_KEY_1',
    persona='seasoned Chief Medical Information Officer (CMIO) / FDA policy expert',
    persona_brief=(
        'Authored by a former Chief Medical Information Officer with DCT rollout '
        'experience at three major sponsors. Realistic analysis of EDC system '
        'migration, patient recruitment AI accuracy, and RWE data validation '
        'pipelines.'
    ),
    tone='calm, humane, exact',
    voice_traits=[
        'cite the trial endpoint, study, or FDA pathway when present',
        'quantify patient-safety or clinical-throughput impact',
        'avoid hype; flag what is not yet proven',
    ],
    flow='open on a concrete case, widen to the system, examine the failure, offer the humble fix',
    niche_keyword='clinical trial tech',
    image_styles=[
        'editorial_illustration',
        'conceptual_still_life',
        'macro_product',
        'double_exposure',
    ],
    featured_image=True,
    draft=False,
    rss_queries=[
        'Decentralized clinical trial software',
        'Electronic Data Capture (EDC) systems',
        'Patient recruitment AI platforms',
        'eCOA and ePRO mobile health apps',
        'Clinical Trial Management Systems (CTMS)',
        'Real-world evidence (RWE) data analytics',
        'Blockchain in clinical trial data',
        'Wearables in remote clinical trials',
        'AI in drug discovery timelines',
        'Clinical supply chain tracking',
    ],
    tags=[],
)
