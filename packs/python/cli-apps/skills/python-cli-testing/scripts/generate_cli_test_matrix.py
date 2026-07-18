#!/usr/bin/env python3
"""Generate a reviewable CLI test matrix from a declarative JSON surface.

Requires Python 3.11 or newer and only the standard library. Reads one local JSON file and
writes to stdout unless ``--output`` is explicit; existing output is refused unless
``--force`` is also supplied. It never contacts the network or executes external commands.
"""

from __future__ import annotations

import argparse
import itertools
import json
import sys
from pathlib import Path
from typing import Any


def validate(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["Input must be a JSON object."]
    if data.get("schemaVersion") != 1:
        errors.append("schemaVersion must be 1.")
    dimensions = data.get("dimensions")
    if not isinstance(dimensions, dict) or not dimensions:
        errors.append("dimensions must be a non-empty object.")
    else:
        for name, values in dimensions.items():
            if not isinstance(name, str) or not name:
                errors.append("dimension names must be non-empty strings.")
            if (
                not isinstance(values, list)
                or not values
                or not all(isinstance(item, str) for item in values)
            ):
                errors.append(f"dimension {name!r} must be a non-empty string array.")
    scenarios = data.get("requiredScenarios")
    if not isinstance(scenarios, list) or not scenarios:
        errors.append("requiredScenarios must be a non-empty array.")
    else:
        ids = set()
        for index, scenario in enumerate(scenarios):
            path = f"requiredScenarios[{index}]"
            if not isinstance(scenario, dict):
                errors.append(f"{path} must be an object.")
                continue
            identifier = scenario.get("id")
            if not isinstance(identifier, str) or not identifier:
                errors.append(f"{path}.id must be a non-empty string.")
            elif identifier in ids:
                errors.append(f"{path}.id is duplicated.")
            else:
                ids.add(identifier)
            if (
                not isinstance(scenario.get("purpose"), str)
                or not scenario.get("purpose", "").strip()
            ):
                errors.append(f"{path}.purpose must be a non-empty string.")
            expected = scenario.get("assert")
            if (
                not isinstance(expected, list)
                or not expected
                or not all(isinstance(item, str) for item in expected)
            ):
                errors.append(f"{path}.assert must be a non-empty string array.")
    return errors


def build_cases(data: dict[str, Any], max_combinations: int) -> list[dict[str, Any]]:
    dimensions: dict[str, list[str]] = data["dimensions"]
    names = list(dimensions)
    products = itertools.product(*(dimensions[name] for name in names))
    combinations = [
        {
            "id": f"matrix-{index + 1}",
            "kind": "dimension-combination",
            "dimensions": dict(zip(names, values)),
        }
        for index, values in enumerate(itertools.islice(products, max_combinations))
    ]
    required = [
        {
            "id": item["id"],
            "kind": "required-scenario",
            "purpose": item["purpose"],
            "assert": item["assert"],
        }
        for item in data["requiredScenarios"]
    ]
    return required + combinations


def markdown(data: dict[str, Any], cases: list[dict[str, Any]], max_combinations: int) -> str:
    lines = [
        f"# CLI test matrix: {data.get('program', 'program')}",
        "",
        "## Required scenarios",
        "",
        "| ID | Purpose | Assertions |",
        "|---|---|---|",
    ]
    for case in cases:
        if case["kind"] == "required-scenario":
            lines.append(f"| `{case['id']}` | {case['purpose']} | {'; '.join(case['assert'])} |")
    dimension_names = list(data["dimensions"])
    lines.extend(
        [
            "",
            f"## Dimension combinations (capped at {max_combinations})",
            "",
            "| ID | " + " | ".join(dimension_names) + " |",
            "|---|" + "|".join("---" for _ in dimension_names) + "|",
        ]
    )
    for case in cases:
        if case["kind"] == "dimension-combination":
            lines.append(
                f"| `{case['id']}` | "
                + " | ".join(case["dimensions"][name] for name in dimension_names)
                + " |"
            )
    lines.extend(
        [
            "",
            "The Cartesian matrix is a planning aid, not a requirement to test every combination.",
            "Select representative combinations from each equivalence class and add targeted",
            "cases for high-risk interactions.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("surface", type=Path, help="JSON test-surface file.")
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    parser.add_argument("--max-combinations", type=int, default=24)
    parser.add_argument("--output", type=Path, help="Write to an explicit path instead of stdout.")
    parser.add_argument("--force", action="store_true", help="Allow overwriting --output.")
    args = parser.parse_args()
    if not 1 <= args.max_combinations <= 500:
        parser.error("--max-combinations must be from 1 through 500.")
    try:
        data = json.loads(args.surface.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    errors = validate(data)
    if errors:
        for error in errors:
            print(f"error: {error}", file=sys.stderr)
        return 2
    cases = build_cases(data, args.max_combinations)
    content = (
        json.dumps({"schemaVersion": 1, "program": data.get("program"), "cases": cases}, indent=2)
        + "\n"
        if args.format == "json"
        else markdown(data, cases, args.max_combinations)
    )
    if args.output:
        output = args.output.expanduser().resolve()
        if output.exists() and not args.force:
            parser.error(f"output exists; pass --force to overwrite: {output}")
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(content, encoding="utf-8", newline="\n")
        print(output)
    else:
        sys.stdout.write(content)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
