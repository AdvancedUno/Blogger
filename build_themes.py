"""build_themes.py — bulk-customize JetTheme v2.9 XML for the blog network.

Reads `JetTheme_v2.9.xml` from the project root, applies 6 customization
rules per blog, and writes the per-blog XML to `themes_output/`.

Usage:
    # Show what would be written, no files created
    python build_themes.py --dry-run

    # Test on a single blog (substring match on blog name)
    python build_themes.py --blog "AI Infra"

    # Write all 20 customized theme XMLs
    python build_themes.py

Each output file is a complete, ready-to-upload Blogger XML theme:
    Blogger Dashboard -> Theme -> Restore -> Upload .xml
"""
from __future__ import annotations

import argparse
import logging
import re
import sys
from html import escape as html_escape
from pathlib import Path

BASE_THEME_PATH = Path(__file__).parent / "JetTheme_v2.9.xml"
OUTPUT_DIR = Path(__file__).parent / "themes_output"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("build_themes")


# =====================================================================
# Blog data — edit the bios below to match each blog's editorial voice.
# Keys are the blog display names (used as <h2> header text + copyright).
# Values are the footer "About Us" bio text (HTML21 widget content).
# =====================================================================
BLOGS: dict[str, str] = {
    # ----- TECH & INFRASTRUCTURE (Enterprise CTO / Systems Architect) -----
    "AI Infra Insider": (
        "Curated by a senior systems architect with 15+ years building "
        "hyperscale infrastructure for Fortune 500 enterprises. We cut "
        "through vendor marketing to expose the real operational economics "
        "of enterprise LLM deployments, GPU cluster TCO, and AI workload "
        "orchestration."
    ),
    "Zero Trust Enterprise": (
        "Authored by a veteran CISO with hands-on Zero Trust rollout "
        "experience across banking, healthcare, and federal contracting. "
        "Translating CISA frameworks and NIST guidance into deployment-"
        "ready architecture decisions for security leaders."
    ),
    "DataOps & Vector DBs": (
        "Written by a former Principal Data Engineer at a top-tier hedge "
        "fund, now advising Series B-D AI startups on data infrastructure. "
        "Expect unfiltered teardowns of vector DB pricing, RAG latency, "
        "and lakehouse migration patterns."
    ),
    "Industrial Edge AI": (
        "Led by a Global VP of Operations who has automated discrete "
        "manufacturing across three continents. Real-world analysis of "
        "Industrial IoT cybersecurity, predictive maintenance ROI, and "
        "5G private network deployment economics."
    ),
    "Quantum Commercialization": (
        "Curated by a quantum computing researcher turned enterprise "
        "advisor on post-quantum migration. Practical guidance on NIST "
        "PQC standards, QKD networks, and the realistic enterprise "
        "timeline for quantum-resistant infrastructure."
    ),
    # ----- FINANCE & FINTECH (Wall Street / Fintech VC) -----
    "B2B Payment Rails": (
        "Written by a former payments product lead at a top-tier fintech "
        "who has shipped cross-border B2B rails to enterprise treasurers. "
        "Sharp analysis of ISO 20022 migration, RTP integration patterns, "
        "and stablecoin settlement economics."
    ),
    "Institutional Digital Assets": (
        "Authored by a former institutional crypto trading desk lead with "
        "hands-on tokenization deal experience. Unfiltered coverage of "
        "RWA market structure, custody architecture, and the regulatory "
        "frameworks shaping institutional flow."
    ),
    "WealthTech Systems": (
        "Curated by a Fintech VC with 12+ years investing in wealth "
        "management technology and family-office systems. Strategic "
        "analysis of advisor tech stacks, direct indexing platforms, "
        "and AI-driven portfolio construction."
    ),
    "Enterprise InsurTech": (
        "Led by an actuary turned product strategist who has launched "
        "commercial property and casualty platforms across three major "
        "carriers. Hard data on AI underwriting accuracy, parametric "
        "coverage structures, and embedded insurance economics."
    ),
    "Corporate Treasury Tech": (
        "Written by a corporate treasurer-turned-advisor with TMS "
        "implementation experience at five Fortune 1000 firms. Practical "
        "guidance on liquidity management software, FX hedging platforms, "
        "and multibank connectivity APIs."
    ),
    # ----- HEALTHCARE (CMIO / FDA Policy Expert) -----
    "Clinical Trial Tech": (
        "Authored by a former Chief Medical Information Officer with DCT "
        "rollout experience at three major sponsors. Realistic analysis "
        "of EDC system migration, patient recruitment AI accuracy, and "
        "RWE data validation pipelines."
    ),
    "Digital Health Interoperability": (
        "Curated by a FHIR architecture lead who has shipped HIE "
        "integrations to 200+ health systems. Unfiltered coverage of EHR "
        "migration economics, patient-identity matching algorithms, and "
        "the realities of HIPAA-compliant cloud hosting."
    ),
    "MedDevice Cybersecurity": (
        "Written by a hospital CISO with hands-on IoMT remediation "
        "experience across legacy and connected device fleets. Direct "
        "guidance on FDA software compliance, SBOM management, and "
        "ransomware defense for clinical networks."
    ),
    # ----- REAL ESTATE (Portfolio Manager / PropTech) -----
    "Commercial PropTech": (
        "Led by a former portfolio manager at a top-tier REIT who now "
        "advises PropTech founders. Sharp analysis of lease admin "
        "automation, tenant experience platforms, and the ROI math "
        "behind smart-HVAC investments."
    ),
    "Smart Building ESG": (
        "Curated by a sustainability engineer with carbon-accounting "
        "deployment experience across 500M+ sq ft of commercial real "
        "estate. Practical guidance on Scope 3 reporting, LEED tracking "
        "software, and net-zero strategy execution."
    ),
    # ----- LOGISTICS & OPERATIONS (Global VP of Ops) -----
    "Supply Chain Visibility": (
        "Authored by a Global VP of Supply Chain Operations who has "
        "rolled out control-tower platforms across consumer-goods and "
        "industrial OEMs. Unfiltered teardowns of freight-API "
        "integrations, MEIO algorithms, and 3PL platform economics."
    ),
    "Autonomous Fleet Ops": (
        "Written by a former director of fleet operations at a top-3 "
        "logistics company who specializes in warehouse robotics ROI. "
        "Hard data on AGV/AMR economics, last-mile routing AI, and "
        "commercial EV charging-API integration patterns."
    ),
    # ----- COMPLIANCE & LEGAL -----
    "Cyber Compliance Automation": (
        "Led by a former GRC director at a Big 4 firm with audit "
        "experience across SOC 2, ISO 27001, and HIPAA programs. "
        "Practical guidance on compliance automation platforms, vendor "
        "risk assessments, and continuous monitoring economics."
    ),
    "LegalTech Enterprise": (
        "Curated by a former General Counsel who has deployed CLM "
        "platforms across two Fortune 500 legal departments. Strategic "
        "analysis of AI contract review accuracy, e-discovery platform "
        "selection, and outside-counsel management economics."
    ),
    # ----- REVENUE & SALES OPERATIONS -----
    "Enterprise RevOps": (
        "Authored by a former CRO with 10+ years building RevOps "
        "functions at B2B SaaS scale-ups. Direct analysis of CPQ "
        "platform economics, conversation intelligence accuracy, and "
        "the realistic ROI of pipeline-forecasting AI."
    ),
}


