"""Profile: Cyber Compliance Automation

Led by a former GRC director at a Big 4 firm with audit experience across SOC
2, ISO 27001, and HIPAA programs. Practical guidance on compliance automation
platforms, vendor risk assessments, and continuous monitoring economics.
"""

from blogkit.profiles.base import BlogProfile

PROFILE = BlogProfile(
    slug='cyber_compliance_automation',
    name='Cyber Compliance Automation',
    blog_id='2594397222220490820',
    run_group=4,
    api_key_env='GEMINI_API_KEY_8',
    persona='veteran CISO / Cyber Intelligence Director',
    persona_brief=(
        'Led by a former GRC director at a Big 4 firm with audit experience '
        'across SOC 2, ISO 27001, and HIPAA programs. Practical guidance on '
        'compliance automation platforms, vendor risk assessments, and continuous '
        'monitoring economics.'
    ),
    niche_keyword='cyber compliance automation',
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
        'SOC 2 compliance automation SaaS',
        'GDPR data privacy APIs',
        'ISO 27001 readiness platforms',
        'Continuous compliance monitoring',
        'Enterprise risk management (ERM) software',
        'Third-party vendor risk assessment',
        'HIPAA compliance management tools',
        'CCPA data mapping software',
        'Cyber incident response playbooks',
        'Governance Risk and Compliance (GRC) platforms',
    ],
    tags=[],
)
