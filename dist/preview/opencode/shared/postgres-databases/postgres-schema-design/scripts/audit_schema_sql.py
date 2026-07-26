#!/usr/bin/env python3
"""Perform a conservative, offline heuristic review of PostgreSQL DDL text.

Requires Python 3.11 or newer and only the standard library. Reads SQL from one local file
or stdin and writes findings only to stdout; it never modifies files, connects to PostgreSQL,
contacts the network, or executes SQL or external commands.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class Finding:
    severity: str
    code: str
    line: int
    message: str


RULES: tuple[tuple[str, str, str, re.Pattern[str]], ...] = (
    (
        "warning",
        "serial-key",
        "Review legacy serial types; identity columns make generation semantics explicit.",
        re.compile(r"\b(?:smallserial|serial|bigserial)\b", re.IGNORECASE),
    ),
    (
        "warning",
        "timestamp-without-zone",
        "Confirm that timestamp without time zone represents a civil/local value, not an instant.",
        re.compile(
            r"\btimestamp\s+without\s+time\s+zone\b|\btimestamp\b(?!\s+with)", re.IGNORECASE
        ),
    ),
    (
        "warning",
        "floating-money",
        "Floating-point types are usually inappropriate for exact monetary amounts.",
        re.compile(r"\b(?:real|double\s+precision|float[48]?)\b", re.IGNORECASE),
    ),
    (
        "warning",
        "varchar-without-domain-reason",
        "Confirm that the varchar length is a real domain rule; text is often clearer.",
        re.compile(r"\bvarchar\s*\(\s*\d+\s*\)", re.IGNORECASE),
    ),
    (
        "error",
        "public-create-grant",
        "Granting CREATE on public to PUBLIC expands the trusted search path surface.",
        re.compile(r"\bgrant\s+create\s+on\s+schema\s+public\s+to\s+public\b", re.IGNORECASE),
    ),
    (
        "warning",
        "unqualified-create-table",
        "Schema-qualify application objects and define ownership/search_path deliberately.",
        re.compile(r"^\s*create\s+table\s+(?:if\s+not\s+exists\s+)?(?![\"\w]+\.)", re.IGNORECASE),
    ),
    (
        "warning",
        "json-default-object",
        "Confirm a JSON object default is semantically valid rather than hiding missing input.",
        re.compile(r"\bjsonb?\b[^;,\n]*\bdefault\s+'?\{\}'?(?:::jsonb?)?", re.IGNORECASE),
    ),
    (
        "warning",
        "cascade-delete",
        "Confirm ON DELETE CASCADE matches lifecycle ownership and bounded delete impact.",
        re.compile(r"\bon\s+delete\s+cascade\b", re.IGNORECASE),
    ),
)


def strip_comments(text: str) -> str:
    text = re.sub(
        r"/\*.*?\*/", lambda match: "\n" * match.group(0).count("\n"), text, flags=re.DOTALL
    )
    return re.sub(r"--[^\n]*", "", text)


def line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def analyze(text: str) -> list[Finding]:
    sanitized = strip_comments(text)
    findings: list[Finding] = []
    for severity, code, message, pattern in RULES:
        for match in pattern.finditer(sanitized):
            findings.append(Finding(severity, code, line_number(sanitized, match.start()), message))

    for match in re.finditer(
        r"\bcreate\s+table\b(?P<body>.*?);",
        sanitized,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        statement = match.group(0)
        if not re.search(r"\bprimary\s+key\b", statement, re.IGNORECASE):
            findings.append(
                Finding(
                    "warning",
                    "table-without-primary-key",
                    line_number(sanitized, match.start()),
                    "Confirm whether this table intentionally lacks a primary key.",
                )
            )

    findings.sort(key=lambda item: (item.line, item.severity, item.code))
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ddl", type=Path, help="SQL file to inspect; use '-' for standard input.")
    parser.add_argument("--json", action="store_true", help="Emit a JSON report.")
    parser.add_argument(
        "--fail-on",
        choices=("never", "error", "warning"),
        default="never",
        help="Choose a finding threshold that produces exit status 1.",
    )
    args = parser.parse_args()

    try:
        text = sys.stdin.read() if str(args.ddl) == "-" else args.ddl.read_text(encoding="utf-8")
    except OSError as exc:
        parser.error(str(exc))

    findings = analyze(text)
    if args.json:
        json.dump({"findings": [asdict(item) for item in findings]}, sys.stdout, indent=2)
        print()
    elif findings:
        for item in findings:
            print(f"{item.severity.upper()} {item.code} line {item.line}: {item.message}")
    else:
        print("No heuristic findings. This does not prove the DDL is safe or correct.")

    ranks = {"never": 99, "error": 2, "warning": 1}
    severity_rank = {"error": 2, "warning": 1}
    threshold = ranks[args.fail_on]
    return 1 if any(severity_rank[item.severity] >= threshold for item in findings) else 0


if __name__ == "__main__":
    raise SystemExit(main())