# =====================================================================
# Standard 5 navigation links — used in both the main menu (LinkList11)
# and the footer link list (LinkList13).
# =====================================================================
STANDARD_LINKS: list[tuple[str, str]] = [
    ("Home", "/"),
    ("About Us", "/p/about-us.html"),
    ("Contact Us", "/p/contact-us.html"),
    ("Editorial Standards", "/p/editorial-standards.html"),
    ("Privacy Policy", "/p/privacy-policy.html"),
    ("Terms of Service", "/p/terms-of-service.html"),
]


# =====================================================================
# Low-level helpers
# =====================================================================
def _xml_escape(text: str) -> str:
    """Escape `&`, `<`, `>` for embedding inside a widget-setting element
    body. Leaves quotes alone — settings bodies aren't attribute values.
    """
    return html_escape(text, quote=False)


def _slug(name: str) -> str:
    s = re.sub(r"[^\w\-]+", "_", name.strip())
    return re.sub(r"_+", "_", s).strip("_")[:60] or "unnamed"


# =====================================================================
# Widget-scoped replacement helpers
# Each helper anchors on a specific widget id so changes don't bleed
# into adjacent widgets. The non-greedy `[\s\S]*?` lets us span newlines
# without re.DOTALL (keeps the rest of the pattern strict).
# =====================================================================
def _replace_html_widget_content(
    xml: str,
    widget_id: str,
    new_content: str,
    *,
    wrap_in_paragraph: bool = False,
) -> tuple[str, bool]:
    """Replace the body of <b:widget-setting name='content'> inside the
    HTML widget with the given id.

    Always wraps the replacement in <![CDATA[...]]>. JetTheme's original
    XML uses CDATA for every HTML widget's `content` setting, and Blogger's
    restore-validator rejects the file if we drop the wrapper. Inside CDATA
    the `<`, `>`, and `&` chars are all literal so no entity encoding is
    needed (the one forbidden sequence is `]]>`, which won't appear in any
    of our blog names or bios).

    Pass wrap_in_paragraph=True for plain-prose content like the footer
    bio so the rendered HTML still has paragraph structure (matching the
    JetTheme original's <p>Lorem ipsum...</p>).
    """
    pattern = re.compile(
        r"(<b:widget\b[^>]*?\bid=['\"]" + re.escape(widget_id) + r"['\"][^>]*?>"
        r"[\s\S]*?<b:widget-setting\s+name=['\"]content['\"]\s*>)"
        r"[\s\S]*?"
        r"(</b:widget-setting>)",
    )
    body = f"<p>{new_content}</p>" if wrap_in_paragraph else new_content
    cdata = f"<![CDATA[{body}]]>"
    new_xml, n = pattern.subn(
        lambda m: m.group(1) + cdata + m.group(2),
        xml,
        count=1,
    )
    return new_xml, (n > 0)


