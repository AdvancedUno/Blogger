"""One-off AdSense plumbing for every blog profile.

Creates the 5 standard static pages (About Us, Contact Us, Editorial Standards,
Privacy Policy, Terms of Service) on every blog in the profile registry, and can
print the AdSense ads.txt line. Reuses the OAuth refresh-token flow from
`blogkit.core.publisher`.

Required environment variables (same as the daily pipeline):
    GOOGLE_CLIENT_ID
    GOOGLE_CLIENT_SECRET
    GOOGLE_REFRESH_TOKEN

Usage:
    # Preview substitutions without any API write calls
    python setup_pages.py --dry-run

    # Test on a single blog first (substring match on the profile name)
    python setup_pages.py --blog-name "AI Infra" --dry-run
    python setup_pages.py --blog-name "AI Infra"

    # Run it for real across all blogs
    python setup_pages.py

    # Print the ads.txt line to paste into each blog's custom ads.txt setting
    python setup_pages.py --ads-txt pub-1234567890123456

The page creation is idempotent: it lists existing pages on each blog first
and skips any page whose title is already present, so a re-run after a partial
failure won't create duplicates.

    # Replace the OLD thin About/Privacy/Terms pages in place (updates existing
    # pages by title instead of skipping them) — needed to deploy refreshed copy:
    python setup_pages.py --overwrite
"""
from __future__ import annotations

import argparse
import logging
import sys
import time
from typing import TYPE_CHECKING
from urllib.parse import urlparse

if TYPE_CHECKING:
    # mypy always sees the real exception type for annotations / except clauses.
    from googleapiclient.errors import HttpError
else:
    # At runtime the --ads-txt path doesn't need the Google libs; fall back to a
    # base class so `except HttpError` still works when they're absent.
    try:
        from googleapiclient.errors import HttpError
    except ImportError:
        HttpError = Exception

# Reuse the OAuth helper + the blog registry the daily pipeline uses.
from blogkit.core.publisher import _build_service
from blogkit.profiles.base import BlogProfile
from blogkit.profiles.registry import all_profiles

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("setup_pages")

# Blogger v3 enforces a tight per-user WRITE quota — much stricter than
# the 10K/day project quota. Once exceeded, the API enters an extended
# cool-down where every write returns 429 for several minutes regardless
# of pacing, so we err on the side of generous gaps + exponential backoff.
INTER_PAGE_SLEEP_SECONDS = 15.0   # gap between consecutive page inserts
INTER_BLOG_SLEEP_SECONDS = 15.0   # gap between blogs
QUOTA_RETRY_DELAY_SECONDS = 60.0  # 429 → sleep this long before retry 1
MAX_INSERT_ATTEMPTS = 4           # 1 initial + 3 retries (60s, 120s, 240s)


# =====================================================================
# Page templates (HTML with three placeholder tokens that get .replace()'d)
#   [Your Blog Name]
#   [Your Blog URL]
#   [Your Professional Email Address]  (Contact Us only)
# =====================================================================
ABOUT_HTML = """\
<p><strong>[Your Blog Name]</strong> is an independent analysis publication covering the enterprise technology and financial-infrastructure sectors. We exist to do one thing well: turn the day's raw industry news into analysis a working professional can actually use — the implications, the trade-offs, and the decisions behind the headline, not a rehash of the headline itself.</p>

<h2>What We Cover</h2>
<p>Each article starts from primary reporting and public filings, then works outward to the questions our readers actually ask: What changes because of this? Who captures the value and who absorbs the cost? What should a buyer, builder, or operator do differently next quarter? We focus on durable, decision-grade analysis rather than press-release summaries or speculation.</p>
<ul>
  <li><strong>Architecture &amp; operations</strong> — how systems are actually built, deployed, and run in production versus how they are sold.</li>
  <li><strong>Economics &amp; ROI</strong> — total cost of ownership, pricing models, and the numbers that decide whether a project ships.</li>
  <li><strong>Regulation &amp; risk</strong> — the compliance pressures (SEC, FDA, HIPAA, GDPR, CISA, and their peers) that shape every roadmap.</li>
</ul>

<h2>Who We Write For</h2>
<p>Our readers are practitioners and decision-makers: engineers, product leaders, analysts, and the executives who sign off on their budgets. We assume you already read the news; our job is to be worth your time after you have.</p>

<h2>Our Approach</h2>
<p>We hold ourselves to a clear set of editorial principles — sourcing from primary reporting, grounding every figure in the record, separating analysis from advice, and correcting errors promptly. You can read them in full on our <a href="[Your Blog URL]p/editorial-standards.html">Editorial Standards</a> page.</p>

<p>Have a tip, a correction, or feedback? We read everything — reach us through our <a href="[Your Blog URL]p/contact-us.html">Contact</a> page.</p>
"""

