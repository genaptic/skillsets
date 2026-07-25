from __future__ import annotations

import ast
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MARKER = "windows_release_integration"
APPROVED_WINDOWS_SKIP = (
    "tests/test_release_security.py::"
    "test_publication_preview_uses_exact_base_and_preserves_newer_candidate"
)


def _sanitized_pytest_environment() -> dict[str, str]:
    environment = os.environ.copy()
    for name in (
        "PYTEST_ADDOPTS",
        "PYTEST_XDIST_TESTRUNUID",
        "PYTEST_XDIST_WORKER",
        "PYTEST_XDIST_WORKER_COUNT",
    ):
        environment.pop(name, None)
    return environment


def _collection(marker_expression: str | None = None) -> set[str]:
    command = [
        sys.executable,
        "-m",
        "pytest",
        "--collect-only",
        "-q",
        "--no-cov",
        "-p",
        "no:cacheprovider",
        "-c",
        str(ROOT / "pyproject.toml"),
    ]
    if marker_expression is not None:
        command.extend(["-m", marker_expression])
    completed = subprocess.run(
        command,
        cwd=ROOT,
        env=_sanitized_pytest_environment(),
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    return {
        line for line in completed.stdout.splitlines() if line.startswith("tests/") and "::" in line
    }


def _uses_marker(node: ast.AST) -> bool:
    return any(isinstance(item, ast.Attribute) and item.attr == MARKER for item in ast.walk(node))


def test_windows_marker_partition_is_exhaustive_disjoint_and_keeps_skip_visible() -> None:
    full = _collection()
    core = _collection(f"not {MARKER}")
    release = _collection(MARKER)

    assert core.isdisjoint(release)
    assert core | release == full
    assert APPROVED_WINDOWS_SKIP in release
    assert APPROVED_WINDOWS_SKIP not in core


def test_windows_release_marker_is_function_scoped_and_has_no_arguments() -> None:
    registered = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert f'"{MARKER}:' in registered
    assert "windows_slow_first" not in registered

    errors: list[str] = []
    for path in sorted((ROOT / "tests").glob("test_*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        allowed_references: set[int] = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for decorator in node.decorator_list:
                    if isinstance(decorator, ast.Attribute) and decorator.attr == MARKER:
                        allowed_references.add(id(decorator))
                    elif _uses_marker(decorator):
                        errors.append(
                            f"{path.relative_to(ROOT)}:{node.lineno}: "
                            f"{MARKER} must be a bare function decorator"
                        )
            elif isinstance(node, ast.ClassDef) and any(
                _uses_marker(decorator) for decorator in node.decorator_list
            ):
                errors.append(
                    f"{path.relative_to(ROOT)}:{node.lineno}: {MARKER} cannot decorate a class"
                )

        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Attribute)
                and node.attr == MARKER
                and id(node) not in allowed_references
            ):
                errors.append(
                    f"{path.relative_to(ROOT)}:{node.lineno}: "
                    f"{MARKER} must be a bare function decorator"
                )

    assert errors == []


def test_nested_collection_does_not_inherit_outer_shard_or_worker_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inherited = {
        "PYTEST_ADDOPTS": '-n 4 --dist=loadgroup -m "windows_release_integration"',
        "PYTEST_XDIST_TESTRUNUID": "run-id",
        "PYTEST_XDIST_WORKER": "gw3",
        "PYTEST_XDIST_WORKER_COUNT": "4",
    }
    for name, value in inherited.items():
        monkeypatch.setenv(name, value)

    environment = _sanitized_pytest_environment()

    assert inherited.keys().isdisjoint(environment)


def test_unknown_marker_is_rejected_under_strict_marker_validation(tmp_path: Path) -> None:
    unknown = tmp_path / "test_unknown_windows_partition_marker.py"
    unknown.write_text(
        "import pytest\n\n"
        "@pytest.mark.unknown_windows_partition_marker\n"
        "def test_unknown_marker():\n"
        "    pass\n",
        encoding="utf-8",
    )
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "--collect-only",
            "-q",
            "--no-cov",
            "-p",
            "no:cacheprovider",
            "-c",
            str(ROOT / "pyproject.toml"),
            str(unknown),
        ],
        cwd=ROOT,
        env=_sanitized_pytest_environment(),
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode != 0
    assert "unknown_windows_partition_marker" in completed.stdout + completed.stderr
