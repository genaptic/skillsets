#!/usr/bin/env python3
"""Inventory Python tests statically without importing project or test modules.

Requires Python 3.11 or newer and only the standard library. Reads local test source and
writes the inventory only to stdout; it never modifies files, contacts the network, imports
tests, or executes project code or external commands.
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


def decorator_name(node: ast.expr) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        left = decorator_name(node.value)
        return f"{left}.{node.attr}" if left else node.attr
    if isinstance(node, ast.Call):
        return decorator_name(node.func)
    return ""


def inspect_file(path: Path) -> dict[str, Any]:
    result: dict[str, Any] = {
        "path": str(path),
        "tests": 0,
        "testClasses": 0,
        "fixtures": [],
        "parametrized": 0,
        "marks": [],
        "asyncTests": 0,
        "parseError": None,
    }
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, UnicodeError, SyntaxError) as exc:
        result["parseError"] = str(exc)
        return result

    marks: Counter[str] = Counter()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            decorators = [decorator_name(item) for item in node.decorator_list]
            if node.name.startswith("test"):
                result["tests"] += 1
                if isinstance(node, ast.AsyncFunctionDef):
                    result["asyncTests"] += 1
            if any(name.endswith(".fixture") or name == "fixture" for name in decorators):
                result["fixtures"].append(node.name)
            if any("parametrize" in name for name in decorators):
                result["parametrized"] += 1
            for name in decorators:
                if ".mark." in name:
                    marks[name.split(".mark.", 1)[1].split(".", 1)[0]] += 1
        elif isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
            result["testClasses"] += 1
    result["marks"] = [{"name": name, "count": count} for name, count in sorted(marks.items())]
    return result


def discover(root: Path) -> list[Path]:
    candidates = []
    for pattern in ("test_*.py", "*_test.py"):
        candidates.extend(root.rglob(pattern))
    return sorted({path.resolve() for path in candidates if "__pycache__" not in path.parts})


def build_report(root: Path) -> dict[str, Any]:
    files = [inspect_file(path) for path in discover(root)]
    marks: Counter[str] = Counter()
    for item in files:
        for mark in item["marks"]:
            marks[mark["name"]] += mark["count"]
    totals = {
        "files": len(files),
        "tests": sum(item["tests"] for item in files),
        "testClasses": sum(item["testClasses"] for item in files),
        "fixtures": sum(len(item["fixtures"]) for item in files),
        "parametrized": sum(item["parametrized"] for item in files),
        "asyncTests": sum(item["asyncTests"] for item in files),
        "parseErrors": sum(item["parseError"] is not None for item in files),
    }
    findings = []
    if not files:
        findings.append("No files matching test_*.py or *_test.py were found.")
    if files and totals["parametrized"] == 0:
        findings.append(
            "No parametrized tests were detected; confirm whether boundary tables are represented."
        )
    if totals["parseErrors"]:
        findings.append("Some test files could not be parsed; inspect parseError entries.")
    if totals["fixtures"] > max(totals["files"] * 3, 15):
        findings.append(
            "Fixture count is high relative to files; review scope, ownership, and hidden coupling."
        )
    return {
        "root": str(root),
        "totals": totals,
        "marks": [{"name": name, "count": count} for name, count in sorted(marks.items())],
        "files": files,
        "findings": findings,
        "limitations": [
            "Static counts do not measure test quality, isolation, runtime, or coverage.",
            "Dynamic test generation and non-pytest frameworks may not be represented.",
            "No project code or tests were imported or executed.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", nargs="?", default=".", help="Repository or tests directory.")
    parser.add_argument("--json", action="store_true", help="Emit JSON.")
    args = parser.parse_args()
    root = Path(args.path).expanduser().resolve()
    if not root.is_dir():
        parser.error(f"not a directory: {root}")
    report = build_report(root)
    if args.json:
        json.dump(report, sys.stdout, indent=2)
        print()
    else:
        print(f"root: {report['root']}")
        for key, value in report["totals"].items():
            print(f"{key}: {value}")
        if report["marks"]:
            print("marks:")
            for item in report["marks"]:
                print(f"  {item['name']}: {item['count']}")
        for finding in report["findings"]:
            print(f"finding: {finding}")
        print("limitations:")
        for limitation in report["limitations"]:
            print(f"  - {limitation}")
    return 1 if report["totals"]["parseErrors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