CONTACT_HTML = """\
<p>We welcome questions, corrections, story tips, and partnership inquiries from readers and industry professionals. The fastest way to reach us is by email, and we read every message.</p>

<h2>Editorial Inquiries &amp; News Tips</h2>
<p>Spotted an error, have a primary source we should see, or want to suggest a topic? Send the details — links to source material are especially helpful and get a faster response.</p>

<h2>Corrections</h2>
<p>Accuracy matters to us. If you believe something we published is wrong, tell us what and where, and we will review it against the source record and update the article if a correction is warranted. See our <a href="[Your Blog URL]p/editorial-standards.html">Editorial Standards</a> for how we handle corrections.</p>

<h2>Partnerships &amp; Advertising</h2>
<p>For advertising, sponsorship, or content partnerships, please include <strong>"Partnership Inquiry"</strong> in your subject line so we can route it correctly.</p>

<h2>Reach Us by Email</h2>
<p><strong>[Your Professional Email Address]</strong></p>
<p>We typically respond within 24&ndash;48 business hours. Thank you for taking the time to get in touch.</p>
"""

PRIVACY_HTML = """\
<p>At <strong>[Your Blog Name]</strong>, accessible from <a href="[Your Blog URL]">[Your Blog URL]</a>, the privacy of our visitors is a priority. This Privacy Policy explains what information we collect, how we use it, and the choices you have. By using this site you consent to the practices described here. This policy is reviewed periodically; the version on this page is always the one in effect.</p>

<h2>Information We Collect</h2>
<p>We do not ask you to create an account or submit personal information to read our articles. Like most websites, our hosting platform and analytics tools automatically record standard technical log data when you visit, including:</p>
<ul>
  <li>IP address (often truncated or anonymized)</li>
  <li>Browser type and device information</li>
  <li>Referring and exit pages</li>
  <li>Date, time, and duration of the visit</li>
</ul>
<p>This data is aggregated and used to understand traffic trends, diagnose technical problems, and improve the site. It is not used to personally identify you.</p>

<h2>Cookies and Web Beacons</h2>
<p>This site uses cookies to remember preferences and to measure how content is used so we can improve it. Most browsers let you refuse or delete cookies through their settings; doing so will not prevent you from reading our articles.</p>

<h2>Advertising and the Google AdSense / DART Cookie</h2>
<p>We display advertising served by Google and its partners to support our work. Google, as a third-party vendor, uses cookies (including the DoubleClick DART cookie) to serve ads based on your visits to this and other sites. You can opt out of personalized advertising by visiting <a href="https://www.google.com/settings/ads" target="_blank" rel="noopener">Google Ads Settings</a>, and you can learn how Google uses data from sites that use its services at <a href="https://policies.google.com/technologies/partner-sites" target="_blank" rel="noopener">policies.google.com/technologies/partner-sites</a>.</p>

<h2>Third-Party Advertisers</h2>
<p>Third-party ad networks may use cookies, JavaScript, or web beacons in the advertisements that appear on this site. They receive your IP address automatically when this happens. These technologies measure advertising effectiveness and personalize the ad content you see. We have no access to or control over the cookies used by third-party advertisers, and this Privacy Policy does not apply to them; please consult the respective privacy policies of those parties.</p>

<h2>Your Rights (GDPR &amp; CCPA)</h2>
<p>Depending on where you live, you may have the right to access, correct, or request deletion of personal data held about you, and to opt out of the "sale" of personal information as defined by the CCPA. To make such a request, contact us at the address below. We do not knowingly sell personal information.</p>

<h2>Children's Information</h2>
<p>This site is intended for a professional audience and is not directed at children under 13. We do not knowingly collect personal information from children. If you believe a child has provided us information, please contact us and we will remove it.</p>

<h2>Contact</h2>
<p>Questions about this policy can be sent to <strong>[Your Professional Email Address]</strong>.</p>
"""

