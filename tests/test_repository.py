from __future__ import annotations

import hashlib
import json
from pathlib import Path

from skillpack_tools.evals import eval_report, run_structural_evals
from skillpack_tools.generate import apply_generated_files
from skillpack_tools.models import discover_packs, load_repository
from skillpack_tools.util import parse_skill_markdown
from skillpack_tools.validate import validate_repository

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_PACKS = {
    "python-best-practices": [
        "python-project-layout",
        "python-testing-strategy",
        "python-error-handling",
    ],
    "python-cli-apps": [
        "python-cli-command-design",
        "python-cli-error-output",
        "python-cli-testing",
    ],
    "postgres-databases": [
        "postgres-schema-design",
        "postgres-schema-review",
        "postgres-query-performance-review",
        "postgres-index-design",
        "postgres-migration-safety",
        "postgres-backup-recovery",
    ],
    "repository-development": [
        "create-new-skill",
        "create-new-skillset",
    ],
    "rust-best-practices": [
        "rust-core-best-practices",
        "rust-project-architecture",
        "rust-code-structure",
        "rust-abstraction-design",
        "rust-async-concurrency",
        "rust-networking",
        "rust-testing-strategy",
        "rust-dependency-portability",
        "rust-workspace-documentation",
        "rustdoc-maintenance",
    ],
    "rust-cli-apps": [
        "rust-cli-application-design",
        "rust-cli-command-development",
    ],
}


def test_repository_identity_model() -> None:
    config = load_repository(ROOT)
    assert config.project_name == "Genaptic Skillsets"
    assert config.slug == "genaptic/skillsets"
    assert config.default_branch == "main"
    assert config.publisher_name == "Genaptic"
    assert config.copyright_owner == "Genaptic"
    assert config.maintainer_name == "Connor Sanders"
    assert config.maintainer_github == "jecsand838"
    assert config.security_channel == "github-private-vulnerability-reporting"
    assert config.security_email is None
    assert config.security_url == ("https://github.com/genaptic/skillsets/security/advisories/new")
    assert config.marketplace_name == "genaptic-skillsets"
    assert config.license == "Apache-2.0"


def test_pack_and_skill_inventory_is_exact() -> None:
    packs = discover_packs(ROOT)
    assert {pack.id: pack.skills for pack in packs} == EXPECTED_PACKS
    names = [skill for pack in packs for skill in pack.skills]
    assert len(names) == 26
    assert len(names) == len(set(names))


def test_every_skill_has_portable_routing_frontmatter() -> None:
    for pack in discover_packs(ROOT):
        for skill in pack.skills:
            path = pack.path / "skills" / skill / "SKILL.md"
            metadata, body = parse_skill_markdown(path)
            assert metadata["name"] == skill
            assert metadata["license"] == "Apache-2.0"
            assert metadata["metadata"]["skillpack"] == pack.id
            assert all(isinstance(value, str) for value in metadata["metadata"].values())
            assert "Use when" in metadata["description"]
            assert "Do not use" in metadata["description"]
            assert "## Verification" in body
            assert "## Output contract" in body


def test_structural_eval_totals() -> None:
    report = eval_report(run_structural_evals(ROOT))
    assert report["totals"] == {
        "skills": 26,
        "routingCases": 182,
        "behaviorCases": 52,
    }


def test_repository_validation_and_generated_state() -> None:
    result = validate_repository(ROOT, check_generated=True)
    assert result.ok, result.errors
    assert result.warnings == []
    assert apply_generated_files(ROOT, check=True) == []


def test_generated_hash_manifest_matches_files() -> None:
    manifest = json.loads((ROOT / "dist" / "generated-files.json").read_text(encoding="utf-8"))
    assert manifest["schemaVersion"] == 1
    entries = manifest["files"]
    assert entries == sorted(entries, key=lambda item: item["path"])
    assert len(entries) > 100
    for item in entries:
        path = ROOT / item["path"]
        assert path.is_file(), item["path"]
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        assert digest == item["sha256"], item["path"]


def test_marketplaces_and_catalog_cover_every_pack() -> None:
    catalog = json.loads((ROOT / "catalog.json").read_text(encoding="utf-8"))
    claude = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
    codex = json.loads(
        (ROOT / ".agents" / "plugins" / "marketplace.json").read_text(encoding="utf-8")
    )
    expected = set(EXPECTED_PACKS)
    assert {item["id"] for item in catalog["packs"]} == expected
    assert all(
        item["publication"] == {"state": "unpublished", "sourceType": "repo-local"}
        for item in catalog["packs"]
    )
    assert {item["name"] for item in claude["plugins"]} == expected
    assert {item["name"] for item in codex["plugins"]} == expected
    for pack in discover_packs(ROOT):
        index = ROOT / "dist" / "opencode" / pack.language / pack.subject / "index.json"
        data = json.loads(index.read_text(encoding="utf-8"))
        assert [item["name"] for item in data["skills"]] == pack.skills