def _replace_widget_settings_block(
    xml: str,
    widget_id: str,
    new_settings_xml: str,
) -> tuple[str, bool]:
    """Replace the entire <b:widget-settings>...</b:widget-settings> block
    inside the widget with the given id.

    new_settings_xml is dropped in verbatim; the caller is responsible
    for ensuring it is a well-formed `<b:widget-settings>` block.
    """
    pattern = re.compile(
        r"(<b:widget\b[^>]*?\bid=['\"]" + re.escape(widget_id) + r"['\"][^>]*?>"
        r"[\s\S]*?)"
        r"<b:widget-settings>[\s\S]*?</b:widget-settings>"
        r"([\s\S]*?</b:widget>)",
    )
    new_xml, n = pattern.subn(
        lambda m: m.group(1) + new_settings_xml + m.group(2),
        xml,
        count=1,
    )
    return new_xml, (n > 0)


def _build_links_settings(links: list[tuple[str, str]]) -> str:
    """Build a `<b:widget-settings>` block in Blogger's stock LinkList schema.

    JetTheme + Blogger's restore-validator both require:
      <b:widget-setting name='sorting'>NONE</b:widget-setting>
      <b:widget-setting name='text-0'>{label}</b:widget-setting>
      <b:widget-setting name='link-0'>{url}</b:widget-setting>
      <b:widget-setting name='text-1'>...</b:widget-setting>
      <b:widget-setting name='link-1'>...</b:widget-setting>
      ...

    Using the label as the setting `name` (which is what the previous
    version did) makes Blogger reject the whole XML on restore.
    """
    parts = ["<b:widget-settings>",
             "        <b:widget-setting name='sorting'>NONE</b:widget-setting>"]
    for i, (label, url) in enumerate(links):
        parts.append(
            f"        <b:widget-setting name='text-{i}'>"
            f"{_xml_escape(label)}</b:widget-setting>"
        )
        parts.append(
            f"        <b:widget-setting name='link-{i}'>"
            f"{_xml_escape(url)}</b:widget-setting>"
        )
    parts.append("      </b:widget-settings>")
    return "\n".join(parts)


