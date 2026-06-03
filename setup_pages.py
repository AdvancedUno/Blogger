"""One-off bulk page setup for every blog in config.yaml.

Creates the 4 standard static pages (About Us, Contact Us, Privacy Policy,
Terms of Service) on every Blogger site listed in `blogger_sites`. Reuses
the existing OAuth refresh-token flow from `src/blogger_publisher.py`.

Required environment variables (same as the daily pipeline):
    GOOGLE_CLIENT_ID
    GOOGLE_CLIENT_SECRET
    GOOGLE_REFRESH_TOKEN

Usage:
    # 1) Preview substitutions without making any API write calls
    python setup_pages.py --dry-run

    # 2) Test on a single blog first (substring match on config `name`)
    python setup_pages.py --blog-name "AI Infra" --dry-run
    python setup_pages.py --blog-name "AI Infra"

    # 3) Run it for real across all blogs
    python setup_pages.py

The script is idempotent: it lists existing pages on each blog first and
skips any page whose title is already present, so a re-run after a partial
failure won't create duplicates.
"""
from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

import yaml
from googleapiclient.errors import HttpError

# Reuse the OAuth helper the daily pipeline already uses.
from blogkit.core.publisher import _build_service

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("setup_pages")

CONFIG_PATH = Path(__file__).parent / "config.yaml"

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
<p>Welcome to <strong>[Your Blog Name]</strong>, a premier digital publication dedicated to providing high-level macro analysis, architectural breakdowns, and strategic insights into the enterprise technology and financial infrastructure sectors.</p>

<p>In a rapidly accelerating digital economy, C-suite executives, institutional investors, and IT decision-makers require more than just surface-level news. Our mission is to cut through the noise, delivering unfiltered realities, exposing hidden operational friction, and tracking the regulatory pressures that shape the global B2B landscape.</p>

<p>We synthesize real-time market signals and technical data into actionable intelligence, helping organizational leaders map their strategic fiscal quarters and navigate complex infrastructural migrations.</p>

<p>Thank you for trusting <strong>[Your Blog Name]</strong> as your source for elite industry intelligence.</p>
"""

CONTACT_HTML = """\
<p>We welcome inquiries from industry professionals, readers, and potential corporate partners.</p>

<h2>Editorial Inquiries &amp; News Tips</h2>
<p>If you have a pressing market signal, a correction, or an insider tip regarding enterprise infrastructure, please reach out to our editorial team.</p>

<h2>Corporate Partnerships &amp; Sponsorships</h2>
<p>For information regarding B2B advertising, sponsored executive briefings, or lead-generation partnerships, please specify <strong>"Partnership Inquiry"</strong> in your subject line.</p>

<h2>Reach Us via Email</h2>
<p><strong>[Your Professional Email Address]</strong></p>

<p>Please allow 24-48 business hours for our team to route your inquiry to the appropriate analyst or department.</p>
"""

PRIVACY_HTML = """\
<p>At <strong>[Your Blog Name]</strong>, accessible from <a href="[Your Blog URL]">[Your Blog URL]</a>, one of our main priorities is the privacy of our visitors. This Privacy Policy document contains types of information that is collected and recorded by [Your Blog Name] and how we use it.</p>

<h2>Log Files</h2>
<p>[Your Blog Name] follows a standard procedure of using log files. These files log visitors when they visit websites. The information collected by log files includes:</p>
<ul>
  <li>IP addresses</li>
  <li>Browser type</li>
  <li>Internet Service Provider (ISP)</li>
  <li>Date and time stamp</li>
  <li>Referring and exit pages</li>
  <li>Number of clicks</li>
</ul>
<p>These are not linked to any information that is personally identifiable. The purpose is analyzing trends, administering the site, and tracking users' movement on the website.</p>

<h2>Cookies and Web Beacons</h2>
<p>Like any other website, [Your Blog Name] uses "cookies" to store information including visitors' preferences, and the pages on the website that the visitor accessed. The information optimizes the users' experience by customizing our web page content based on browser type.</p>

