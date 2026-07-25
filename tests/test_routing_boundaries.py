from __future__ import annotations

import json
import shutil
from copy import deepcopy
from pathlib import Path

from skillpack_tools.evals import (
    validate_eval_file,
    validate_routing_boundaries,
)
from skillpack_tools.generate import build_generated_files
from skillpack_tools.models import discover_packs

ROOT = Path(__file__).resolve().parents[1]


def _boundary_fixture(tmp_path: Path, document: dict) -> Path:
    (tmp_path / "schemas").mkdir()
    (tmp_path / "evals").mkdir()
    shutil.copy2(
        ROOT / "schemas/routing-boundaries.schema.json",
        tmp_path / "schemas/routing-boundaries.schema.json",
    )
    (tmp_path / "evals/routing-boundaries.json").write_text(
        json.dumps(document, indent=2) + "\n",
        encoding="utf-8",
    )
    return tmp_path


def test_reviewed_boundary_graph_is_complete_and_four_way() -> None:
    errors, boundaries = validate_routing_boundaries(ROOT)
    assert errors == []
    assert len(boundaries) == 18
    assert sum(len(boundary.cases) for boundary in boundaries) == 72
    assert [boundary.skills for boundary in boundaries] == sorted(
        boundary.skills for boundary in boundaries
    )
    assert {
        outcome
        for boundary in boundaries
        for outcome in (case["outcome"] for case in boundary.cases)
    } == {"a-only", "b-only", "both", "neither"}
    public_skills = {
        skill
        for pack in discover_packs(ROOT)
        if pack.visibility == "public"
        for skill in pack.skills
    }
    participating = {skill for boundary in boundaries for skill in boundary.skills}
    assert public_skills <= participating

    legacy = json.loads(
        (ROOT / "tests/fixtures/routing-overlap-prompts-v1.json").read_text(encoding="utf-8")
    )["prompts"]
    current = [case["prompt"] for boundary in boundaries for case in boundary.cases]
    assert len(legacy) == len(set(legacy)) == 26
    assert set(legacy) <= set(current)
    assert len(set(current) - set(legacy)) == 46


def test_first_canary_release_blocker_boundaries_keep_exact_four_way_contracts() -> None:
    document = json.loads((ROOT / "evals/routing-boundaries.json").read_text(encoding="utf-8"))
    selected = {
        boundary["id"]: [
            (case["outcome"], case["prompt"], case["expectedSkills"]) for case in boundary["cases"]
        ]
        for boundary in document["boundaries"]
        if boundary["id"]
        in {
            "python-cli-error-output-vs-python-error-handling",
            "python-cli-testing-vs-python-test-architecture",
            "python-project-layout-vs-python-test-architecture",
        }
    }
    assert selected == {
        "python-cli-error-output-vs-python-error-handling": [
            (
                "a-only",
                "Review a Python command's messages, debug mode, stderr routing, and process "
                "exit status when exceptions occur.",
                ["python-cli-error-output"],
            ),
            (
                "b-only",
                "Refactor internal exceptions, context-manager cleanup, retries, and logging "
                "before any CLI mapping is considered.",
                ["python-error-handling"],
            ),
            (
                "both",
                "Define this Python library's exception taxonomy and translation boundaries, "
                "then map them to safe CLI diagnostics, traceback policy, streams, and exit "
                "statuses.",
                ["python-cli-error-output", "python-error-handling"],
            ),
            (
                "neither",
                "Review a static HTML color palette for accessibility without changing Python "
                "code or a command-line interface.",
                [],
            ),
        ],
        "python-cli-testing-vs-python-test-architecture": [
            (
                "a-only",
                "Create a comprehensive test matrix for command help, stdout, stderr, exit "
                "codes, stdin, and shell invocation.",
                ["python-cli-testing"],
            ),
            (
                "b-only",
                "Redesign fixture scopes, coverage goals, markers, and the full Python project's "
                "pull-request test selection.",
                ["python-test-architecture"],
            ),
            (
                "both",
                "Create the repository-wide Python test pyramid and CI selection policy, then "
                "add a focused matrix for CLI help, streams, exit codes, stdin, and shell "
                "invocation.",
                ["python-cli-testing", "python-test-architecture"],
            ),
            (
                "neither",
                "Run an already documented production smoke command and report its output "
                "without changing test design or test code.",
                [],
            ),
        ],
        "python-project-layout-vs-python-test-architecture": [
            (
                "a-only",
                "Review this Python repository's src layout, package discovery, editable-install "
                "isolation, namespace boundaries, and import behavior without redesigning its "
                "tests.",
                ["python-project-layout"],
            ),
            (
                "b-only",
                "Create a risk-based unit, integration, and end-to-end test plan for this "
                "existing Python package.",
                ["python-test-architecture"],
            ),
            (
                "both",
                "Move this Python project to an import-safe src layout and redesign unit, "
                "integration, and package-install tests around the new boundaries.",
                ["python-project-layout", "python-test-architecture"],
            ),
            (
                "neither",
                "Tune a PostgreSQL query plan from supplied execution evidence without touching "
                "the Python repository.",
                [],
            ),
        ],
    }


