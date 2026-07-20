#!/usr/bin/env python3
"""Flag PostgreSQL migration SQL patterns that require explicit operational review.

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
    statement_excerpt: str
    message: str


def strip_comments(text: str) -> str:
    text = re.sub(
        r"/\*.*?\*/", lambda match: "\n" * match.group(0).count("\n"), text, flags=re.DOTALL
    )
    return re.sub(r"--[^\n]*", "", text)


def split_statements(text: str) -> list[tuple[int, str]]:
    statements: list[tuple[int, str]] = []
    start = 0
    in_single = False
    in_double = False
    dollar_tag: str | None = None
    index = 0
    while index < len(text):
        if dollar_tag:
            if text.startswith(dollar_tag, index):
                index += len(dollar_tag)
                dollar_tag = None
                continue
        elif in_single:
            if text[index] == "'" and index + 1 < len(text) and text[index + 1] == "'":
                index += 2
                continue
            if text[index] == "'":
                in_single = False
        elif in_double:
            if text[index] == '"' and index + 1 < len(text) and text[index + 1] == '"':
                index += 2
                continue
            if text[index] == '"':
                in_double = False
        else:
            if text[index] == "'":
                in_single = True
            elif text[index] == '"':
                in_double = True
            elif text[index] == "$":
                match = re.match(r"\$[A-Za-z_][A-Za-z0-9_]*\$|\$\$", text[index:])
                if match:
                    dollar_tag = match.group(0)
                    index += len(dollar_tag)
                    continue
            elif text[index] == ";":
                statement = text[start : index + 1].strip()
                if statement:
                    line = text.count("\n", 0, start) + 1
                    statements.append((line, statement))
                start = index + 1
        index += 1
    remainder = text[start:].strip()
    if remainder:
        statements.append((text.count("\n", 0, start) + 1, remainder))
    return statements


RULES: tuple[tuple[str, str, re.Pattern[str], str], ...] = (
    (
        "high",
        "blocking-index-build",
        re.compile(r"^\s*create\s+(?:unique\s+)?index\s+(?!concurrently\b)", re.IGNORECASE),
        "Regular CREATE INDEX can block writes; justify it or evaluate a concurrent build.",
    ),
    (
        "high",
        "destructive-drop",
        re.compile(
            r"^\s*(?:drop\s+(?:table|schema|type)|alter\s+table\b.*\bdrop\s+column\b)",
            re.IGNORECASE | re.DOTALL,
        ),
        "Destructive DDL needs proof of disuse, retention/recovery, compatibility, and rollback analysis.",
    ),
    (
        "high",
        "truncate",
        re.compile(r"^\s*truncate\b", re.IGNORECASE),
        "TRUNCATE is destructive and acquires strong locks; require explicit data and dependency review.",
    ),
    (
        "high",
        "unbounded-update",
        re.compile(r"^\s*update\b(?!.*\bwhere\b)", re.IGNORECASE | re.DOTALL),
        "UPDATE without a WHERE clause can rewrite an entire table; use an intentional bounded plan.",
    ),
    (
        "warning",
        "set-not-null",
        re.compile(r"\balter\s+column\b.*\bset\s+not\s+null\b", re.IGNORECASE | re.DOTALL),
        "SET NOT NULL needs existing-data proof and target-version lock/scan analysis.",
    ),
    (
        "warning",
        "add-required-column",
        re.compile(r"\badd\s+column\b.*\bnot\s+null\b", re.IGNORECASE | re.DOTALL),
        "Adding a required column needs default, rewrite, compatibility, and backfill analysis.",
    ),
    (
        "warning",
        "alter-column-type",
        re.compile(r"\balter\s+column\b.*\btype\b", re.IGNORECASE | re.DOTALL),
        "Type changes can rewrite data and break mixed-version clients; analyze USING, locks, and expansion alternatives.",
    ),
    (
        "warning",
        "validate-constraint",
        re.compile(r"\bvalidate\s+constraint\b", re.IGNORECASE),
        "Constraint validation scans existing rows and needs resource, lock, and replication monitoring.",
    ),
    (
        "warning",
        "cascade",
        re.compile(r"\bcascade\b", re.IGNORECASE),
        "CASCADE can affect unlisted dependents; enumerate and approve them explicitly.",
    ),
    (
        "warning",
        "explicit-lock",
        re.compile(r"^\s*lock\s+table\b", re.IGNORECASE),
        "Explicit table locking needs lock-mode, acquisition, duration, and traffic analysis.",
    ),
)


def excerpt(statement: str, limit: int = 120) -> str:
    compact = " ".join(statement.split())
    return compact if len(compact) <= limit else compact[: limit - 1] + "…"


def analyze(text: str) -> list[Finding]:
    sanitized = strip_comments(text)
    findings: list[Finding] = []
    statements = split_statements(sanitized)
    has_transaction = any(
        re.match(r"^\s*(?:begin|start\s+transaction)\b", statement, re.IGNORECASE)
        for _, statement in statements
    )
    for line, statement in statements:
        for severity, code, pattern, message in RULES:
            if pattern.search(statement):
                findings.append(Finding(severity, code, line, excerpt(statement), message))
        if (
            re.search(
                r"\b(?:create|drop|reindex)\s+index\s+concurrently\b", statement, re.IGNORECASE
            )
            and has_transaction
        ):
            findings.append(
                Finding(
                    "high",
                    "concurrent-index-in-transaction",
                    line,
                    excerpt(statement),
                    "Concurrent index operations cannot run inside a transaction block; split the migration phase.",
                )
            )
    return sorted(findings, key=lambda item: (item.line, item.severity, item.code))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "migration", type=Path, help="SQL file to inspect; use '-' for standard input."
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON.")
    parser.add_argument(
        "--fail-on",
        choices=("never", "high", "warning"),
        default="never",
        help="Return status 1 at this threshold.",
    )
    args = parser.parse_args()
    try:
        text = (
            sys.stdin.read()
            if str(args.migration) == "-"
            else args.migration.read_text(encoding="utf-8")
        )
    except OSError as exc:
        parser.error(str(exc))

    findings = analyze(text)
    report = {
        "findings": [asdict(item) for item in findings],
        "caveat": "Lexical findings require target-version, catalog, workload, and migration-runner review.",
    }
    if args.json:
        json.dump(report, sys.stdout, indent=2)
        print()
    elif findings:
        for item in findings:
            print(f"{item.severity.upper()} {item.code} line {item.line}: {item.message}")
            print(f"  {item.statement_excerpt}")
        print(f"caveat: {report['caveat']}")
    else:
        print("No heuristic findings. This does not prove the migration is safe.")

    ranks = {"high": 2, "warning": 1}
    threshold = {"never": 99, "high": 2, "warning": 1}[args.fail_on]
    return 1 if any(ranks[item.severity] >= threshold for item in findings) else 0


if __name__ == "__main__":
    raise SystemExit(main())
