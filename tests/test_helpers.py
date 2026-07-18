from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from skillpack_tools.models import discover_packs

ROOT = Path(__file__).resolve().parents[1]


def run_helper(
    script: Path, *arguments: str, expected: int = 0
) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        [sys.executable, "-I", "-S", str(script), *map(str, arguments)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )
    assert completed.returncode == expected, (
        f"command failed: {script} {' '.join(map(str, arguments))}\n"
        f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
    )
    return completed


def canonical_scripts() -> list[Path]:
    scripts: list[Path] = []
    for pack in discover_packs(ROOT):
        for skill in pack.skills:
            scripts.extend(sorted((pack.path / "skills" / skill / "scripts").glob("*.py")))
    return scripts


def test_helper_inventory_is_exact() -> None:
    scripts = canonical_scripts()
    assert len(scripts) == 14
    assert len({script.resolve() for script in scripts}) == 14


@pytest.mark.parametrize("script", canonical_scripts(), ids=lambda value: value.stem)
def test_every_helper_has_working_help(script: Path) -> None:
    completed = run_helper(script, "--help")
    assert "usage:" in completed.stdout.lower()


def test_python_helper_happy_paths(tmp_path: Path) -> None:
    layout = (
        ROOT / "packs/python/best-practices/skills/python-project-layout/scripts/inspect_layout.py"
    )
    report = run_helper(layout, ROOT, "--json")
    assert json.loads(report.stdout)["root"] == str(ROOT.resolve())

    inventory = (
        ROOT
        / "packs/python/best-practices/skills/python-testing-strategy/scripts/inventory_tests.py"
    )
    report = run_helper(inventory, ROOT / "tests", "--json")
    assert json.loads(report.stdout)["totals"]["files"] >= 3

    safe_source = tmp_path / "safe.py"
    safe_source.write_text(
        "class DomainError(Exception):\n    pass\n\n"
        "def parse(value: str) -> int:\n"
        "    try:\n        return int(value)\n"
        "    except ValueError as exc:\n"
        "        raise DomainError('invalid integer') from exc\n",
        encoding="utf-8",
    )
    audit = (
        ROOT
        / "packs/python/best-practices/skills/python-error-handling/scripts/audit_exception_handlers.py"
    )
    report = run_helper(audit, safe_source, "--json")
    assert json.loads(report.stdout)["parseErrors"] == []


def test_cli_helper_happy_paths() -> None:
    base = ROOT / "packs/python/cli-apps/skills"
    command_spec = base / "python-cli-command-design/assets/command-spec.example.json"
    command_validator = base / "python-cli-command-design/scripts/validate_command_spec.py"
    report = run_helper(command_validator, command_spec, "--json")
    assert json.loads(report.stdout)["valid"] is True

    contract = base / "python-cli-error-output/assets/cli-error-contract.example.json"
    contract_checker = base / "python-cli-error-output/scripts/check_cli_contract.py"
    report = run_helper(contract_checker, contract, "--json")
    data = json.loads(report.stdout)
    assert data["valid"] is True
    assert data["executed"] is False

    surface = base / "python-cli-testing/assets/cli-test-surface.example.json"
    matrix = base / "python-cli-testing/scripts/generate_cli_test_matrix.py"
    report = run_helper(matrix, surface, "--format", "json", "--max-combinations", "5")
    assert len(json.loads(report.stdout)["cases"]) == 10


def test_postgres_helper_happy_paths() -> None:
    base = ROOT / "packs/shared/postgres-databases/skills"

    schema = run_helper(
        base / "postgres-schema-design/scripts/audit_schema_sql.py",
        base / "postgres-schema-design/assets/schema.example.sql",
        "--json",
    )
    assert "findings" in json.loads(schema.stdout)

    review = run_helper(
        base / "postgres-schema-review/scripts/render_review_queries.py",
        "--section",
        "context",
        "--section",
        "constraints",
    )
    assert "BEGIN TRANSACTION READ ONLY" in review.stdout
    assert review.stdout.rstrip().endswith("ROLLBACK;")

    plan = run_helper(
        base / "postgres-query-performance-review/scripts/summarize_explain_json.py",
        base / "postgres-query-performance-review/assets/explain-plan.example.json",
        "--json",
    )
    assert json.loads(plan.stdout)["nodeCount"] == 3

    indexes = run_helper(
        base / "postgres-index-design/scripts/review_index_inventory.py",
        base / "postgres-index-design/assets/index-inventory.example.json",
        "--json",
    )
    assert json.loads(indexes.stdout)["indexCount"] == 3

    migration = run_helper(
        base / "postgres-migration-safety/scripts/audit_migration_sql.py",
        base / "postgres-migration-safety/assets/phased-migration.example.sql",
        "--json",
    )
    assert "findings" in json.loads(migration.stdout)

    drill = run_helper(
        base / "postgres-backup-recovery/scripts/build_recovery_drill.py",
        base / "postgres-backup-recovery/assets/recovery-profile.example.json",
    )
    assert "# Recovery drill" in drill.stdout
    assert "Generated worksheet only" in drill.stdout


def test_helpers_refuse_implicit_overwrite(tmp_path: Path) -> None:
    base = ROOT / "packs/shared/postgres-databases/skills"
    output = tmp_path / "queries.sql"
    renderer = base / "postgres-schema-review/scripts/render_review_queries.py"
    run_helper(renderer, "--section", "context", "--output", output)
    second = run_helper(renderer, "--section", "context", "--output", output, expected=2)
    assert "refusing to overwrite" in second.stderr

    drill_output = tmp_path / "drill.md"
    drill = base / "postgres-backup-recovery/scripts/build_recovery_drill.py"
    profile = base / "postgres-backup-recovery/assets/recovery-profile.example.json"
    run_helper(drill, profile, "--output", drill_output)
    second = run_helper(drill, profile, "--output", drill_output, expected=2)
    assert "refusing to overwrite" in second.stderr
