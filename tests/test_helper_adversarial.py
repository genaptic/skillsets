from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = {
    "audit-exceptions": ROOT
    / "packs/python/best-practices/skills/python-error-handling/scripts"
    / "audit_exception_handlers.py",
    "inspect-layout": ROOT
    / "packs/python/best-practices/skills/python-project-layout/scripts"
    / "inspect_layout.py",
    "inventory-tests": ROOT
    / "packs/python/best-practices/skills/python-testing-strategy/scripts"
    / "inventory_tests.py",
    "validate-command-spec": ROOT
    / "packs/python/cli-apps/skills/python-cli-command-design/scripts"
    / "validate_command_spec.py",
    "check-cli-contract": ROOT
    / "packs/python/cli-apps/skills/python-cli-error-output/scripts"
    / "check_cli_contract.py",
    "generate-cli-matrix": ROOT
    / "packs/python/cli-apps/skills/python-cli-testing/scripts"
    / "generate_cli_test_matrix.py",
    "build-recovery-drill": ROOT
    / "packs/shared/postgres-databases/skills/postgres-backup-recovery/scripts"
    / "build_recovery_drill.py",
    "review-index-inventory": ROOT
    / "packs/shared/postgres-databases/skills/postgres-index-design/scripts"
    / "review_index_inventory.py",
    "audit-migration-sql": ROOT
    / "packs/shared/postgres-databases/skills/postgres-migration-safety/scripts"
    / "audit_migration_sql.py",
    "summarize-explain": ROOT
    / "packs/shared/postgres-databases/skills/postgres-query-performance-review/scripts"
    / "summarize_explain_json.py",
    "audit-schema-sql": ROOT
    / "packs/shared/postgres-databases/skills/postgres-schema-design/scripts"
    / "audit_schema_sql.py",
    "render-review-queries": ROOT
    / "packs/shared/postgres-databases/skills/postgres-schema-review/scripts"
    / "render_review_queries.py",
}


def run_helper(
    name: str,
    *arguments: str | Path,
    cwd: Path,
    input_text: str | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-I", "-S", str(SCRIPTS[name]), *map(str, arguments)],
        cwd=cwd,
        input=input_text,
        text=True,
        capture_output=True,
        check=False,
        timeout=10,
    )


def write_json(path: Path, value: object) -> Path:
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def assert_safe_failure(completed: subprocess.CompletedProcess[str], expected: int) -> None:
    assert completed.returncode == expected, completed
    assert "Traceback" not in completed.stdout
    assert "Traceback" not in completed.stderr


def command_spec(payload: str = "Run the command safely.") -> dict[str, object]:
    return {
        "program": "example",
        "configurationPrecedence": [
            "command-line",
            "environment",
            "configuration-file",
            "default",
        ],
        "globalOptions": [],
        "commands": [
            {
                "name": "run",
                "summary": payload,
                "options": [],
                "arguments": [],
            }
        ],
    }


def cli_contract(argv: list[str]) -> dict[str, object]:
    return {
        "schemaVersion": 1,
        "scenarios": [
            {
                "id": "adversarial-command",
                "argv": argv,
                "expectedExit": 0,
                "stdout": {"mode": "any"},
                "stderr": {"mode": "any"},
                "timeoutSeconds": 1,
            }
        ],
    }


def matrix_surface(payload: str = "Check the successful path.") -> dict[str, object]:
    return {
        "schemaVersion": 1,
        "program": "example",
        "dimensions": {"platform": ["linux"]},
        "requiredScenarios": [
            {"id": "success", "purpose": payload, "assert": ["exit status is zero"]}
        ],
    }


def make_layout(path: Path, package_source: str = "") -> Path:
    path.mkdir()
    (path / "pyproject.toml").write_text(
        "[build-system]\n"
        "requires = []\n"
        'build-backend = "example.backend"\n\n'
        "[project]\n"
        'name = "example"\n'
        'requires-python = ">=3.11"\n',
        encoding="utf-8",
    )
    package = path / "src" / "example"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text(package_source, encoding="utf-8")
    return path


@pytest.mark.parametrize("name", sorted(SCRIPTS))
def test_helper_help_discloses_prerequisites_and_effects(name: str, tmp_path: Path) -> None:
    completed = run_helper(name, "--help", cwd=tmp_path)
    assert completed.returncode == 0, completed.stderr
    help_text = " ".join(completed.stdout.split())
    assert "Python 3.11" in help_text
    assert "standard library" in help_text
    assert "network" in help_text
    assert "stdout" in help_text
    assert "external command" in help_text or "external program" in help_text


