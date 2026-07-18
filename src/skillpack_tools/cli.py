from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .configure import configure_repository
from .evals import eval_report, run_structural_evals
from .generate import apply_generated_files
from .models import get_pack
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
                f"{totals['behaviorCases']} behavior cases."
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
            )
            print(f"Archive: {archive.relative_to(root)}")
            print(f"Checksum: {checksum.relative_to(root)}")
            print(f"Release notes: {notes.relative_to(root)}")
            return 0

    except (SkillpackError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    parser.error("Unhandled command.")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
