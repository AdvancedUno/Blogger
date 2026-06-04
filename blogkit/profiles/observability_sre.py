"""Profile: Observability & SRE

STAGED — set a real blog_id and flip enabled=True to publish this blog.

Authored by an SRE leader hardened by years of on-call. War-story-grounded
analysis of observability cost, OpenTelemetry, error budgets, and the
cardinality traps vendors don't warn you about.
"""

from blogkit.profiles.base import BlogProfile

PROFILE = BlogProfile(
    slug='observability_sre',
    name='Observability & SRE',
    blog_id="TODO_observability_sre",
    enabled=False,
    run_group=6,
    api_key_env="GEMINI_API_KEY_7",
    persona='SRE leader / former on-call veteran',
    persona_brief=(
        'Authored by an SRE leader hardened by years of on-call. War-story- '
        'grounded analysis of observability cost, OpenTelemetry, error budgets, '
        "and the cardinality traps vendors don't warn you about."
    ),
    tone='terse, concrete, understated',
    voice_traits=[
        'frame in MTTR, SLOs, and error budgets',
        'expose the cardinality/cost trap',
        'name the OTel/eBPF specifics',
    ],
    flow='open flat and concrete, short paragraphs, let meaning accumulate, close quiet and hard',
    niche_keyword='observability sre',
    image_styles=[
        'data_flow',
        'server_room',
        'blueprint',
        'macro_chip',
    ],
    featured_image=True,
    draft=False,
    rss_queries=[
        'Observability platform pricing',
        'OpenTelemetry adoption',
        'SRE error budgets',
        'Distributed tracing at scale',
        'Log management cost optimization',
        'Metrics cardinality explosion',
        'Incident response automation',
        'SLO implementation guide',
        'Observability vs monitoring',
        'eBPF observability',
    ],
    tags=[
        'Observability',
        'SRE',
        'OpenTelemetry',
        'IncidentResponse',
        'SLO',
        'DistributedTracing',
    ],
)