def test_exception_auditor_valid_invalid_and_nonexecuting(tmp_path: Path) -> None:
    valid = tmp_path / "valid.py"
    valid.write_text("def parse(value: str) -> int:\n    return int(value)\n", encoding="utf-8")
    completed = run_helper("audit-exceptions", valid, "--json", cwd=tmp_path)
    assert completed.returncode == 0
    assert json.loads(completed.stdout)["parseErrors"] == []

    invalid = tmp_path / "invalid.py"
    invalid.write_text("def broken(:\n", encoding="utf-8")
    completed = run_helper("audit-exceptions", invalid, "--json", cwd=tmp_path)
    assert_safe_failure(completed, 2)

    marker = tmp_path / "must-not-exist"
    payload = tmp_path / "payload.py"
    payload.write_text(
        "from pathlib import Path\n"
        f"Path({str(marker)!r}).write_text('executed', encoding='utf-8')\n",
        encoding="utf-8",
    )
    completed = run_helper("audit-exceptions", payload, "--json", cwd=tmp_path)
    assert completed.returncode == 0
    assert not marker.exists()


def test_layout_inspector_valid_invalid_and_nonimporting(tmp_path: Path) -> None:
    valid = make_layout(tmp_path / "valid-layout")
    completed = run_helper("inspect-layout", valid, "--json", cwd=tmp_path)
    assert completed.returncode == 0
    assert json.loads(completed.stdout)["layout"] == "src"

    invalid = tmp_path / "invalid-layout"
    invalid.mkdir()
    (invalid / "pyproject.toml").write_text("[project\n", encoding="utf-8")
    completed = run_helper("inspect-layout", invalid, "--json", cwd=tmp_path)
    assert_safe_failure(completed, 1)

    marker = tmp_path / "must-not-exist"
    payload = make_layout(
        tmp_path / "payload-layout",
        f"from pathlib import Path\nPath({str(marker)!r}).write_text('executed')\n",
    )
    completed = run_helper("inspect-layout", payload, "--json", cwd=tmp_path)
    assert completed.returncode == 0
    assert not marker.exists()


def test_test_inventory_valid_invalid_and_nonimporting(tmp_path: Path) -> None:
    valid = tmp_path / "valid-tests"
    valid.mkdir()
    (valid / "test_ok.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")
    completed = run_helper("inventory-tests", valid, "--json", cwd=tmp_path)
    assert completed.returncode == 0
    assert json.loads(completed.stdout)["totals"]["tests"] == 1

    invalid = tmp_path / "invalid-tests"
    invalid.mkdir()
    (invalid / "test_broken.py").write_text("def test_broken(:\n", encoding="utf-8")
    completed = run_helper("inventory-tests", invalid, "--json", cwd=tmp_path)
    assert_safe_failure(completed, 1)

    marker = tmp_path / "must-not-exist"
    adversarial = tmp_path / "adversarial-tests"
    adversarial.mkdir()
    (adversarial / "test_payload.py").write_text(
        "from pathlib import Path\n"
        f"Path({str(marker)!r}).write_text('executed')\n"
        "def test_safe():\n    assert True\n",
        encoding="utf-8",
    )
    completed = run_helper("inventory-tests", adversarial, "--json", cwd=tmp_path)
    assert completed.returncode == 0
    assert not marker.exists()


def test_command_spec_validator_valid_invalid_and_nonexecuting(tmp_path: Path) -> None:
    valid = write_json(tmp_path / "valid.json", command_spec())
    completed = run_helper("validate-command-spec", valid, "--json", cwd=tmp_path)
    assert completed.returncode == 0
    assert json.loads(completed.stdout)["valid"] is True

    invalid = write_json(tmp_path / "invalid.json", {})
    completed = run_helper("validate-command-spec", invalid, "--json", cwd=tmp_path)
    assert_safe_failure(completed, 1)

    marker = tmp_path / "must-not-exist"
    payload = f"$(touch {marker}); `touch {marker}`"
    adversarial = write_json(tmp_path / "adversarial.json", command_spec(payload))
    completed = run_helper("validate-command-spec", adversarial, "--json", cwd=tmp_path)
    assert completed.returncode == 0
    assert not marker.exists()