TERMS_HTML = """\
<p>By accessing <strong>[Your Blog Name]</strong> at <a href="[Your Blog URL]">[Your Blog URL]</a>, you agree to these Terms of Service. If you disagree with any part of them, please discontinue use of the site.</p>

<h2>1. Use of Content</h2>
<p>All articles, graphics, and other materials on this site are provided for general informational purposes. You are welcome to read, share, and link to our content. You may not republish substantial portions of our articles as your own or use them in a misleading way without permission.</p>

<h2>2. Not Professional Advice</h2>
<p>Our content is analysis and commentary, not professional advice. Nothing on this site constitutes financial, investment, legal, medical, or other professional advice, and it should not be relied upon as a substitute for consultation with a qualified professional. Decisions you make based on what you read here are your own responsibility.</p>

<h2>3. Accuracy and "As Is" Disclaimer</h2>
<p>We work to be accurate and to ground our analysis in credible sources, but the materials on this site are provided "as is" without warranties of any kind, express or implied. We do not warrant that the content is complete, current, or error-free. If you spot a mistake, our <a href="[Your Blog URL]p/contact-us.html">Contact</a> page explains how to tell us.</p>

<h2>4. External Links</h2>
<p>Our articles link to third-party websites and sources for attribution and further reading. We are not responsible for the content, accuracy, or practices of those external sites.</p>

<h2>5. Limitation of Liability</h2>
<p>To the fullest extent permitted by law, <strong>[Your Blog Name]</strong> and its contributors will not be liable for any damages arising from your use of, or inability to use, this website or its content.</p>

<h2>6. Changes to These Terms</h2>
<p>We may update these Terms from time to time. Continued use of the site after changes are posted constitutes acceptance of the revised Terms.</p>

<h2>7. Contact</h2>
<p>Questions about these Terms can be sent to <strong>[Your Professional Email Address]</strong>.</p>
"""

EDITORIAL_HTML = """\
<p>At <strong>[Your Blog Name]</strong>, our value to readers depends entirely on being trustworthy and genuinely useful. These standards describe how we research, write, and stand behind our work.</p>

<h2>Sourcing</h2>
<p>Our analysis begins with primary material: original reporting from established outlets, company announcements, regulatory filings, technical documentation, and public data. We attribute the sources behind each article so you can verify the underlying facts and read further.</p>

<h2>Accuracy and Original Analysis</h2>
<p>We do not publish rephrased news. Every article is built to add something the source material does not provide on its own — synthesis across separate developments, the second-order consequences, the trade-offs practitioners weigh, and concrete takeaways. Specific figures, dates, and named entities are grounded in the source record; where a number is illustrative rather than measured, we say so. We do not invent statistics, quotes, vendors, or events.</p>

<h2>Analysis, Not Advice</h2>
<p>Our articles are professional analysis and commentary. They are not financial, legal, medical, or other professional advice, and should not be the sole basis for a decision. See our <a href="[Your Blog URL]p/terms-of-service.html">Terms of Service</a> for the full disclaimer.</p>

<h2>Independence</h2>
<p>Editorial decisions are made independently of advertisers. Advertising and any sponsored material are kept separate from, and clearly distinguishable from, our editorial analysis. A commercial relationship never determines the conclusions of an article.</p>

<h2>Corrections</h2>
<p>We correct errors promptly. If you believe an article contains a factual error, please tell us through our <a href="[Your Blog URL]p/contact-us.html">Contact</a> page with the specifics and, where possible, a source. We review every report against the record and update the article when a correction is warranted.</p>

<h2>Feedback</h2>
<p>Reader feedback makes our work better. We welcome questions, challenges, and story suggestions at <strong>[Your Professional Email Address]</strong>.</p>
"""

# Ordered list of (title, template) tuples. Title is used both as the
# Blogger page title AND as the idempotency key against existing pages.
PAGES: list[tuple[str, str]] = [
    ("About Us", ABOUT_HTML),
    ("Contact Us", CONTACT_HTML),
    ("Editorial Standards", EDITORIAL_HTML),
    ("Privacy Policy", PRIVACY_HTML),
    ("Terms of Service", TERMS_HTML),
]


ADS_TXT_EXCHANGE = "f08c47fec0942fa0"   # Google AdSense ads.txt relationship id


def print_ads_txt(pub_id: str) -> int:
    """Print the ads.txt line for AdSense. Blogger has no API to set ads.txt,
    so this is paste-ready for each blog's custom ads.txt setting."""
    pub = pub_id if pub_id.startswith("pub-") else f"pub-{pub_id}"
    print(f"google.com, {pub}, DIRECT, {ADS_TXT_EXCHANGE}")
    print()
    print("# Paste the line above into EACH blog:")
    print("#   Blogger dashboard -> Settings -> Monetization ->")
    print("#   'Enable custom ads.txt' -> paste -> Save")
    return 0


def _is_rate_limit(err: HttpError) -> bool:
    """Detect Blogger's 429 / rateLimitExceeded / resource-exhausted errors."""
    status = getattr(getattr(err, "resp", None), "status", None)
    try:
        status_int = int(status) if status is not None else None
    except (TypeError, ValueError):
        status_int = None
    if status_int == 429:
        return True
    msg = str(err).lower()
    return any(s in msg for s in (
        "ratelimit",
        "rate limit",
        "resource has been exhausted",
        "quota",
    ))