<h2>Google DoubleClick DART Cookie</h2>
<p>Google is a third-party vendor on our site. It uses DART cookies to serve ads to our site visitors. Visitors may decline the use of DART cookies by visiting the Google ad and content network Privacy Policy at: <a href="https://policies.google.com/technologies/ads" target="_blank" rel="noopener">https://policies.google.com/technologies/ads</a></p>

<h2>Third-Party Privacy Policies</h2>
<p>[Your Blog Name]'s Privacy Policy does not apply to other advertisers or websites. We advise you to consult the respective Privacy Policies of these third-party ad servers for more detailed information.</p>

<h2>Consent</h2>
<p>By using our website, you hereby consent to our Privacy Policy and agree to its Terms and Conditions.</p>
"""

TERMS_HTML = """\
<h2>1. Terms</h2>
<p>By accessing this Website, accessible from <a href="[Your Blog URL]">[Your Blog URL]</a>, you are agreeing to be bound by these Website Terms and Conditions of Use. If you disagree with any of these terms, you are prohibited from accessing this site.</p>

<h2>2. Disclaimer</h2>
<p>All the materials on <strong>[Your Blog Name]</strong>'s Website are provided "as is". [Your Blog Name] makes no warranties, expressed or implied, and therefore negates all other warranties. The content provided is for informational and educational purposes only and should not be construed as certified financial, legal, or professional advisory services.</p>

<h2>3. Limitations</h2>
<p>[Your Blog Name] or its suppliers will not be held accountable for any damages that arise from the use or inability to use the materials on [Your Blog Name]'s Website.</p>

<h2>4. Revisions and Errata</h2>
<p>The materials appearing on [Your Blog Name]'s Website may include technical, typographical, or photographic errors. [Your Blog Name] does not warrant that any of the materials on this Website are accurate, complete, or current.</p>

