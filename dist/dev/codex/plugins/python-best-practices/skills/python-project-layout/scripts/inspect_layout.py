#!/usr/bin/env python3
"""Inspect a Python repository layout without importing or modifying project code.

Requires Python 3.11 or newer and only the standard library. Reads local paths and
``pyproject.toml`` and writes findings only to stdout; it never changes files, contacts the
network, imports project code, or executes external commands.
"""

from __future__ import annotations

import argparse
import json
import sys
import tomllib
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

IGNORED_TOP_LEVEL = {
    ".git",
    ".hg",
    ".svn",
    ".tox",
    ".nox",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "build",
    "dist",
}


@dataclass(frozen=True)
class Finding:
    severity: str
    code: str
    message: str


def load_pyproject(path: Path) -> tuple[dict[str, Any] | None, list[Finding]]:
    pyproject = path / "pyproject.toml"
    if not pyproject.is_file():
        return None, [
            Finding(
                "warning",
                "missing-pyproject",
                "No pyproject.toml was found at the repository root.",
            )
        ]
    try:
        with pyproject.open("rb") as handle:
            return tomllib.load(handle), []
    except tomllib.TOMLDecodeError as exc:
        return None, [
            Finding("error", "invalid-pyproject", f"pyproject.toml is invalid TOML: {exc}")
        ]


def package_candidates(folder: Path) -> list[str]:
    if not folder.is_dir():
        return []
    candidates = []
    for child in sorted(folder.iterdir()):
        if not child.is_dir() or child.name.startswith((".", "_")):
            continue
        if (child / "__init__.py").is_file() or any(child.glob("*.py")):
            candidates.append(child.name)
    return candidates


def inspect(root: Path) -> dict[str, Any]:
    findings: list[Finding] = []
    pyproject, pyproject_findings = load_pyproject(root)
    findings.extend(pyproject_findings)

    src_packages = package_candidates(root / "src")
    flat_packages = [
        name
        for name in package_candidates(root)
        if name not in IGNORED_TOP_LEVEL and name not in {"tests", "docs", "examples", "scripts"}
    ]
    test_packages = package_candidates(root / "tests")

    if src_packages and flat_packages:
        findings.append(
            Finding(
                "warning",
                "mixed-layout",
                "Importable packages appear both under src/ and at the repository root; confirm package discovery.",
            )
        )
    elif src_packages:
        findings.append(
            Finding(
                "info", "src-layout", f"Detected src-layout packages: {', '.join(src_packages)}."
            )
        )
    elif flat_packages:
        findings.append(
            Finding(
                "info", "flat-layout", f"Detected root-level packages: {', '.join(flat_packages)}."
            )
        )
    else:
        findings.append(
            Finding(
                "warning",
                "no-package-candidate",
                "No obvious import package was detected under src/ or the root.",
            )
        )

    if test_packages:
        findings.append(
            Finding(
                "warning",
                "tests-importable",
                f"tests/ contains import-package candidates ({', '.join(test_packages)}); confirm this is intentional.",
            )
        )

    if pyproject is not None:
        if "build-system" not in pyproject:
            findings.append(
                Finding(
                    "warning", "missing-build-system", "pyproject.toml has no [build-system] table."
                )
            )
        if "project" not in pyproject:
            findings.append(
                Finding(
                    "warning", "missing-project-metadata", "pyproject.toml has no [project] table."
                )
            )
        else:
            project = pyproject["project"]
            if "requires-python" not in project:
                findings.append(
                    Finding(
                        "warning",
                        "missing-requires-python",
                        "[project] does not declare requires-python.",
                    )
                )
            if "name" not in project:
                findings.append(
                    Finding("error", "missing-project-name", "[project] does not declare name.")
                )

        setuptools_find = (
            pyproject.get("tool", {}).get("setuptools", {}).get("packages", {}).get("find", {})
            if isinstance(pyproject.get("tool", {}), dict)
            else {}
        )
        if src_packages and setuptools_find and "src" not in setuptools_find.get("where", []):
            findings.append(
                Finding(
                    "warning",
                    "setuptools-discovery",
                    "src/ packages were detected but setuptools package discovery does not include where = ['src'].",
                )
            )

    top_level = [
        child.name for child in sorted(root.iterdir()) if child.name not in IGNORED_TOP_LEVEL
    ]
    return {
        "root": str(root),
        "layout": "src"
        if src_packages and not flat_packages
        else "flat"
        if flat_packages and not src_packages
        else "mixed-or-unknown",
        "srcPackages": src_packages,
        "flatPackages": flat_packages,
        "topLevelEntries": top_level,
        "findings": [asdict(item) for item in findings],
        "limitations": [
            "Package detection is heuristic and does not execute the build backend.",
            "Namespace packages and custom discovery rules require manual review.",
            "A clean build and install test are still required.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", nargs="?", default=".", help="Repository root to inspect.")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of text.")
    args = parser.parse_args()

    root = Path(args.path).expanduser().resolve()
    if not root.is_dir():
        parser.error(f"not a directory: {root}")
    report = inspect(root)
    if args.json:
        json.dump(report, sys.stdout, indent=2)
        print()
    else:
        print(f"root: {report['root']}")
        print(f"layout: {report['layout']}")
        for finding in report["findings"]:
            print(f"{finding['severity']}: {finding['code']}: {finding['message']}")
        print("limitations:")
        for limitation in report["limitations"]:
            print(f"  - {limitation}")
    return 1 if any(item["severity"] == "error" for item in report["findings"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
