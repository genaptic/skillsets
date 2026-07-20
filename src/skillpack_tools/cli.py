from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .checks import check as run_check
from .checks import check_pack as run_check_pack
from .checks import lint as run_lint
from .checks import lock as run_lock
from .checks import test as run_test
from .configure import configure_repository
from .evals import eval_report, run_structural_evals
from .generate import apply_generated_files
from .lifecycle_commands import apply_lifecycle_plan, build_lifecycle_plan, plan_text
from .models import get_pack
from .publication import load_publication_record, prepare_publication_update
from .release import build_release
from .util import SkillpackError, atomic_write, find_repository_root
from .validate import (
    raise_for_result,
    validate_compatibility_report,
    validate_repository,
)


def _root(value: str | None) -> Path:
    return find_repository_root(Path(value) if value else None)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="skillpacks",
        description="Generate, validate, evaluate, configure, and release Genaptic Skillsets.",
    )
    parser.add_argument("--root", help="Repository root or a path inside it.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    generate = subparsers.add_parser("generate", help="Regenerate all derived artifacts.")
    generate.add_argument("--check", action="store_true", help="Fail instead of writing changes.")

    validate = subparsers.add_parser("validate", help="Validate the repository.")
    validate.add_argument("--check-generated", action="store_true")
    validate.add_argument("--strict-placeholders", action="store_true")
    validate.add_argument("--json", dest="json_path")

    evals = subparsers.add_parser("eval", help="Validate structural skill eval suites.")
    evals.add_argument("--skill")
    evals.add_argument("--json", dest="json_path")

    compatibility = subparsers.add_parser(
        "compatibility", help="Validate a native-client compatibility report."
    )
    compatibility.add_argument("report")
    compatibility.add_argument("--pack")
    compatibility.add_argument("--source-sha")

    configure = subparsers.add_parser("configure", help="Set repository identity.")
    configure.add_argument("--project-name")
    configure.add_argument("--project-description")
    configure.add_argument("--owner")
    configure.add_argument("--repository")
    configure.add_argument(
        "--default-branch",
        help=(
            "Portable Git branch name (for example main or release/v2; no leading dot/dash, "
            "double dots/slashes, .lock component, or trailing dot/slash)."
        ),
    )
    configure.add_argument("--publisher-name")
    configure.add_argument("--copyright-owner")
    configure.add_argument("--maintainer-name")
    configure.add_argument("--maintainer-github")
    configure.add_argument("--maintainer-github-id", type=int)
    configure.add_argument("--trusted-ssh-fingerprint")
    configure.add_argument("--security-channel", choices=["github-private-vulnerability-reporting"])
    configure.add_argument("--security-email")
    configure.add_argument("--marketplace-name")
    configure.add_argument("--marketplace-display-name")
    configure.add_argument("--marketplace-description")
    configure.add_argument("--license", dest="license_id")
    configure.add_argument("--initial-year", type=int)

    release = subparsers.add_parser("release", help="Build a deterministic local pack release.")
    release.add_argument("pack_id")
    release.add_argument(
        "--draft",
        action="store_true",
        help="Build a clearly marked rehearsal without Git/tag/evidence release gates.",
    )
    release.add_argument(
        "--policy-root",
        help="Protected-main policy checkout; required for a publishable release.",
    )

    prepare_release = subparsers.add_parser(
        "prepare-release", help="Preview or apply an atomic stable release transition."
    )
    prepare_release.add_argument("pack_id")
    prepare_release.add_argument("--release-date", required=True)
    prepare_release.add_argument("--version")
    prepare_release.add_argument("--apply", action="store_true")
    prepare_release.add_argument("--plan-digest")

    begin_development = subparsers.add_parser(
        "begin-development", help="Start a higher candidate without losing the public release."
    )
    begin_development.add_argument("pack_id")
    begin_development.add_argument("--next-version", required=True)
    begin_development.add_argument("--apply", action="store_true")
    begin_development.add_argument("--plan-digest")

    publication = subparsers.add_parser(
        "prepare-publication-update",
        help="Preview or apply canonical metadata from an immutable release record.",
    )
    publication.add_argument("record")
    publication.add_argument("--apply", action="store_true")
    publication.add_argument("--plan-digest")

    subparsers.add_parser("check", help="Run the complete non-mutating repository gate.")
    check_pack = subparsers.add_parser(
        "check-pack", help="Run focused checks while retaining global graph validation."
    )
    check_pack.add_argument("pack_id")
    subparsers.add_parser("lint", help="Run repository linters.")
    subparsers.add_parser("test", help="Run the complete Python test suite.")
    lock = subparsers.add_parser("lock", help="Regenerate or verify the hash-locked dependencies.")
    lock.add_argument("--check", action="store_true")
    release.add_argument(
        "--report",
        action="append",
        default=[],
        help="External exact-SHA compatibility report (repeat for each native client).",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    root = _root(args.root)

    try:
        if args.command == "generate":
            changed = apply_generated_files(root, check=args.check)
            if args.check:
                print("Generated artifacts are current.")
            elif changed:
                print("Generated:")
                for path in changed:
                    print(f"  {path}")
            else:
                print("Generated artifacts were already current.")
            return 0

        if args.command == "validate":
            result = validate_repository(
                root,
                check_generated=args.check_generated,
                strict_placeholders=args.strict_placeholders,
            )
            report = {
                "ok": result.ok,
                "errors": result.errors,
                "warnings": result.warnings,
            }
            if args.json_path:
                atomic_write(root / args.json_path, json.dumps(report, indent=2) + "\n")
            for warning in result.warnings:
                print(f"warning: {warning}", file=sys.stderr)
            raise_for_result(result)
            print("Repository validation passed.")
            return 0

        if args.command == "eval":
            summaries = run_structural_evals(root, skill_filter=args.skill)
            report = eval_report(summaries)
            if args.json_path:
                atomic_write(root / args.json_path, json.dumps(report, indent=2) + "\n")
            totals = report["totals"]
            print(
                f"Eval specifications passed: {totals['skills']} skills, "
                f"{totals['routingCases']} routing cases, "
                f"{totals['behaviorCases']} behavior cases, "
                f"{totals['routingBoundaries']} routing boundaries, and "
                f"{totals['boundaryCases']} boundary cases."
            )
            return 0

        if args.command == "compatibility":
            try:
                pack = get_pack(root, args.pack) if args.pack else None
            except KeyError as exc:
                raise SkillpackError(str(exc)) from exc
            errors, _ = validate_compatibility_report(
                root,
                root / args.report,
                pack=pack,
                source_sha=args.source_sha,
            )
            if errors:
                raise SkillpackError(
                    "Compatibility report validation failed:\n"
                    + "\n".join(f"  - {error}" for error in errors)
                )
            print("Compatibility report validation passed.")
            return 0

        if args.command == "configure":
            changed = configure_repository(
                root,
                owner=args.owner,
                repository=args.repository,
                project_name=args.project_name,
                project_description=args.project_description,
                default_branch=args.default_branch,
                publisher_name=args.publisher_name,
                copyright_owner=args.copyright_owner,
                maintainer_name=args.maintainer_name,
                maintainer_github=args.maintainer_github,
                maintainer_github_id=args.maintainer_github_id,
                trusted_ssh_fingerprint=args.trusted_ssh_fingerprint,
                security_channel=args.security_channel,
                security_email=args.security_email,
                marketplace_name=args.marketplace_name,
                marketplace_display_name=args.marketplace_display_name,
                marketplace_description=args.marketplace_description,
                license_id=args.license_id,
                initial_year=args.initial_year,
            )
            if changed:
                print("Repository identity updated.")
                print("Updated or regenerated:")
                for path in changed:
                    print(f"  {path}")
            else:
                print("Repository identity is already current.")
            return 0

        if args.command == "release":
            archive, checksum, notes = build_release(
                root,
                args.pack_id,
                draft=args.draft,
                reports=[Path(path).resolve() for path in args.report],
                policy_root=Path(args.policy_root).resolve() if args.policy_root else None,
            )
            print(f"Archive: {archive.relative_to(root)}")
            print(f"Checksum: {checksum.relative_to(root)}")
            print(f"Release notes: {notes.relative_to(root)}")
            return 0

        if args.command in {"prepare-release", "begin-development"}:
            operation = args.command
            release_date = args.release_date if operation == "prepare-release" else None
            version = args.version if operation == "prepare-release" else args.next_version
            if args.apply:
                plan = apply_lifecycle_plan(
                    root,
                    args.pack_id,
                    operation=operation,
                    plan_digest=args.plan_digest,
                    release_date=release_date,
                    version=version,
                )
            else:
                if args.plan_digest:
                    raise SkillpackError("--plan-digest is only valid with --apply.")
                plan = build_lifecycle_plan(
                    root,
                    args.pack_id,
                    operation=operation,
                    release_date=release_date,
                    version=version,
                )
            print(plan_text(plan), end="")
            if not args.apply:
                print("No files changed. Re-run with --apply --plan-digest DIGEST after review.")
            return 0

        if args.command == "prepare-publication-update":
            record = load_publication_record(root, Path(args.record))
            plan = prepare_publication_update(
                root,
                record,
                apply=args.apply,
                plan_digest=args.plan_digest,
            )
            print(json.dumps(plan, indent=2, ensure_ascii=False))
            if not args.apply:
                print("No files changed. Re-run with --apply --plan-digest DIGEST after review.")
            return 0

        if args.command == "check":
            run_check(root)
            print("Complete repository check passed.")
            return 0

        if args.command == "check-pack":
            run_check_pack(root, args.pack_id)
            return 0

        if args.command == "lint":
            run_lint(root)
            return 0

        if args.command == "test":
            run_test(root)
            return 0

        if args.command == "lock":
            run_lock(root, check=args.check)
            return 0

    except (SkillpackError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    parser.error("Unhandled command.")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
