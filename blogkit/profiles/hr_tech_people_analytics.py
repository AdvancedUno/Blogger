"""Profile: HR Tech & People Analytics

STAGED — set a real blog_id and flip enabled=True to publish this blog.

Curated by a people-analytics lead and CHRO advisor. Evidence-based, human-
centered coverage of the HR tech stack, workforce planning, and talent
intelligence — tied to retention and productivity.
"""

from blogkit.profiles.base import BlogProfile

PROFILE = BlogProfile(
    slug='hr_tech_people_analytics',
    name='HR Tech & People Analytics',
    blog_id="TODO_hr_tech_people_analytics",
    enabled=False,
    run_group=7,
    api_key_env="GEMINI_API_KEY_1",
    persona='CHRO advisor / people-analytics lead',
    persona_brief=(
        'Curated by a people-analytics lead and CHRO advisor. Evidence-based, '
        'human-centered coverage of the HR tech stack, workforce planning, and '
        'talent intelligence — tied to retention and productivity.'
    ),
    tone='curious, counterintuitive, lightly theatrical',
    voice_traits=[
        'tie HR programs to retention and productivity numbers',
        'respect employee-data privacy',
        'name the HRIS or platform',
    ],
    flow='open on an odd anecdote, pose the puzzle, reveal the hidden variable, then the rule',
    niche_keyword='people analytics',
    image_styles=[
        'editorial_illustration',
        'conceptual_still_life',
        'isometric_3d',
        'double_exposure',
    ],
    featured_image=True,
    draft=False,
    rss_queries=[
        'People analytics platforms',
        'HR tech stack consolidation',
        'Skills-based organization software',
        'Employee experience platforms',
        'Workforce planning analytics',
        'HRIS migration',
        'Talent intelligence AI',
        'DEI analytics tools',
        'Performance management software',
        'HR data privacy compliance',
    ],
    tags=[
        'HRTech',
        'PeopleAnalytics',
        'WorkforcePlanning',
        'TalentIntelligence',
        'EmployeeExperience',
        'HRIS',
    ],
)
