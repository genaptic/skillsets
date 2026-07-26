#!/usr/bin/env python3
"""Render a PostgreSQL recovery-drill worksheet from a reviewed JSON profile.

Requires Python 3.11 or newer and only the standard library. Reads one local JSON profile
and writes to stdout or one explicit new output file, refusing overwrites. It never contacts
PostgreSQL or the network and never executes recovery steps or external commands.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def require(value: Any, kind: type, path: str, errors: list[str]) -> Any:
    if not isinstance(value, kind):
        errors.append(f"{path} must be {kind.__name__}")
    return value


def validate(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["profile must be a JSON object"]
    if data.get("schemaVersion") != 1:
        errors.append("schemaVersion must be 1")
    for section in ("system", "scenario", "backup", "target", "validation", "evidence"):
        require(data.get(section), dict, section, errors)
    for section in ("roles", "observability", "stopConditions"):
        require(data.get(section), list, section, errors)

    scenario = data.get("scenario", {})
    if isinstance(scenario, dict):
        for field in ("id", "title", "description", "scope", "recoveryTarget"):
            if not isinstance(scenario.get(field), str) or not scenario.get(field):
                errors.append(f"scenario.{field} must be a non-empty string")
        for field in ("rpoMinutes", "rtoMinutes"):
            value = scenario.get(field)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                errors.append(f"scenario.{field} must be a non-negative integer")

    roles = data.get("roles", [])
    if isinstance(roles, list):
        for index, item in enumerate(roles):
            if not isinstance(item, dict) or not all(
                isinstance(item.get(field), str) and item.get(field)
                for field in ("role", "responsibility")
            ):
                errors.append(
                    f"roles[{index}] must contain non-empty role and responsibility strings"
                )

    validation = data.get("validation", {})
    if isinstance(validation, dict):
        for field in ("technical", "business"):
            values = validation.get(field)
            if (
                not isinstance(values, list)
                or not values
                or not all(isinstance(value, str) and value for value in values)
            ):
                errors.append(f"validation.{field} must be a non-empty string array")
    return errors


def bullets(values: list[str]) -> str:
    return "\n".join(f"- [ ] {value}" for value in values) if values else "- [ ] Define."


def render(data: dict[str, Any]) -> str:
    system = data["system"]
    scenario = data["scenario"]
    backup = data["backup"]
    target = data["target"]
    validation = data["validation"]
    evidence = data["evidence"]
    roles = data.get("roles", [])

    role_lines = (
        "\n".join(f"- **{item['role']}:** {item['responsibility']}" for item in roles)
        or "- Define exercise roles."
    )

    extension_lines = ", ".join(target.get("extensions", [])) or "None declared"
    tablespace_lines = ", ".join(target.get("tablespaces", [])) or "None declared"
    backup_checks = backup.get("verification", [])
    if not isinstance(backup_checks, list):
        backup_checks = []

    return f"""# Recovery drill — {scenario["title"]}

> Generated worksheet only. It does not authorize production access or execute recovery.

## Control

- System: `{system.get("name", "unknown")}`
- Environment: `{system.get("environment", "unknown")}`
- PostgreSQL version: `{system.get("postgresVersion", "unknown")}`
- Provider: `{system.get("provider", "unknown")}`
- Scenario ID: `{scenario["id"]}`
- Scope: `{scenario["scope"]}`
- Target RPO: {scenario["rpoMinutes"]} minutes
- Target RTO: {scenario["rtoMinutes"]} minutes
- Recovery target: {scenario["recoveryTarget"]}
- Failure injection: {scenario.get("failureInjection", "None declared")}

### Scenario

{scenario["description"]}

### Roles

{role_lines}

## Preconditions and stop conditions

### Stop conditions

{bullets(data.get("stopConditions", []))}

### Source backup requirements

- Method: {backup.get("method", "unknown")}
- Location class: {backup.get("sourceLocationClass", "unknown")}
- Maximum backup age: {backup.get("maximumBackupAgeHours", "unknown")} hours

{bullets(backup_checks)}

## Isolated target

- Isolation: {target.get("isolation", "unknown")}
- PostgreSQL version: {target.get("version", "unknown")}
- Capacity: {target.get("capacity", "unknown")}
- Extensions: {extension_lines}
- Tablespaces: {tablespace_lines}

## Stage timeline

| Timestamp | Actor | Stage/action | Evidence/result | Decision |
|---|---|---|---|---|
| | | Authorization and isolation | | |
| | | Artifact selection and integrity | | |
| | | Target provisioning | | |
| | | Base restore | | |
| | | WAL replay/recovery target | | |
| | | Technical validation | | |
| | | Business validation | | |
| | | Cutover rehearsal/cleanup | | |

## Technical validation

{bullets(validation.get("technical", []))}

## Business validation

{bullets(validation.get("business", []))}

## Observability

{bullets(data.get("observability", []))}

## Results

- Selected backup ID and creation time:
- Selected WAL/timeline evidence:
- Achieved recovery point:
- Calculated data-loss window:
- Authorization duration:
- Provisioning duration:
- Transfer duration:
- Restore/replay duration:
- Technical validation duration:
- Business validation duration:
- Total achieved RTO:
- RPO target met:
- RTO target met:
- Production-readiness decision:

## Evidence and security

- Evidence directory: `{evidence.get("directory", "not declared")}`
- Redaction policy: {evidence.get("redactionPolicy", "not declared")}
- Recovery identity and key-access audit:
- Artifact and report retention:
- Isolated target cleanup/secure deletion:

## Deviations and remediation

| ID | Deviation or residual risk | Consequence | Owner | Due date | Verification |
|---|---|---|---|---|---|
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile", type=Path, help="Recovery profile JSON.")
    parser.add_argument("--output", type=Path, help="Write to a new file; default is stdout.")
    args = parser.parse_args()
    try:
        data = json.loads(args.profile.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    errors = validate(data)
    if errors:
        for error in errors:
            print(f"error: {error}", file=sys.stderr)
        return 2

    text = render(data)
    if args.output:
        path = args.output.expanduser()
        if path.exists():
            parser.error(f"refusing to overwrite existing file: {path}")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
        print(f"Wrote {path}", file=sys.stderr)
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
