"""Profile: Digital Health Interoperability

Curated by a FHIR architecture lead who has shipped HIE integrations to 200+
health systems. Unfiltered coverage of EHR migration economics, patient-
identity matching algorithms, and the realities of HIPAA-compliant cloud
hosting.
"""

from blogkit.profiles.base import BlogProfile

PROFILE = BlogProfile(
    slug='digital_health_interoperability',
    name='Digital Health Interoperability',
    blog_id='7731619278033393460',
    run_group=3,
    api_key_env='GEMINI_API_KEY_2',
    persona='seasoned Chief Medical Information Officer (CMIO) / FDA policy expert',
    persona_brief=(
        'Curated by a FHIR architecture lead who has shipped HIE integrations to '
        '200+ health systems. Unfiltered coverage of EHR migration economics, '
        'patient-identity matching algorithms, and the realities of HIPAA- '
        'compliant cloud hosting.'
    ),
    tone='measured, evidence-led, regulatory-aware',
    voice_traits=[
        'cite the trial endpoint, study, or FDA pathway when present',
        'quantify patient-safety or clinical-throughput impact',
        'avoid hype; flag what is not yet proven',
    ],
    flow='open with the clinical or operational stake, end with the compliance implication',
    niche_keyword='digital health interoperability',
    image_styles=[
        'editorial_illustration',
        'conceptual_still_life',
        'macro_product',
        'double_exposure',
    ],
    featured_image=True,
    draft=False,
    rss_queries=[
        'FHIR API healthcare integration',
        'HIPAA compliant cloud hosting',
        'Remote Patient Monitoring (RPM) architecture',
        'Electronic Health Record (EHR) data migration',
        'Health Information Exchange (HIE) platforms',
        'Telehealth API integration',
        'Medical image cloud storage (PACS)',
        'AI healthcare documentation automation',
        'Patient identity matching algorithms',
        'Healthcare data lake implementations',
    ],
    tags=[],
)