def test_cli_contract_valid_invalid_and_confirmation_boundary(tmp_path: Path) -> None:
    valid = write_json(tmp_path / "valid.json", cli_contract(["not-executed"]))
    completed = run_helper("check-cli-contract", valid, "--json", cwd=tmp_path)
    assert completed.returncode == 0
    assert json.loads(completed.stdout)["executed"] is False

    invalid = write_json(tmp_path / "invalid.json", {})
    completed = run_helper("check-cli-contract", invalid, "--json", cwd=tmp_path)
    assert_safe_failure(completed, 2)

    marker = tmp_path / "must-not-exist"
    code = f"from pathlib import Path; Path({str(marker)!r}).write_text('executed')"
    adversarial = write_json(
        tmp_path / "adversarial.json", cli_contract([sys.executable, "-c", code])
    )
    completed = run_helper("check-cli-contract", adversarial, "--json", cwd=tmp_path)
    assert completed.returncode == 0
    assert json.loads(completed.stdout)["executed"] is False
    assert not marker.exists()

    completed = run_helper(
        "check-cli-contract",
        adversarial,
        "--confirm-execute",
        "--scenario",
        "unknown",
        cwd=tmp_path,
    )
    assert_safe_failure(completed, 2)
    assert not marker.exists()


def test_matrix_generator_valid_invalid_and_safe_output(tmp_path: Path) -> None:
    valid = write_json(tmp_path / "valid.json", matrix_surface())
    completed = run_helper("generate-cli-matrix", valid, "--format", "json", cwd=tmp_path)
    assert completed.returncode == 0
    assert json.loads(completed.stdout)["cases"]

    invalid = write_json(tmp_path / "invalid.json", {})
    completed = run_helper("generate-cli-matrix", invalid, cwd=tmp_path)
    assert_safe_failure(completed, 2)

    marker = tmp_path / "must-not-exist"
    payload = f"$(touch {marker}) | `touch {marker}`"
    adversarial = write_json(tmp_path / "adversarial.json", matrix_surface(payload))
    completed = run_helper("generate-cli-matrix", adversarial, cwd=tmp_path)
    assert completed.returncode == 0
    assert payload in completed.stdout
    assert not marker.exists()

    output = tmp_path / "existing.md"
    output.write_text("sentinel\n", encoding="utf-8")
    completed = run_helper("generate-cli-matrix", adversarial, "--output", output, cwd=tmp_path)
    assert_safe_failure(completed, 2)
    assert output.read_text(encoding="utf-8") == "sentinel\n"


def test_recovery_drill_valid_invalid_and_safe_output(tmp_path: Path) -> None:
    fixture = (
        ROOT
        / "packs/shared/postgres-databases/skills/postgres-backup-recovery/assets"
        / "recovery-profile.example.json"
    )
    completed = run_helper("build-recovery-drill", fixture, cwd=tmp_path)
    assert completed.returncode == 0
    assert "Generated worksheet only" in completed.stdout

    invalid = write_json(tmp_path / "invalid.json", {})
    completed = run_helper("build-recovery-drill", invalid, cwd=tmp_path)
    assert_safe_failure(completed, 2)

    marker = tmp_path / "must-not-exist"
    profile = json.loads(fixture.read_text(encoding="utf-8"))
    payload = f"$(touch {marker}); COPY data FROM PROGRAM 'touch {marker}'"
    profile["scenario"]["description"] = payload
    adversarial = write_json(tmp_path / "adversarial.json", profile)
    completed = run_helper("build-recovery-drill", adversarial, cwd=tmp_path)
    assert completed.returncode == 0
    assert payload in completed.stdout
    assert not marker.exists()

    output = tmp_path / "existing.md"
    output.write_text("sentinel\n", encoding="utf-8")
    completed = run_helper("build-recovery-drill", adversarial, "--output", output, cwd=tmp_path)
    assert_safe_failure(completed, 2)
    assert output.read_text(encoding="utf-8") == "sentinel\n"


def test_index_reviewer_valid_invalid_and_nonexecuting(tmp_path: Path) -> None:
    fixture = (
        ROOT
        / "packs/shared/postgres-databases/skills/postgres-index-design/assets"
        / "index-inventory.example.json"
    )
    completed = run_helper("review-index-inventory", fixture, "--json", cwd=tmp_path)
    assert completed.returncode == 0
    assert json.loads(completed.stdout)["indexCount"] == 3

    invalid = write_json(tmp_path / "invalid.json", {})
    completed = run_helper("review-index-inventory", invalid, "--json", cwd=tmp_path)
    assert_safe_failure(completed, 2)

    marker = tmp_path / "must-not-exist"
    inventory = json.loads(fixture.read_text(encoding="utf-8"))
    inventory["indexes"][0]["name"] = f"$(touch {marker})"
    adversarial = write_json(tmp_path / "adversarial.json", inventory)
    completed = run_helper("review-index-inventory", adversarial, "--json", cwd=tmp_path)
    assert completed.returncode == 0
    assert not marker.exists()


