"""Profile: Quantum Commercialization

Curated by a quantum computing researcher turned enterprise advisor on post-
quantum migration. Practical guidance on NIST PQC standards, QKD networks, and
the realistic enterprise timeline for quantum-resistant infrastructure.
"""

from blogkit.profiles.base import BlogProfile

PROFILE = BlogProfile(
    slug='quantum_commercialization',
    name='Quantum Commercialization',
    blog_id='7093969680450817058',
    run_group=1,
    api_key_env='GEMINI_API_KEY_5',
    persona='Enterprise CTO / Lead Systems Architect',
    persona_brief=(
        'Curated by a quantum computing researcher turned enterprise advisor on '
        'post-quantum migration. Practical guidance on NIST PQC standards, QKD '
        'networks, and the realistic enterprise timeline for quantum-resistant '
        'infrastructure.'
    ),
    niche_keyword='quantum commercialization',
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
        'Quantum-safe cryptography migration',
        'Quantum computing SaaS platforms',
        'Enterprise quantum algorithms',
        'Post-quantum cybersecurity standards',
        'Quantum key distribution (QKD) networks',
        'Quantum computing hardware advancements',
        'Quantum machine learning in finance',
        'NIST post-quantum encryption algorithms',
        'Hybrid quantum-classical computing',
        'Quantum error correction methods',
    ],
    tags=[],
)
