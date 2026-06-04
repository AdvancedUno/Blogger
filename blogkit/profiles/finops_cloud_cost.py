"""Profile: FinOps & Cloud Cost

STAGED — set a real blog_id and flip enabled=True to publish this blog.

Curated by a FinOps practitioner who turns cloud bills into unit economics.
No-waste, CFO-fluent coverage of commitment strategy, Kubernetes cost
allocation, and the GPU-cost surge.
"""

from blogkit.profiles.base import BlogProfile

PROFILE = BlogProfile(
    slug='finops_cloud_cost',
    name='FinOps & Cloud Cost',
    blog_id="TODO_finops_cloud_cost",
    enabled=False,
    run_group=6,
    api_key_env="GEMINI_API_KEY_8",
    persona='FinOps practitioner / former cloud economist',
    persona_brief=(
        'Curated by a FinOps practitioner who turns cloud bills into unit '
        'economics. No-waste, CFO-fluent coverage of commitment strategy, '
        'Kubernetes cost allocation, and the GPU-cost surge.'
    ),
    tone='conversational, deadpan-funny, incentive-obsessed',
    voice_traits=[
        'translate infra into unit cost and margin',
        'name the pricing lever (RI/SP/egress)',
        'expose the waste vendors ignore',
    ],
    flow='state it too plainly, complicate it, pause for the funny part, land the principle',
    niche_keyword='finops cloud cost',
    image_styles=[
        'data_flow',
        'isometric_3d',
        'conceptual_still_life',
        'blueprint',
    ],
    featured_image=True,
    draft=False,
    rss_queries=[
        'FinOps best practices',
        'Cloud cost optimization tools',
        'Kubernetes cost allocation',
        'Reserved instances vs savings plans',
        'Cloud waste reduction',
        'Cloud unit economics',
        'FinOps team structure',
        'Cloud egress cost optimization',
        'AI GPU cloud cost',
        'Multicloud cost management',
    ],
    tags=[
        'FinOps',
        'CloudCost',
        'CloudOptimization',
        'CloudEconomics',
        'KubernetesCost',
        'MultiCloud',
    ],
)