def _write_page_with_retry(
    service,
    blog_id: str,
    body: dict,
    page_title: str,
    page_id: str | None = None,
) -> dict:
    """pages.insert() (or pages.update() when ``page_id`` is given) wrapper with
    exponential backoff on 429.

    Sleep schedule: 60s, 120s, 240s on consecutive 429s. The doubling
    gives the Blogger quota progressively more time to clear if the API
    has entered a deep cool-down state.
    """
    last_err: HttpError | None = None
    for attempt in range(1, MAX_INSERT_ATTEMPTS + 1):
        try:
            pages = service.pages()
            call = (
                pages.update(blogId=blog_id, pageId=page_id, body=body)
                if page_id
                else pages.insert(blogId=blog_id, body=body, isDraft=False)
            )
            return call.execute()
        except HttpError as e:
            last_err = e
            if _is_rate_limit(e) and attempt < MAX_INSERT_ATTEMPTS:
                # Exponential backoff: 60s → 120s → 240s
                wait = QUOTA_RETRY_DELAY_SECONDS * (2 ** (attempt - 1))
                logger.warning(
                    "  [retry] %s — 429 quota; sleeping %ds, then attempt %d/%d",
                    page_title,
                    int(wait),
                    attempt + 1,
                    MAX_INSERT_ATTEMPTS,
                )
                time.sleep(wait)
                continue
            raise
    assert last_err is not None
    raise last_err


def _list_existing_pages(service, blog_id: str) -> dict[str, str]:
    """Return a {title: page_id} map of pages that already exist on this blog.

    Used for idempotency — a re-run skips (or, with --overwrite, updates) any
    page whose title is already on the blog instead of creating duplicates. The
    id is needed for the update path.
    """
    pages: dict[str, str] = {}
    page_token: str | None = None
    while True:
        kwargs: dict = {"blogId": blog_id, "maxResults": 100}
        if page_token:
            kwargs["pageToken"] = page_token
        resp = service.pages().list(**kwargs).execute()
        for item in resp.get("items") or []:
            title = (item.get("title") or "").strip()
            if title:
                pages[title] = item.get("id") or ""
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return pages


def _substitute(
    template: str,
    blog_name: str,
    blog_url: str,
    contact_email: str,
) -> str:
    return (
        template
        .replace("[Your Blog Name]", blog_name)
        .replace("[Your Blog URL]", blog_url)
        .replace("[Your Professional Email Address]", contact_email)
    )


