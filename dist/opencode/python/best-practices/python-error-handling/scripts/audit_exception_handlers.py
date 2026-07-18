#!/usr/bin/env python3
"""Statically audit Python exception-handling patterns without importing project code.

Requires Python 3.11 or newer and only the standard library. Reads local Python source and
writes findings only to stdout; it never modifies inputs, contacts the network, or executes
project code or external commands.
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    severity: str
    code: str
    message: str


def dotted_name(node: ast.AST | None) -> str:
    if node is None:
        return ""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        left = dotted_name(node.value)
        return f"{left}.{node.attr}" if left else node.attr
    if isinstance(node, ast.Call):
        return dotted_name(node.func)
    if isinstance(node, ast.Tuple):
        return ", ".join(filter(None, (dotted_name(item) for item in node.elts)))
    return ""


class Auditor(ast.NodeVisitor):
    def __init__(self, path: Path) -> None:
        self.path = path
        self.findings: list[Finding] = []
        self.except_depth = 0

    def add(self, node: ast.AST, severity: str, code: str, message: str) -> None:
        self.findings.append(
            Finding(str(self.path), getattr(node, "lineno", 0), severity, code, message)
        )

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        caught = dotted_name(node.type)
        if node.type is None:
            self.add(
                node,
                "error",
                "bare-except",
                "Bare except also catches interrupts and system-exit signals.",
            )
        elif caught in {"BaseException", "Exception"}:
            self.add(
                node,
                "warning",
                "broad-catch",
                f"Broad catch of {caught}; confirm this is a top-level boundary.",
            )
        if len(node.body) == 1 and isinstance(node.body[0], ast.Pass):
            self.add(node, "error", "silent-pass", "Exception is silently discarded with pass.")
        self.except_depth += 1
        for child in node.body:
            self.visit(child)
        self.except_depth -= 1

    def visit_Raise(self, node: ast.Raise) -> None:
        if self.except_depth and node.exc is not None and node.cause is None:
            name = dotted_name(node.exc)
            self.add(
                node,
                "info",
                "translation-without-cause",
                f"Raised {name or 'a new exception'} inside an except block without an explicit cause; review chaining.",
            )
        if isinstance(node.exc, ast.Call) and dotted_name(node.exc.func) in {
            "Exception",
            "BaseException",
        }:
            self.add(
                node,
                "warning",
                "generic-raise",
                "Generic Exception/BaseException weakens caller contracts.",
            )
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        name = dotted_name(node.func)
        if name in {"warnings.warn", "warn"}:
            if not any(keyword.arg == "stacklevel" for keyword in node.keywords):
                self.add(
                    node,
                    "info",
                    "warning-stacklevel",
                    "warnings.warn has no explicit stacklevel; caller location may be unhelpful.",
                )
        if self.except_depth and name.endswith((".error", ".warning", ".critical")):
            if not any(keyword.arg == "exc_info" for keyword in node.keywords):
                self.add(
                    node,
                    "info",
                    "log-without-traceback",
                    "Logging inside an exception handler may omit traceback context; review boundary policy.",
                )
        self.generic_visit(node)


def python_files(root: Path) -> Iterable[Path]:
    if root.is_file():
        if root.suffix == ".py":
            yield root
        return
    for path in sorted(root.rglob("*.py")):
        if not any(
            part in {".git", ".venv", "venv", "__pycache__", "build", "dist"} for part in path.parts
        ):
            yield path


def audit(root: Path) -> dict:
    findings: list[Finding] = []
    parse_errors = []
    for path in python_files(root):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (OSError, UnicodeError, SyntaxError) as exc:
            parse_errors.append({"path": str(path), "error": str(exc)})
            continue
        visitor = Auditor(path)
        visitor.visit(tree)
        findings.extend(visitor.findings)
    return {
        "root": str(root),
        "findings": [asdict(item) for item in findings],
        "parseErrors": parse_errors,
        "limitations": [
            "Findings are review prompts, not proof of a defect.",
            "Control flow, exception ownership, and framework boundaries require human analysis.",
            "The audit does not import or execute project code.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", nargs="?", default=".", help="Python file or directory.")
    parser.add_argument("--json", action="store_true", help="Emit JSON.")
    args = parser.parse_args()
    root = Path(args.path).expanduser().resolve()
    if not root.exists():
        parser.error(f"path does not exist: {root}")
    report = audit(root)
    if args.json:
        json.dump(report, sys.stdout, indent=2)
        print()
    else:
        for item in report["findings"]:
            print(
                f"{item['path']}:{item['line']}: {item['severity']}: {item['code']}: {item['message']}"
            )
        for item in report["parseErrors"]:
            print(f"{item['path']}: error: parse-error: {item['error']}")
        print(f"findings: {len(report['findings'])}")
        print(f"parse errors: {len(report['parseErrors'])}")
    if report["parseErrors"]:
        return 2
    return 1 if any(item["severity"] == "error" for item in report["findings"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
