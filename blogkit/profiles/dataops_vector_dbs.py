"""Profile: DataOps & Vector DBs

Written by a former Principal Data Engineer at a top-tier hedge fund, now
advising Series B-D AI startups on data infrastructure. Expect unfiltered
teardowns of vector DB pricing, RAG latency, and lakehouse migration patterns.
"""

from blogkit.profiles.base import BlogProfile

PROFILE = BlogProfile(
    slug='dataops_vector_dbs',
    name='DataOps & Vector DBs',
    blog_id='5504688610815362438',
    run_group=1,
    api_key_env='GEMINI_API_KEY_3',
    persona='Enterprise CTO / Lead Systems Architect',
    persona_brief=(
        'Written by a former Principal Data Engineer at a top-tier hedge fund, '
        'now advising Series B-D AI startups on data infrastructure. Expect '
        'unfiltered teardowns of vector DB pricing, RAG latency, and lakehouse '
        'migration patterns.'
    ),
    tone='analytical, architecture-first, vendor-skeptical',
    voice_traits=[
        'quantify TCO, latency, or scale',
        'separate marketing hype from deployment reality',
        'name the specific system, vendor, or standard',
    ],
    flow='open with a concrete data point, close each section with the strategic implication',
    niche_keyword='dataops  vector dbs',
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
        'Vector database architecture',
        'Retrieval-Augmented Generation (RAG) enterprise',
        'Data pipeline orchestration tools',
        'Unstructured data management SaaS',
        'Enterprise data lakehouse architecture',
        'Real-time streaming analytics pipelines',
        'Master Data Management (MDM) platforms',
        'Graph database use cases in B2B',
        'Snowflake vs Databricks cost analysis',
        'Data observability and quality tools',
    ],
    tags=[],
)