def _process_blog(
    service,
    profile: BlogProfile,
    dry_run: bool,
    overwrite: bool = False,
) -> tuple[int, int, int, int]:
    """Create (or, with ``overwrite``, refresh) the standard pages on one blog.

    Returns (created, updated, skipped, failed).
    """
    name_cfg = profile.name
    blog_id = str(profile.blog_id or "")

    # Skip placeholder ids like "[YOUR_BLOGGER_ID_8]" or staged "TODO_<slug>"
    # ids — those are unfinished entries the daily pipeline already ignores.
    if not blog_id or blog_id.startswith("[") or blog_id.upper().startswith("TODO"):
        logger.warning("[%s] blog_id is a placeholder (%r) — skipping",
                       name_cfg, blog_id)
        return 0, 0, 0, 0

    # 1) Pull the live name + URL straight from Blogger.
    try:
        blog = service.blogs().get(blogId=blog_id).execute()
    except HttpError as e:
        logger.error("[%s] blogs.get failed for blog_id=%s: %s",
                     name_cfg, blog_id, e)
        return 0, 0, 0, len(PAGES)

    blog_name = (blog.get("name") or name_cfg).strip()
    # Normalize trailing slash so any anchor link/email looks consistent.
    blog_url = (blog.get("url") or "").rstrip("/") + "/"
    domain = urlparse(blog_url).netloc or "example.com"
    contact_email = f"contact@{domain}"

    logger.info("================ %s ================", blog_name)
    logger.info("  blog_id = %s", blog_id)
    logger.info("  url     = %s", blog_url)
    logger.info("  contact = %s", contact_email)

    # 2) Inventory existing pages so we don't create duplicates on re-run.
    try:
        existing = _list_existing_pages(service, blog_id)
    except HttpError as e:
        logger.error("[%s] pages.list failed: %s — will assume zero existing",
                     blog_name, e)
        existing = {}
    if existing:
        logger.info("  Existing pages: %s", sorted(existing))

    created = updated = skipped = failed = 0
    needs_pacing = False  # flip to True after the first real write attempt
    for title, template in PAGES:
        exists = title in existing
        # Without --overwrite, an existing page is left untouched (idempotent).
        if exists and not overwrite:
            logger.info("  [skip] %s — already exists on this blog", title)
            skipped += 1
            continue

        content = _substitute(template, blog_name, blog_url, contact_email)
        body = {
            "kind": "blogger#page",
            "title": title,
            "content": content,
        }
        page_id = existing.get(title) if exists else None
        action = "update" if exists else "create"

        if dry_run:
            logger.info("  [dry-run] %s — would %s (%d chars of HTML)",
                        title, action, len(content))
            if exists:
                updated += 1
            else:
                created += 1
            continue

        # Pace consecutive writes to stay under Blogger's per-user write
        # quota. Skipped pages don't bump this flag because they don't hit
        # the write quota.
        if needs_pacing:
            time.sleep(INTER_PAGE_SLEEP_SECONDS)

        try:
            result = _write_page_with_retry(service, blog_id, body, title, page_id)
            page_url = result.get("url") or "(url not returned)"
            logger.info("  [ok]   %s (%sd) -> %s", title, action, page_url)
            if exists:
                updated += 1
            else:
                created += 1
        except HttpError as e:
            logger.error("  [fail] %s — HTTP error: %s", title, e)
            failed += 1
        except Exception as e:
            logger.error("  [fail] %s — unexpected error: %s", title, e)
            failed += 1
        needs_pacing = True

    return created, updated, skipped, failed


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="One-off bulk page creator for every blog in config.yaml",
    )
    p.add_argument(
        "--dry-run", action="store_true",
        help="Render every substitution and log what would happen without "
             "calling pages.insert(). No live writes.",
    )
    p.add_argument(
        "--blog-name", default=None,
        help="Run only blogs whose profile name CONTAINS this substring "
             "(case-insensitive). Useful for testing one blog first.",
    )
    p.add_argument(
        "--ads-txt", metavar="PUB_ID", default=None,
        help="Print the AdSense ads.txt line for the given publisher id "
             "(e.g. pub-1234567890123456) and exit. No page writes.",
    )
    p.add_argument(
        "--include-disabled", action="store_true",
        help="Also process disabled/staged blogs (default: only enabled blogs).",
    )
    p.add_argument(
        "--overwrite", action="store_true",
        help="Update existing pages (by title) in place instead of skipping "
             "them. Use this to replace OLD thin About/Privacy/Terms pages with "
             "the refreshed copy.",
    )
    return p.parse_args()


def main() -> int:
    args = _parse_args()

    if args.ads_txt:
        return print_ads_txt(args.ads_txt)

    profiles = all_profiles()
    if not profiles:
        logger.error("No blog profiles found")
        return 1

    # Only touch live blogs. Disabled/staged profiles carry TODO_<slug>
    # blog_ids (no real Blogger site yet), so hitting them would just burn
    # the per-user write quota on guaranteed-failing API calls.
    if not args.include_disabled:
        live = [p for p in profiles if p.enabled]
        staged = len(profiles) - len(live)
        if staged:
            logger.info("Skipping %d disabled/staged blog(s) "
                        "(use --include-disabled to override)", staged)
        profiles = live

    if args.blog_name:
        needle = args.blog_name.lower()
        profiles = [p for p in profiles if needle in p.name.lower()]
        logger.info("Filtered by --blog-name=%r -> %d blog(s)",
                    args.blog_name, len(profiles))
        if not profiles:
            return 0

    mode = "DRY-RUN" if args.dry_run else "LIVE (will publish)"
    if args.overwrite:
        mode += " + OVERWRITE existing"
    logger.info("Mode = %s — processing %d blog(s)", mode, len(profiles))
    service = _build_service()

    total_created = total_updated = total_skipped = total_failed = 0
    for idx, profile in enumerate(profiles):
        c, u, s, f = _process_blog(service, profile, args.dry_run, args.overwrite)
        total_created += c
        total_updated += u
        total_skipped += s
        total_failed += f
        if idx < len(profiles) - 1:
            time.sleep(INTER_BLOG_SLEEP_SECONDS)

    logger.info("=================== SUMMARY ===================")
    logger.info("  Mode             : %s", mode)
    logger.info("  Blogs processed  : %d", len(profiles))
    logger.info("  Pages created    : %d", total_created)
    logger.info("  Pages updated    : %d", total_updated)
    logger.info("  Pages skipped    : %d (already existed)", total_skipped)
    logger.info("  Pages failed     : %d", total_failed)

    return 0 if total_failed == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