<h2>5. Site Terms of Use Modifications</h2>
<p>[Your Blog Name] may revise these Terms of Use for its Website at any time without prior notice. By using this Website, you are agreeing to be bound by the current version of these Terms and Conditions of Use.</p>
"""

# Ordered list of (title, template) tuples. Title is used both as the
# Blogger page title AND as the idempotency key against existing pages.
PAGES: list[tuple[str, str]] = [
    ("About Us", ABOUT_HTML),
    ("Contact Us", CONTACT_HTML),
    ("Privacy Policy", PRIVACY_HTML),
    ("Terms of Service", TERMS_HTML),
]


def load_blogger_sites() -> list[dict]:
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"Missing config file: {CONFIG_PATH}")
    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    return cfg.get("blogger_sites") or []


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


def _insert_page_with_retry(
    service,
    blog_id: str,
    body: dict,
    page_title: str,
) -> dict:
    """pages.insert() wrapper with exponential backoff on 429.

    Sleep schedule: 60s, 120s, 240s on consecutive 429s. The doubling
    gives the Blogger quota progressively more time to clear if the API
    has entered a deep cool-down state.
    """
    last_err: HttpError | None = None
    for attempt in range(1, MAX_INSERT_ATTEMPTS + 1):
        try:
            return (
                service.pages()
                .insert(blogId=blog_id, body=body, isDraft=False)
                .execute()
            )
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


def _list_existing_page_titles(service, blog_id: str) -> set[str]:
    """Return the set of page titles that already exist on this blog.

    Used for idempotency — a re-run of the script will skip any page whose
    title is already on the blog instead of creating duplicates.
    """
    titles: set[str] = set()
    page_token: str | None = None
    while True:
        kwargs: dict = {"blogId": blog_id, "maxResults": 100}
        if page_token:
            kwargs["pageToken"] = page_token
        resp = service.pages().list(**kwargs).execute()
        for item in resp.get("items") or []:
            titles.add((item.get("title") or "").strip())
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return titles


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
    site: dict,
    dry_run: bool,
) -> tuple[int, int, int]:
    """Create the 4 standard pages on one blog. Returns (created, skipped, failed)."""
    name_cfg = site.get("name", "<unnamed>")
    blog_id = str(site.get("blog_id") or "")

    # Skip placeholder ids like "[YOUR_BLOGGER_ID_8]" — those are unfinished
    # config entries the daily pipeline already ignores.
    if not blog_id or blog_id.startswith("["):
        logger.warning("[%s] blog_id is a placeholder (%r) — skipping",
                       name_cfg, blog_id)
        return 0, 0, 0

    # 1) Pull the live name + URL straight from Blogger.
    try:
        blog = service.blogs().get(blogId=blog_id).execute()
    except HttpError as e:
        logger.error("[%s] blogs.get failed for blog_id=%s: %s",
                     name_cfg, blog_id, e)
        return 0, 0, len(PAGES)

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
        existing = _list_existing_page_titles(service, blog_id)
    except HttpError as e:
        logger.error("[%s] pages.list failed: %s — will assume zero existing",
                     blog_name, e)
        existing = set()
    if existing:
        logger.info("  Existing pages: %s", sorted(existing))

    created = skipped = failed = 0
    needs_pacing = False  # flip to True after the first real write attempt
    for title, template in PAGES:
        if title in existing:
            logger.info("  [skip] %s — already exists on this blog", title)
            skipped += 1
            continue

        content = _substitute(template, blog_name, blog_url, contact_email)
        body = {
            "kind": "blogger#page",
            "title": title,
            "content": content,
        }

        if dry_run:
            logger.info("  [dry-run] %s — would create (%d chars of HTML)",
                        title, len(content))
            created += 1
            continue

        # Pace consecutive writes to stay under Blogger's per-user write
        # quota. Skipped pages don't bump this flag because they don't hit
        # the write quota.
        if needs_pacing:
            time.sleep(INTER_PAGE_SLEEP_SECONDS)

        try:
            result = _insert_page_with_retry(service, blog_id, body, title)
            page_url = result.get("url") or "(url not returned)"
            logger.info("  [ok]   %s -> %s", title, page_url)
            created += 1
        except HttpError as e:
            logger.error("  [fail] %s — HTTP error: %s", title, e)
            failed += 1
        except Exception as e:
            logger.error("  [fail] %s — unexpected error: %s", title, e)
            failed += 1
        needs_pacing = True

    return created, skipped, failed


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
        help="Run only blogs whose config `name` field CONTAINS this "
             "substring (case-insensitive). Useful for testing one blog first.",
    )
    return p.parse_args()


def main() -> int:
    args = _parse_args()
    sites = load_blogger_sites()
    if not sites:
        logger.error("No blogger_sites found in %s", CONFIG_PATH)
        return 1

    if args.blog_name:
        needle = args.blog_name.lower()
        sites = [s for s in sites
                 if needle in str(s.get("name", "")).lower()]
        logger.info("Filtered by --blog-name=%r -> %d site(s)",
                    args.blog_name, len(sites))
        if not sites:
            return 0

    mode = "DRY-RUN" if args.dry_run else "LIVE (will publish)"
    logger.info("Mode = %s — processing %d blog(s)", mode, len(sites))
    service = _build_service()

    total_created = total_skipped = total_failed = 0
    for idx, site in enumerate(sites):
        c, s, f = _process_blog(service, site, args.dry_run)
        total_created += c
        total_skipped += s
        total_failed += f
        if idx < len(sites) - 1:
            time.sleep(INTER_BLOG_SLEEP_SECONDS)

    logger.info("=================== SUMMARY ===================")
    logger.info("  Mode             : %s", mode)
    logger.info("  Blogs processed  : %d", len(sites))
    logger.info("  Pages created    : %d", total_created)
    logger.info("  Pages skipped    : %d (already existed)", total_skipped)
    logger.info("  Pages failed     : %d", total_failed)

    return 0 if total_failed == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
