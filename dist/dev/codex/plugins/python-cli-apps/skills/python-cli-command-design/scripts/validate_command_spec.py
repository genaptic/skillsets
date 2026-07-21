#!/usr/bin/env python3
"""Validate a JSON command-interface specification without executing a CLI.

Requires Python 3.11 or newer and only the standard library. Reads one local JSON file and
writes findings only to stdout; it never modifies files, contacts the network, or executes
the described CLI or any external command.
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
    path: str
    code: str
    message: str


def add(findings: list[Finding], severity: str, path: str, code: str, message: str) -> None:
    findings.append(Finding(severity, path, code, message))


def validate_options(options: Any, path: str, findings: list[Finding]) -> None:
    if not isinstance(options, list):
        add(findings, "error", path, "options-type", "options must be an array.")
        return
    seen: set[str] = set()
    for index, option in enumerate(options):
        current = f"{path}[{index}]"
        if not isinstance(option, dict):
            add(findings, "error", current, "option-type", "option must be an object.")
            continue
        names = option.get("names")
        if (
            not isinstance(names, list)
            or not names
            or not all(isinstance(item, str) for item in names)
        ):
            add(
                findings,
                "error",
                current,
                "option-names",
                "names must be a non-empty string array.",
            )
            continue
        if not any(name.startswith("--") and len(name) > 2 for name in names):
            add(
                findings,
                "warning",
                current,
                "missing-long-name",
                "Public options should normally have a long name.",
            )
        for name in names:
            if not name.startswith("-") or name == "-":
                add(
                    findings,
                    "error",
                    current,
                    "invalid-option-name",
                    f"Invalid option name: {name!r}.",
                )
            if name in seen:
                add(
                    findings,
                    "error",
                    current,
                    "duplicate-option",
                    f"Duplicate option name: {name}.",
                )
            seen.add(name)
        if not isinstance(option.get("help"), str) or not option.get("help", "").strip():
            add(findings, "error", current, "missing-help", "Option needs concise help text.")
        if option.get("secret") is True and option.get("source") == "argument":
            add(
                findings,
                "warning",
                current,
                "secret-argument",
                "Secrets on command lines can be exposed in history and process listings; prefer a safer source.",
            )


def validate_arguments(arguments: Any, path: str, findings: list[Finding]) -> None:
    if not isinstance(arguments, list):
        add(findings, "error", path, "arguments-type", "arguments must be an array.")
        return
    variadic_seen = False
    names: set[str] = set()
    for index, argument in enumerate(arguments):
        current = f"{path}[{index}]"
        if not isinstance(argument, dict):
            add(findings, "error", current, "argument-type", "argument must be an object.")
            continue
        name = argument.get("name")
        if not isinstance(name, str) or not name:
            add(findings, "error", current, "argument-name", "argument needs a name.")
        elif name in names:
            add(findings, "error", current, "duplicate-argument", f"Duplicate argument: {name}.")
        else:
            names.add(name)
        if variadic_seen:
            add(
                findings,
                "error",
                current,
                "after-variadic",
                "No positional argument may follow a variadic argument.",
            )
        if argument.get("variadic") is True:
            variadic_seen = True
        if (
            argument.get("optional") is True
            and index < len(arguments) - 1
            and not argument.get("variadic")
        ):
            add(
                findings,
                "warning",
                current,
                "optional-before-required",
                "An optional positional before later arguments can be ambiguous.",
            )


def validate_commands(commands: Any, path: str, findings: list[Finding]) -> None:
    if not isinstance(commands, list) or not commands:
        add(findings, "error", path, "commands-type", "commands must be a non-empty array.")
        return
    siblings: set[str] = set()
    for index, command in enumerate(commands):
        current = f"{path}[{index}]"
        if not isinstance(command, dict):
            add(findings, "error", current, "command-type", "command must be an object.")
            continue
        name = command.get("name")
        if not isinstance(name, str) or not name or name.startswith("-") or " " in name:
            add(
                findings,
                "error",
                current,
                "command-name",
                "command name must be one token and not begin with '-'.",
            )
        elif name in siblings:
            add(
                findings,
                "error",
                current,
                "duplicate-command",
                f"Duplicate sibling command: {name}.",
            )
        else:
            siblings.add(name)
        if not isinstance(command.get("summary"), str) or not command.get("summary", "").strip():
            add(findings, "error", current, "missing-summary", "command needs a one-line summary.")
        validate_options(command.get("options", []), f"{current}.options", findings)
        validate_arguments(command.get("arguments", []), f"{current}.arguments", findings)
        if "commands" in command:
            validate_commands(command["commands"], f"{current}.commands", findings)


def validate_spec(data: Any) -> list[Finding]:
    findings: list[Finding] = []
    if not isinstance(data, dict):
        return [Finding("error", "<root>", "root-type", "Specification must be a JSON object.")]
    if not isinstance(data.get("program"), str) or not data.get("program", "").strip():
        add(findings, "error", "program", "program-name", "program must be a non-empty string.")
    precedence = data.get("configurationPrecedence")
    expected = ["command-line", "environment", "configuration-file", "default"]
    if precedence != expected:
        add(
            findings,
            "warning",
            "configurationPrecedence",
            "precedence",
            f"Document an explicit precedence. Recommended default is {expected!r}.",
        )
    validate_options(data.get("globalOptions", []), "globalOptions", findings)
    validate_commands(data.get("commands"), "commands", findings)
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("spec", type=Path, help="JSON command specification.")
    parser.add_argument("--json", action="store_true", help="Emit findings as JSON.")
    args = parser.parse_args()
    try:
        data = json.loads(args.spec.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    findings = validate_spec(data)
    if args.json:
        json.dump(
            {
                "valid": not any(item.severity == "error" for item in findings),
                "findings": [asdict(item) for item in findings],
            },
            sys.stdout,
            indent=2,
        )
        print()
    else:
        for item in findings:
            print(f"{item.severity}: {item.path}: {item.code}: {item.message}")
        print(f"findings: {len(findings)}")
    return 1 if any(item.severity == "error" for item in findings) else 0


if __name__ == "__main__":
    raise SystemExit(main())
