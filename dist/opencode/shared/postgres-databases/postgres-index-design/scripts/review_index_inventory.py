#!/usr/bin/env python3
"""Review an exported PostgreSQL index inventory for conservative warning signals.

Requires Python 3.11 or newer and only the standard library. Reads JSON from one local file
or stdin and writes findings only to stdout; it never changes files, connects to PostgreSQL,
contacts the network, or executes SQL or external commands.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Finding:
    severity: str
    code: str
    index: str
    message: str


REQUIRED_FIELDS = {
    "schema",
    "table",
    "name",
    "method",
    "keys",
    "include",
    "predicate",
    "unique",
    "primary",
    "constraintBacked",
    "valid",
    "ready",
    "sizeBytes",
    "idxScan",
}


def validate(data: Any) -> tuple[list[dict[str, Any]], list[str]]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return [], ["inventory must be an object"]
    if data.get("schemaVersion") != 1:
        errors.append("schemaVersion must be 1")
    indexes = data.get("indexes")
    if not isinstance(indexes, list):
        return [], errors + ["indexes must be an array"]
    names: set[tuple[str, str, str]] = set()
    valid_items: list[dict[str, Any]] = []
    for position, item in enumerate(indexes):
        label = f"indexes[{position}]"
        if not isinstance(item, dict):
            errors.append(f"{label} must be an object")
            continue
        missing = REQUIRED_FIELDS - item.keys()
        if missing:
            errors.append(f"{label} missing fields: {', '.join(sorted(missing))}")
            continue
        if not isinstance(item["keys"], list) or not all(
            isinstance(value, str) and value for value in item["keys"]
        ):
            errors.append(f"{label}.keys must be a non-empty string array")
        if not item["keys"]:
            errors.append(f"{label}.keys must not be empty")
        if not isinstance(item["include"], list) or not all(
            isinstance(value, str) and value for value in item["include"]
        ):
            errors.append(f"{label}.include must be a string array")
        for field in ("unique", "primary", "constraintBacked", "valid", "ready"):
            if not isinstance(item[field], bool):
                errors.append(f"{label}.{field} must be boolean")
        for field in ("sizeBytes", "idxScan"):
            if not isinstance(item[field], int) or isinstance(item[field], bool) or item[field] < 0:
                errors.append(f"{label}.{field} must be a non-negative integer")
        identity = (str(item["schema"]), str(item["table"]), str(item["name"]))
        if identity in names:
            errors.append(f"{label} duplicates {'.'.join(identity)}")
        names.add(identity)
        valid_items.append(item)
    return valid_items, errors


def full_name(item: dict[str, Any]) -> str:
    return f"{item['schema']}.{item['table']}.{item['name']}"


def same_semantics(left: dict[str, Any], right: dict[str, Any]) -> bool:
    return (
        left["method"] == right["method"]
        and left["predicate"] == right["predicate"]
        and left["keys"] == right["keys"]
        and left["include"] == right["include"]
        and left["unique"] == right["unique"]
    )


def is_key_prefix(shorter: dict[str, Any], longer: dict[str, Any]) -> bool:
    keys = shorter["keys"]
    return (
        shorter["method"] == longer["method"]
        and shorter["predicate"] == longer["predicate"]
        and len(keys) < len(longer["keys"])
        and longer["keys"][: len(keys)] == keys
    )


def analyze(indexes: list[dict[str, Any]]) -> list[Finding]:
    findings: list[Finding] = []
    for item in indexes:
        name = full_name(item)
        if not item["valid"] or not item["ready"]:
            findings.append(
                Finding(
                    "high",
                    "invalid-or-not-ready",
                    name,
                    "Index is not both valid and ready; inspect build history, dependencies, and safe cleanup.",
                )
            )
        if item["idxScan"] == 0:
            findings.append(
                Finding(
                    "info",
                    "zero-scan-counter",
                    name,
                    "Usage counter is zero in the supplied window; this is not sufficient evidence to drop the index.",
                )
            )
        if item["sizeBytes"] == 0:
            findings.append(
                Finding(
                    "info",
                    "zero-recorded-size",
                    name,
                    "Recorded size is zero; confirm collection permissions and object state.",
                )
            )

    for position, left in enumerate(indexes):
        for right in indexes[position + 1 :]:
            if (left["schema"], left["table"]) != (right["schema"], right["table"]):
                continue
            if same_semantics(left, right):
                findings.append(
                    Finding(
                        "medium",
                        "duplicate-definition",
                        full_name(left),
                        f"Definition matches {full_name(right)}; verify dependencies and workload before consolidation.",
                    )
                )
            elif is_key_prefix(left, right):
                findings.append(
                    Finding(
                        "info",
                        "prefix-overlap",
                        full_name(left),
                        f"Key list is a prefix of {full_name(right)}; compare size, payload, uniqueness, and plans before any removal.",
                    )
                )
            elif is_key_prefix(right, left):
                findings.append(
                    Finding(
                        "info",
                        "prefix-overlap",
                        full_name(right),
                        f"Key list is a prefix of {full_name(left)}; compare size, payload, uniqueness, and plans before any removal.",
                    )
                )
    return sorted(findings, key=lambda item: (item.severity, item.index, item.code))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "inventory", type=Path, help="Inventory JSON file; use '-' for standard input."
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON.")
    parser.add_argument(
        "--fail-on-high", action="store_true", help="Return status 1 when a high finding exists."
    )
    args = parser.parse_args()

    try:
        text = (
            sys.stdin.read()
            if str(args.inventory) == "-"
            else args.inventory.read_text(encoding="utf-8")
        )
        data = json.loads(text)
    except (OSError, json.JSONDecodeError) as exc:
        parser.error(str(exc))

    indexes, errors = validate(data)
    if errors:
        for error in errors:
            print(f"error: {error}", file=sys.stderr)
        return 2

    findings = analyze(indexes)
    report = {
        "statisticsResetAt": data.get("statisticsResetAt"),
        "observationEndsAt": data.get("observationEndsAt"),
        "indexCount": len(indexes),
        "findings": [asdict(item) for item in findings],
        "caveat": "Potential overlap is structural only; plans, constraints, workload coverage, and reset history are required.",
    }
    if args.json:
        json.dump(report, sys.stdout, indent=2)
        print()
    else:
        print(f"indexes: {len(indexes)}")
        print(f"window: {report['statisticsResetAt']} -> {report['observationEndsAt']}")
        for item in findings:
            print(f"{item.severity.upper()} {item.code} {item.index}: {item.message}")
        print(f"caveat: {report['caveat']}")
    return 1 if args.fail_on_high and any(item.severity == "high" for item in findings) else 0


if __name__ == "__main__":
    raise SystemExit(main())