# An EMPTY <b:widget-settings></b:widget-settings> is rejected by Blogger
# for LinkList widgets — they require at least a `sorting` setting. Keep
# the single sorting line; the JetSocial / JetSearch includes render
# nothing when there are no text-N/link-N pairs.
EMPTY_LINKLIST_SETTINGS = (
    "<b:widget-settings>\n"
    "        <b:widget-setting name='sorting'>NONE</b:widget-setting>\n"
    "      </b:widget-settings>"
)


# =====================================================================
# Per-blog transform — applies the 6 rules, reports which fired
# =====================================================================
def transform_for_blog(
    xml: str,
    blog_name: str,
    bio_text: str,
) -> tuple[str, dict[str, object]]:
    """Apply all 6 customization rules. Returns (new_xml, status_dict).

    Status dict maps each rule id to True/False (matched/not-matched), or
    to an int count for the global rule 6 ad-placeholder cleanup. Lets
    the caller warn when a widget id couldn't be found in the base XML.
    """
    status: dict[str, object] = {}

    # Rule 1 — HTML10 header logo: image URL -> styled <h2>{blog_name}</h2>.
    # JetTheme's header uses a flex layout to align the menu items, but the
    # browser-default top/bottom margin on <h2> (~0.83em) pushes the logo
    # text off-center vs the menu. Inline-styles zero the margins, force
    # inline-block + vertical-align:middle so the logo sits on the same
    # baseline as Home / About Us / etc. Inside CDATA, no escaping needed.
    header_logo_html = (
        f"<h2 style=\"margin:0; padding:0; "
        f"font-size:1.6em; line-height:1; font-weight:700; "
        f"display:inline-block; vertical-align:middle;\">"
        f"{blog_name}</h2>"
    )
    xml, status["rule1_HTML10_logo"] = _replace_html_widget_content(
        xml, "HTML10", header_logo_html,
    )

    # Rule 2 — LinkList11 main menu: replace with 5 flat links
    xml, status["rule2_LinkList11_nav"] = _replace_widget_settings_block(
        xml, "LinkList11", _build_links_settings(STANDARD_LINKS),
    )

    # Rule 3 — HTML21 footer About: replace Lorem ipsum with bio.
    # Original was <p>Lorem ipsum...</p> — preserve the <p> wrap so the
    # rendered footer has correct paragraph block-spacing.
    xml, status["rule3_HTML21_bio"] = _replace_html_widget_content(
        xml, "HTML21", bio_text, wrap_in_paragraph=True,
    )

    # Rule 4a — LinkList13 footer links: same 5 standard links
    xml, status["rule4a_LinkList13_footer"] = _replace_widget_settings_block(
        xml, "LinkList13", _build_links_settings(STANDARD_LINKS),
    )

    # Rule 4b — LinkList10 social: empty
    xml, status["rule4b_LinkList10_social"] = _replace_widget_settings_block(
        xml, "LinkList10", EMPTY_LINKLIST_SETTINGS,
    )

    # Rule 4c — LinkList14 social: empty
    xml, status["rule4c_LinkList14_social"] = _replace_widget_settings_block(
        xml, "LinkList14", EMPTY_LINKLIST_SETTINGS,
    )

    # Rule 5 — HTML23 copyright. Inside CDATA, `&#169;` is the literal
    # text "&#169;" — when the HTML widget renders this string the
    # browser's HTML parser decodes it to (c). So this works as intended.
    copyright_html = (
        f"Copyright &#169; 2026 {blog_name}. All Rights Reserved."
    )
    xml, status["rule5_HTML23_copyright"] = _replace_html_widget_content(
        xml, "HTML23", copyright_html,
    )

    # Rule 6 — global cleanup of <hr class="example-ads"/> placeholders.
    # The HR may appear two ways in the XML stream:
    #   - raw inside a <b:includable> template chunk
    #   - entity-encoded inside an HTML widget setting
    # Replace both.
    raw_pat = re.compile(r"<hr\s+class=['\"]example-ads['\"]\s*/?>")
    enc_pat = re.compile(r"&lt;hr\s+class=['\"]example-ads['\"]\s*/?&gt;")
    n_raw = len(raw_pat.findall(xml))
    n_enc = len(enc_pat.findall(xml))
    xml = raw_pat.sub("<!-- AdSense Reserved -->", xml)
    xml = enc_pat.sub("&lt;!-- AdSense Reserved --&gt;", xml)
    status["rule6_ad_placeholders_replaced"] = n_raw + n_enc

    return xml, status