def test_boundary_validation_rejects_unknown_and_contradictory_selections(
    tmp_path: Path,
) -> None:
    canonical = json.loads((ROOT / "evals/routing-boundaries.json").read_text(encoding="utf-8"))
    invalid = deepcopy(canonical)
    boundary = invalid["boundaries"][0]
    boundary["skills"][0] = "unknown-skill"
    boundary["id"] = f"unknown-skill-vs-{boundary['skills'][1]}"
    for case, outcome in zip(
        boundary["cases"], ("a-only", "b-only", "both", "neither"), strict=True
    ):
        case["id"] = f"{boundary['id']}-{outcome}"
    boundary["cases"][0]["expectedSkills"] = ["unknown-skill"]
    boundary["cases"][2]["expectedSkills"][0] = "unknown-skill"
    root = _boundary_fixture(tmp_path, invalid)
    errors, _ = validate_routing_boundaries(root, packs=discover_packs(ROOT))
    assert "unknown skills" in "\n".join(errors)

    contradictory = deepcopy(canonical)
    contradictory["boundaries"][0]["cases"][0]["expectedSkills"] = [
        "genaptic-skillsets-create-skillpack"
    ]
    (root / "evals/routing-boundaries.json").write_text(json.dumps(contradictory), encoding="utf-8")
    errors, _ = validate_routing_boundaries(root, packs=discover_packs(ROOT))
    assert "expectedSkills must be" in "\n".join(errors)


def test_boundary_validation_rejects_duplicate_relationships_and_public_orphans(
    tmp_path: Path,
) -> None:
    canonical = json.loads((ROOT / "evals/routing-boundaries.json").read_text(encoding="utf-8"))
    invalid = deepcopy(canonical)
    duplicate = deepcopy(invalid["boundaries"][0])
    rust_cli_index = next(
        index
        for index, boundary in enumerate(invalid["boundaries"])
        if boundary["id"].startswith("rust-cli-application-design-vs-")
    )
    invalid["boundaries"][rust_cli_index] = duplicate
    invalid["boundaries"].sort(key=lambda boundary: boundary["skills"])
    root = _boundary_fixture(tmp_path, invalid)
    errors, _ = validate_routing_boundaries(root, packs=discover_packs(ROOT))
    combined = "\n".join(errors)
    assert "duplicate unordered boundary pair" in combined
    assert "public skills without a reviewed boundary" in combined
    assert "rust-cli-application-design" in combined


def test_per_skill_eval_schema_rejects_legacy_overlap_relationship(tmp_path: Path) -> None:
    source = ROOT / "packs/python/best-practices/skills/python-project-layout/evals/evals.json"
    data = json.loads(source.read_text(encoding="utf-8"))
    legacy = deepcopy(data["routing"][-1])
    legacy.update(
        {
            "id": "legacy-overlap",
            "kind": "overlap",
            "preferredSkill": "python-test-architecture",
        }
    )
    data["routing"].append(legacy)
    skill_dir = tmp_path / "skills/python-project-layout/evals"
    skill_dir.mkdir(parents=True)
    path = skill_dir / "evals.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    errors, summary = validate_eval_file(ROOT, path)
    assert summary is None
    assert "'overlap' is not one of" in "\n".join(errors)


def test_evals_document_contains_deterministic_generated_matrix() -> None:
    errors, boundaries = validate_routing_boundaries(ROOT)
    assert errors == []
    document = build_generated_files(ROOT)["docs/evals.md"]
    assert isinstance(document, str)
    assert document.count("<!-- BEGIN GENERATED ROUTING BOUNDARY MATRIX -->") == 1
    assert document.count("<!-- END GENERATED ROUTING BOUNDARY MATRIX -->") == 1
    for boundary in boundaries:
        assert document.count(f"`{boundary.id}`") == 1
