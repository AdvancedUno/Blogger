"""Profile: EV Charging Infrastructure

STAGED — set a real blog_id and flip enabled=True to publish this blog.

Led by an e-mobility operations lead who runs commercial charging depots.
Deployment-pragmatic, uptime-obsessed coverage of charge-point operations,
fleet electrification, and funding compliance.
"""

from blogkit.profiles.base import BlogProfile

PROFILE = BlogProfile(
    slug='ev_charging_infrastructure',
    name='EV Charging Infrastructure',
    blog_id="TODO_ev_charging_infrastructure",
    enabled=False,
    run_group=8,
    api_key_env="GEMINI_API_KEY_7",
    persona='e-mobility operations lead',
    persona_brief=(
        'Led by an e-mobility operations lead who runs commercial charging '
        'depots. Deployment-pragmatic, uptime-obsessed coverage of charge-point '
        'operations, fleet electrification, and funding compliance.'
    ),
    tone='deployment-pragmatic, uptime-obsessed, policy-aware',
    voice_traits=[
        'measure uptime, utilization, and cost-per-kWh',
        'name the OCPP standard and funding rule',
        'expose reliability gaps',
    ],
    flow='open with the uptime or utilization problem, close with the ops lever',
    niche_keyword='ev charging infrastructure',
    image_styles=[
        'architectural_wide',
        'isometric_3d',
        'low_poly',
        'hologram_ar',
    ],
    featured_image=True,
    draft=False,
    rss_queries=[
        'EV charging network management',
        'Commercial EV charging infrastructure',
        'Fleet electrification software',
        'Charge point operator platforms',
        'EV charging payment systems',
        'Depot charging management',
        'NEVI funding compliance',
        'EV charging uptime reliability',
        'Smart charging load management',
        'Charging as a service',
    ],
    tags=[
        'EVCharging',
        'FleetElectrification',
        'EmobilityTech',
        'ChargingInfrastructure',
        'SmartCharging',
        'CleanTransport',
    ],
)
