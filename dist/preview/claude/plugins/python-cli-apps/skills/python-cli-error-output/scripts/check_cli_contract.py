#!/usr/bin/env python3
"""Validate, or explicitly execute, a JSON CLI stdout/stderr/exit contract.

Requires Python 3.11 or newer and only the standard library. Reads one local JSON contract
and writes results only to stdout. It makes no network requests and modifies no files itself.
By default it executes nothing; ``--confirm-execute`` runs the declared argv without a shell,
and that external program may have its own filesystem, network, or external effects.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


def validate_stream(value: Any, path: str, errors: list[str]) -> None:
    if not isinstance(value, dict):
        errors.append(f"{path} must be an object.")
        return
    mode = value.get("mode")
    if mode not in {"any", "empty", "exact", "regex"}:
        errors.append(f"{path}.mode must be any, empty, exact, or regex.")
    expected = value.get("value")
    if mode in {"exact", "regex"} and not isinstance(expected, str):
        errors.append(f"{path}.value must be a string for {mode} mode.")
    if mode == "regex" and isinstance(expected, str):
        try:
            re.compile(expected)
        except re.error as exc:
            errors.append(f"{path}.value is not a valid regular expression: {exc}")


def validate_contract(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["Contract must be a JSON object."]
    if data.get("schemaVersion") != 1:
        errors.append("schemaVersion must be 1.")
    scenarios = data.get("scenarios")
    if not isinstance(scenarios, list) or not scenarios:
        errors.append("scenarios must be a non-empty array.")
        return errors
    ids: set[str] = set()
    for index, scenario in enumerate(scenarios):
        path = f"scenarios[{index}]"
        if not isinstance(scenario, dict):
            errors.append(f"{path} must be an object.")
            continue
        identifier = scenario.get("id")
        if not isinstance(identifier, str) or not identifier:
            errors.append(f"{path}.id must be a non-empty string.")
        elif identifier in ids:
            errors.append(f"{path}.id is duplicated: {identifier}.")
        else:
            ids.add(identifier)
        argv = scenario.get("argv")
        if (
            not isinstance(argv, list)
            or not argv
            or not all(isinstance(item, str) and item for item in argv)
        ):
            errors.append(f"{path}.argv must be a non-empty string array.")
        expected_exit = scenario.get("expectedExit")
        if (
            not isinstance(expected_exit, int)
            or isinstance(expected_exit, bool)
            or not 0 <= expected_exit <= 255
        ):
            errors.append(f"{path}.expectedExit must be an integer from 0 through 255.")
        validate_stream(scenario.get("stdout", {"mode": "any"}), f"{path}.stdout", errors)
        validate_stream(scenario.get("stderr", {"mode": "any"}), f"{path}.stderr", errors)
        environment = scenario.get("environment", {})
        if not isinstance(environment, dict) or not all(
            isinstance(key, str) and isinstance(value, str) for key, value in environment.items()
        ):
            errors.append(f"{path}.environment must map strings to strings.")
        timeout = scenario.get("timeoutSeconds", 10)
        if (
            not isinstance(timeout, (int, float))
            or isinstance(timeout, bool)
            or not 0.1 <= timeout <= 60
        ):
            errors.append(f"{path}.timeoutSeconds must be from 0.1 through 60.")
    return errors


def stream_matches(spec: dict[str, Any], actual: str) -> tuple[bool, str]:
    mode = spec.get("mode", "any")
    if mode == "any":
        return True, ""
    if mode == "empty":
        return actual == "", "expected empty stream"
    expected = spec.get("value", "")
    if mode == "exact":
        return actual == expected, f"expected exact value {expected!r}"
    if mode == "regex":
        return re.search(expected, actual, re.MULTILINE) is not None, f"expected regex {expected!r}"
    return False, f"unknown mode {mode!r}"


def execute_scenario(scenario: dict[str, Any], cwd: Path | None) -> dict[str, Any]:
    environment = os.environ.copy()
    environment.update(scenario.get("environment", {}))
    try:
        completed = subprocess.run(
            scenario["argv"],
            cwd=str(cwd) if cwd else None,
            env=environment,
            text=True,
            capture_output=True,
            timeout=float(scenario.get("timeoutSeconds", 10)),
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "id": scenario["id"],
            "passed": False,
            "error": f"timed out after {exc.timeout} seconds",
        }
    except OSError as exc:
        return {"id": scenario["id"], "passed": False, "error": str(exc)}

    stdout_ok, stdout_reason = stream_matches(
        scenario.get("stdout", {"mode": "any"}), completed.stdout
    )
    stderr_ok, stderr_reason = stream_matches(
        scenario.get("stderr", {"mode": "any"}), completed.stderr
    )
    exit_ok = completed.returncode == scenario["expectedExit"]
    failures = []
    if not exit_ok:
        failures.append(f"exit {completed.returncode}, expected {scenario['expectedExit']}")
    if not stdout_ok:
        failures.append(f"stdout mismatch: {stdout_reason}; actual {completed.stdout!r}")
    if not stderr_ok:
        failures.append(f"stderr mismatch: {stderr_reason}; actual {completed.stderr!r}")
    return {
        "id": scenario["id"],
        "passed": not failures,
        "failures": failures,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("contract", type=Path, help="JSON contract file.")
    parser.add_argument(
        "--confirm-execute",
        action="store_true",
        help="Execute each declared argv directly without a shell. Omit for validation only.",
    )
    parser.add_argument("--cwd", type=Path, help="Working directory for explicit execution.")
    parser.add_argument(
        "--scenario", action="append", help="Run only the named scenario; repeatable."
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON report.")
    args = parser.parse_args()

    try:
        data = json.loads(args.contract.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    errors = validate_contract(data)
    if errors:
        if args.json:
            json.dump({"valid": False, "errors": errors}, sys.stdout, indent=2)
            print()
        else:
            for error in errors:
                print(f"error: {error}")
        return 2

    if not args.confirm_execute:
        report = {
            "valid": True,
            "executed": False,
            "scenarios": len(data["scenarios"]),
            "message": "Contract is structurally valid. No command was executed.",
        }
        if args.json:
            json.dump(report, sys.stdout, indent=2)
            print()
        else:
            print(report["message"])
            print(f"scenarios: {report['scenarios']}")
        return 0

    cwd = args.cwd.expanduser().resolve() if args.cwd else None
    if cwd and not cwd.is_dir():
        parser.error(f"--cwd is not a directory: {cwd}")
    selected = set(args.scenario or [])
    unknown = selected - {item["id"] for item in data["scenarios"]}
    if unknown:
        parser.error(f"unknown scenario IDs: {', '.join(sorted(unknown))}")
    scenarios = [item for item in data["scenarios"] if not selected or item["id"] in selected]
    results = [execute_scenario(item, cwd) for item in scenarios]
    report = {
        "valid": True,
        "executed": True,
        "passed": all(item["passed"] for item in results),
        "results": results,
    }
    if args.json:
        json.dump(report, sys.stdout, indent=2)
        print()
    else:
        for item in results:
            print(f"{'PASS' if item['passed'] else 'FAIL'} {item['id']}")
            for failure in item.get("failures", []):
                print(f"  {failure}")
            if item.get("error"):
                print(f"  {item['error']}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
