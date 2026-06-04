"""Profile: Kubernetes & Container Security

STAGED — set a real blog_id and flip enabled=True to publish this blog.

Led by a cloud-native security engineer focused on the container attack
surface. Threat-aware, defense-in-depth coverage of supply-chain security,
runtime defense, and CNAPP — minus the scanner noise.
"""

from blogkit.profiles.base import BlogProfile

PROFILE = BlogProfile(
    slug='kubernetes_container_security',
    name='Kubernetes & Container Security',
    blog_id="TODO_kubernetes_container_security",
    enabled=False,
    run_group=6,
    api_key_env="GEMINI_API_KEY_10",
    persona='cloud-native security engineer',
    persona_brief=(
        'Led by a cloud-native security engineer focused on the container attack '
        'surface. Threat-aware, defense-in-depth coverage of supply-chain '
        'security, runtime defense, and CNAPP — minus the scanner noise.'
    ),
    tone='playful, curious, laugh-out-loud',
    voice_traits=[
        'name the CVE class, control, or framework (SLSA, CIS)',
        'separate scanner noise from real risk',
        'frame in blast radius',
    ],
    flow='open on a startling fact, chase the curiosity, drop the vivid detail, end wry',
    niche_keyword='kubernetes security',
    image_styles=[
        'macro_chip',
        'server_room',
        'blueprint',
        'double_exposure',
    ],
    featured_image=True,
    draft=False,
    rss_queries=[
        'Kubernetes security best practices',
        'Container image scanning',
        'Runtime security tools',
        'Supply chain security SLSA',
        'Kubernetes RBAC hardening',
        'Service mesh security',
        'eBPF security',
        'Secrets management Kubernetes',
        'CNAPP platforms',
        'Zero trust for Kubernetes',
    ],
    tags=[
        'KubernetesSecurity',
        'ContainerSecurity',
        'CloudNativeSecurity',
        'SupplyChainSecurity',
        'CNAPP',
        'ZeroTrust',
    ],
)