# =====================================================================
# CLI
# =====================================================================
def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Bulk-customize JetTheme v2.9 XML for every blog",
    )
    p.add_argument(
        "--dry-run", action="store_true",
        help="Compute transforms and report per-rule matches without "
             "writing any files.",
    )
    p.add_argument(
        "--blog", default=None,
        help="Only process blogs whose name CONTAINS this substring "
             "(case-insensitive).",
    )
    return p.parse_args()


def main() -> int:
    args = _parse_args()
    if not BASE_THEME_PATH.exists():
        logger.error(
            "Base theme not found: %s\nPlace JetTheme_v2.9.xml at the "
            "project root and re-run.", BASE_THEME_PATH,
        )
        return 1

    base_xml = BASE_THEME_PATH.read_text(encoding="utf-8")
    logger.info("Loaded base theme: %s (%d chars)",
                BASE_THEME_PATH.name, len(base_xml))

    items = list(BLOGS.items())
    if args.blog:
        needle = args.blog.lower()
        items = [(n, b) for n, b in items if needle in n.lower()]
        logger.info("Filtered by --blog=%r -> %d blog(s)", args.blog, len(items))
        if not items:
            return 0

    if not args.dry_run:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    written = 0
    warned = 0
    for blog_name, bio in items:
        logger.info("================ %s ================", blog_name)
        new_xml, status = transform_for_blog(base_xml, blog_name, bio)

        any_missing = False
        for rule, result in status.items():
            if isinstance(result, bool):
                tag = "OK  " if result else "MISS"
                if not result:
                    any_missing = True
                logger.info("  %s  %s", tag, rule)
            else:
                logger.info("  OK    %s = %s", rule, result)

        if any_missing:
            warned += 1
            logger.warning(
                "  [%s] One or more widget ids didn't match the base XML — "
                "output is still written but may be incomplete.",
                blog_name,
            )

        if args.dry_run:
            logger.info("  [dry-run] would write %d chars", len(new_xml))
        else:
            out_path = OUTPUT_DIR / f"{_slug(blog_name)}_theme.xml"
            out_path.write_text(new_xml, encoding="utf-8")
            logger.info("  Wrote %s (%d chars)", out_path, len(new_xml))
            written += 1

    logger.info("=================== SUMMARY ===================")
    logger.info("  Blogs processed : %d", len(items))
    if not args.dry_run:
        logger.info("  Files written   : %d", written)
    logger.info("  With warnings   : %d", warned)
    logger.info("  Output dir      : %s", OUTPUT_DIR.resolve())
    return 0 if warned == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
