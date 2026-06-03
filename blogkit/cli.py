"""blogkit command-line interface.

    python -m blogkit list                         # show all blog profiles
    python -m blogkit run --blog zero_trust_enterprise
    python -m blogkit run --group 2 --publish-method email
    python -m blogkit run --all
    python -m blogkit selftest-image [--blog <slug>]   # test HF+GitHub path only

Heavy deps (google-genai) are imported lazily so `list` / `selftest-image`
work without the full generation stack installed.
"""

from __future__ import annotations

import argparse
import logging
import os
import re
import sys
import time

from blogkit.profiles.registry import all_profiles, by_group, get_profile, runnable

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("blogkit")


def _disabled_slugs() -> set[str]:
    """Runtime disable list from BLOGKIT_DISABLE (comma-separated slugs)."""
    return {s.strip() for s in os.environ.get("BLOGKIT_DISABLE", "").split(",") if s.strip()}


def _select(args: argparse.Namespace):
    """Resolve the profiles a run targets from --blog/--group/--all.

    --blog runs that blog explicitly (even if disabled). --group/--all skip
    disabled + BLOGKIT_DISABLE blogs unless --include-disabled is set.
    """
    if getattr(args, "blog", None):
        return [get_profile(args.blog)]
    profs = by_group(args.group) if getattr(args, "group", None) is not None else all_profiles()
    if getattr(args, "group", None) is not None and not profs:
        logger.warning("No blogs in run_group=%d", args.group)
    if getattr(args, "include_disabled", False):
        return profs
    selected = runnable(profs, _disabled_slugs())
    skipped = len(profs) - len(selected)
    if skipped:
        logger.info("Skipping %d disabled blog(s) (enabled=False or BLOGKIT_DISABLE)", skipped)
    return selected


def cmd_list(_args: argparse.Namespace) -> int:
    disabled = _disabled_slugs()
    for p in all_profiles():
        if not p.enabled:
            status = "off "
        elif p.slug in disabled:
            status = "off*"   # runtime-disabled via BLOGKIT_DISABLE
        else:
            status = "ON  "
        print(f"[{status}] g{p.run_group}  {p.slug:32}  {p.persona}")
    print("\n(off = enabled:false in profile; off* = BLOGKIT_DISABLE)")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    from blogkit.core.dedup import GitHubLedgerStore
    from blogkit.core.imager import warm_up_hf_model
    from blogkit.core.pipeline import INTER_SITE_SLEEP_SECONDS, run_profile

    profiles = _select(args)
    if not profiles:
        return 0
    logger.info("Publish method: %s | %d blog(s)", args.publish_method, len(profiles))

    dry_run = getattr(args, "dry_run", False)

    # Cross-blog de-dup ledger (best-effort; empty if no ASSETS_REPO_PAT).
    store = GitHubLedgerStore()
    ledger = store.load()

    # One-shot warm-up if any selected blog wants an image (not in dry-run).
    hf_token = os.environ.get("HF_API_TOKEN")
    if not dry_run and hf_token and any(p.featured_image for p in profiles):
        logger.info("Warming up Hugging Face FLUX.1-schnell model...")
        warm_up_hf_model(hf_token)

    results = []
    for idx, profile in enumerate(profiles):
        ok, info = run_profile(
            profile, publish_method=args.publish_method, ledger=ledger, dry_run=dry_run,
        )
        results.append((profile.slug, ok, info))
        if idx < len(profiles) - 1:
            logger.info("Sleeping %ds before next blog", INTER_SITE_SLEEP_SECONDS)
            time.sleep(INTER_SITE_SLEEP_SECONDS)

    if not dry_run:
        store.save(ledger)   # persist what we used this run

    logger.info("=================== SUMMARY ===================")
    for slug, ok, info in results:
        logger.info("  [%s] %s -- %s", "OK  " if ok else "FAIL", slug, info)

    # Run digest to webhook (best-effort; no-op without RUN_WEBHOOK_URL).
    if not dry_run:
        from blogkit.core.notify import format_digest, send_digest
        if send_digest(format_digest(results)):
            logger.info("Run digest sent to webhook")

    return 0 if all(ok for _, ok, _ in results) else 2


def cmd_doctor(args: argparse.Namespace) -> int:
    from blogkit.core.health import all_ok, check_environment, format_checks

    checks = check_environment(
        publish_method=args.publish_method, need_image=not args.no_image
    )
    print(f"blogkit doctor — publish={args.publish_method}, image={not args.no_image}")
    print(format_checks(checks))
    ok = all_ok(checks)
    print("OK — ready to run." if ok else "NOT READY — fix the FAIL items above.")
    return 0 if ok else 1


def cmd_selftest_image(args: argparse.Namespace) -> int:
    from blogkit.core.imager import build_featured_image_html, warm_up_hf_model

    hf_token = os.environ.get("HF_API_TOKEN")
    missing = [k for k, v in {
        "HF_API_TOKEN": hf_token,
        "ASSETS_REPO_PAT": os.environ.get("ASSETS_REPO_PAT"),
    }.items() if not v]
    if missing:
        logger.error("selftest-image needs env vars: %s", ", ".join(missing))
        return 1

    if args.blog:
        profile = get_profile(args.blog)
        styles, title = profile.style_pool(), f"Self-Test: {profile.name}"
    else:
        styles, title = None, "Self-Test: Enterprise AI Infrastructure in 2026"

    logger.info("Self-test: warming up, then generating one image for %r", title)
    warm_up_hf_model(hf_token)
    html = build_featured_image_html(title, hf_token, styles=styles)
    if not html:
        logger.error("Self-test FAILED — no image produced (see warnings).")
        return 2
    m = re.search(r'src="([^"]+)"', html)
    logger.info("Self-test OK")
    logger.info("  CDN URL : %s", m.group(1) if m else "<not found>")
    logger.info("  HTML    : %s", html)
    return 0


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="blogkit", description="Multi-blog content pipeline")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="List all blog profiles")

    run = sub.add_parser("run", help="Generate + publish posts")
    sel = run.add_mutually_exclusive_group()
    sel.add_argument("--blog", help="Run a single blog by slug")
    sel.add_argument("--group", type=int, help="Run all blogs in a run_group")
    sel.add_argument("--all", action="store_true", help="Run every blog (default)")
    run.add_argument("--publish-method", choices=["api", "email"], default="api",
                     help="api = Blogger v3 REST (default); email = Mail2Blogger SMTP")
    run.add_argument("--dry-run", action="store_true",
                     help="Generate + assemble but do not publish; ledger untouched, "
                          "featured image skipped. For safe testing.")
    run.add_argument("--include-disabled", action="store_true",
                     help="Also run blogs marked enabled=false / in BLOGKIT_DISABLE.")

    st = sub.add_parser("selftest-image", help="Test the HF+GitHub image path only")
    st.add_argument("--blog", help="Use this blog's style pool (else the default sample)")

    doc = sub.add_parser("doctor", help="Preflight: validate secrets/config before a run")
    doc.add_argument("--publish-method", choices=["api", "email"], default="api")
    doc.add_argument("--no-image", action="store_true",
                     help="Skip the featured-image (HF/PAT) checks")

    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    if args.command == "list":
        return cmd_list(args)
    if args.command == "run":
        return cmd_run(args)
    if args.command == "selftest-image":
        return cmd_selftest_image(args)
    if args.command == "doctor":
        return cmd_doctor(args)
    return 1


if __name__ == "__main__":
    sys.exit(main())