def test_migration_auditor_valid_invalid_and_never_executes_sql(tmp_path: Path) -> None:
    valid = tmp_path / "valid.sql"
    valid.write_text("SELECT 1;\n", encoding="utf-8")
    completed = run_helper("audit-migration-sql", valid, "--json", cwd=tmp_path)
    assert completed.returncode == 0

    completed = run_helper("audit-migration-sql", tmp_path / "missing.sql", "--json", cwd=tmp_path)
    assert_safe_failure(completed, 2)

    marker = tmp_path / "must-not-exist"
    adversarial = tmp_path / "adversarial.sql"
    adversarial.write_text(
        f"COPY app.items FROM PROGRAM 'touch {marker}';\n"
        f"\\! touch {marker}\n"
        "SELECT pg_sleep(30);\n",
        encoding="utf-8",
    )
    completed = run_helper("audit-migration-sql", adversarial, "--json", cwd=tmp_path)
    assert completed.returncode == 0
    assert not marker.exists()


def test_explain_summarizer_valid_invalid_and_nonexecuting(tmp_path: Path) -> None:
    valid = write_json(tmp_path / "valid.json", [{"Plan": {"Node Type": "Result", "Plan Rows": 1}}])
    completed = run_helper("summarize-explain", valid, "--json", cwd=tmp_path)
    assert completed.returncode == 0
    assert json.loads(completed.stdout)["nodeCount"] == 1

    invalid = write_json(tmp_path / "invalid.json", {})
    completed = run_helper("summarize-explain", invalid, "--json", cwd=tmp_path)
    assert_safe_failure(completed, 2)

    marker = tmp_path / "must-not-exist"
    payload = f"Seq Scan; $(touch {marker}); COPY FROM PROGRAM 'touch {marker}'"
    adversarial = write_json(
        tmp_path / "adversarial.json",
        [{"Plan": {"Node Type": payload, "Relation Name": payload, "Plan Rows": 1}}],
    )
    completed = run_helper("summarize-explain", adversarial, "--json", cwd=tmp_path)
    assert completed.returncode == 0
    assert payload in completed.stdout
    assert not marker.exists()


def test_schema_auditor_valid_invalid_and_never_executes_sql(tmp_path: Path) -> None:
    valid = tmp_path / "valid.sql"
    valid.write_text("CREATE TABLE app.items (id bigint PRIMARY KEY);\n", encoding="utf-8")
    completed = run_helper("audit-schema-sql", valid, "--json", cwd=tmp_path)
    assert completed.returncode == 0

    completed = run_helper("audit-schema-sql", tmp_path / "missing.sql", "--json", cwd=tmp_path)
    assert_safe_failure(completed, 2)

    marker = tmp_path / "must-not-exist"
    adversarial = tmp_path / "adversarial.sql"
    adversarial.write_text(
        f"COPY app.items FROM PROGRAM 'touch {marker}';\n"
        f"DO $$ BEGIN PERFORM pg_sleep(30); END $$; -- $(touch {marker})\n",
        encoding="utf-8",
    )
    completed = run_helper("audit-schema-sql", adversarial, "--json", cwd=tmp_path)
    assert completed.returncode == 0
    assert not marker.exists()


def test_query_renderer_valid_invalid_and_injection_safe(tmp_path: Path) -> None:
    completed = run_helper("render-review-queries", "--section", "context", cwd=tmp_path)
    assert completed.returncode == 0
    assert "BEGIN TRANSACTION READ ONLY" in completed.stdout

    completed = run_helper("render-review-queries", "--statement-timeout", "0s", cwd=tmp_path)
    assert_safe_failure(completed, 2)

    output = tmp_path / "existing.sql"
    output.write_text("sentinel\n", encoding="utf-8")
    completed = run_helper(
        "render-review-queries",
        "--statement-timeout",
        "5s; SELECT pg_sleep(30); --",
        "--output",
        output,
        cwd=tmp_path,
    )
    assert_safe_failure(completed, 2)
    assert completed.stdout == ""
    assert output.read_text(encoding="utf-8") == "sentinel\n"
