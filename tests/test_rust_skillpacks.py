from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
RUST_ROOT = ROOT / "packs/rust"
pytestmark = pytest.mark.rust_repository_contract

PACKS = {
    RUST_ROOT / "best-practices": {
        "id": "rust-best-practices",
        "display-name": "Rust Best Practices",
        "subject": "best-practices",
        "skills": [
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
    },
    RUST_ROOT / "cli-apps": {
        "id": "rust-cli-apps",
        "display-name": "Rust CLI Applications",
        "subject": "cli-apps",
        "skills": [
            "rust-cli-application-design",
            "rust-cli-command-development",
        ],
    },
}

OPENAI_INTERFACES = {
    "rust-core-best-practices": (
        "Rust Core Best Practices",
        "Review Rust changes against repository policy",
    ),
    "rust-project-architecture": (
        "Rust Project Architecture",
        "Design Rust crates, modules, and workspaces",
    ),
    "rust-code-structure": (
        "Rust Code Structure",
        "Structure Rust types, state, and owned behavior",
    ),
    "rust-abstraction-design": (
        "Rust Abstraction Design",
        "Choose clear Rust traits, generics, and errors",
    ),
    "rust-async-concurrency": (
        "Rust Async and Concurrency",
        "Design bounded, cancellable async Rust systems",
    ),
    "rust-networking": (
        "Rust Networking",
        "Design safe Rust network clients and pools",
    ),
    "rust-testing-strategy": (
        "Rust Testing Strategy",
        "Plan reliable Rust tests across all boundaries",
    ),
    "rust-dependency-portability": (
        "Rust Dependency Portability",
        "Review Cargo dependencies, MSRV, and platforms",
    ),
    "rust-workspace-documentation": (
        "Rust Workspace Documentation",
        "Reconcile Rust workspace and agent documentation",
    ),
    "rustdoc-maintenance": (
        "Rustdoc Maintenance",
        "Refresh public Rust API docs and doctests",
    ),
    "rust-cli-application-design": (
        "Rust CLI Application Design",
        "Design portable, stable Rust CLI applications",
    ),
    "rust-cli-command-development": (
        "Rust CLI Command Development",
        "Add or change commands in an existing Rust CLI",
    ),
}

SCAFFOLD_TEXT = (
    "Describe a realistic prompt",
    "Add another realistic implicit request",
    "While reviewing this artifact",
    "Request a plausible neighboring task",
    "Request another near-match",
    "Perform a focused case",
    "Complete an end-to-end realistic case",
)

REFERENCE_PRESERVATION_LEDGER = {
    "dependencies-and-platforms.md": (
        "best-practices/skills/rust-dependency-portability/references/guide.md",
        "best-practices/skills/rust-dependency-portability/references/cargo-policy.md",
        "best-practices/skills/rust-dependency-portability/references/platform-portability.md",
    ),
    "structs-enums-receiver-methods.md": (
        "best-practices/skills/rust-code-structure/references/guide.md",
        "best-practices/skills/rust-code-structure/references/type-model-examples.md",
    ),
    "agentic-documentation/examples.md": (
        "best-practices/skills/rust-workspace-documentation/references/examples.md",
    ),
    "agentic-documentation/routing.md": (
        "best-practices/skills/rust-workspace-documentation/references/document-roles.md",
    ),
    "agentic-documentation/workflow.md": (
        "best-practices/skills/rust-workspace-documentation/references/guide.md",
    ),
    "rustdocs/examples.md": ("best-practices/skills/rustdoc-maintenance/references/examples.md",),
    "rustdocs/routing.md": (
        "best-practices/skills/rustdoc-maintenance/references/documentation-contracts.md",
    ),
    "rustdocs/workflow.md": ("best-practices/skills/rustdoc-maintenance/references/guide.md",),
    "async.md": (
        "best-practices/skills/rust-async-concurrency/references/guide.md",
        "best-practices/skills/rust-async-concurrency/references/tokio-patterns.md",
        "best-practices/skills/rust-async-concurrency/references/sync-worker-bridge.md",
    ),
    "testing.md": (
        "best-practices/skills/rust-testing-strategy/references/guide.md",
        "best-practices/skills/rust-testing-strategy/references/async-live-tests.md",
    ),
    "cli/official-guides-and-crates.md": (
        "cli-apps/skills/rust-cli-application-design/references/sources.md",
    ),
    "cli/bad-patterns.md": (
        "cli-apps/skills/rust-cli-application-design/references/architecture.md",
        "cli-apps/skills/rust-cli-application-design/references/filesystem-output-safety.md",
    ),
    "cli/full-crud-cli-example.md": (
        "cli-apps/skills/rust-cli-application-design/references/architecture.md",
        "cli-apps/skills/rust-cli-application-design/references/grammar.md",
        "cli-apps/skills/rust-cli-application-design/references/filesystem-output-safety.md",
        "cli-apps/skills/rust-cli-application-design/references/testing.md",
        "cli-apps/skills/rust-cli-application-design/references/end-to-end-example.md",
    ),
    "abstractions.md": ("best-practices/skills/rust-abstraction-design/references/guide.md",),
    "enum-dispatch-trait-pattern.md": (
        "best-practices/skills/rust-abstraction-design/references/enum-dispatch.md",
    ),
    "core-checklist.md": (
        "best-practices/skills/rust-core-best-practices/references/checklist.md",
    ),
    "command/official-guides-and-crates.md": (
        "cli-apps/skills/rust-cli-command-development/references/sources.md",
    ),
    "command/command-addition-playbook.md": (
        "cli-apps/skills/rust-cli-command-development/references/guide.md",
        "cli-apps/skills/rust-cli-command-development/references/parser-dispatch.md",
        "cli-apps/skills/rust-cli-command-development/references/filesystem-transactions.md",
    ),
    "command/examples-good-and-bad-command-diffs.md": (
        "cli-apps/skills/rust-cli-command-development/references/command-diff-shapes.md",
    ),
    "architecture.md": ("best-practices/skills/rust-project-architecture/references/guide.md",),
    "networking.md": (
        "best-practices/skills/rust-networking/references/guide.md",
        "best-practices/skills/rust-networking/references/http-reliability.md",
        "best-practices/skills/rust-networking/references/grpc-database.md",
    ),
}

ASSET_PRESERVATION_LEDGER = {
    "member_with_workspace_lints.toml": "best-practices/skills/rust-dependency-portability/assets/templates/member_with_workspace_lints.toml",
    "target_specific_deps.toml": "best-practices/skills/rust-dependency-portability/assets/templates/target_specific_deps.toml",
    "project_dirs.rs": "best-practices/skills/rust-dependency-portability/assets/templates/project_dirs.rs",
    "graceful_shutdown.rs": "best-practices/skills/rust-async-concurrency/assets/templates/graceful_shutdown.rs",
    "sync_worker_bridge.rs": "best-practices/skills/rust-async-concurrency/assets/templates/sync_worker_bridge.rs",
    "localset_spawn_local.rs": "best-practices/skills/rust-async-concurrency/assets/templates/localset_spawn_local.rs",
    "bounded_fanout.rs": "best-practices/skills/rust-async-concurrency/assets/templates/bounded_fanout.rs",
    "bin_smoke_test.rs": "best-practices/skills/rust-testing-strategy/assets/templates/bin_smoke_test.rs",
    "doctest_examples.rs": "best-practices/skills/rust-testing-strategy/assets/templates/doctest_examples.rs",
    "unit_test_with_fake.rs": "best-practices/skills/rust-testing-strategy/assets/templates/unit_test_with_fake.rs",
    "enum_dispatch.rs": "best-practices/skills/rust-abstraction-design/assets/templates/enum_dispatch.rs",
    "typed_error.rs": "best-practices/skills/rust-abstraction-design/assets/templates/typed_error.rs",
    "baseline-package/Cargo.toml": "best-practices/skills/rust-core-best-practices/assets/templates/baseline-package/Cargo.toml",
    "member-Cargo.toml": "best-practices/skills/rust-core-best-practices/assets/templates/member-Cargo.toml",
    "thin-lib-bin/src/lib.rs": "best-practices/skills/rust-project-architecture/assets/templates/thin-lib-bin/src/lib.rs",
    "thin-lib-bin/src/main.rs": "best-practices/skills/rust-project-architecture/assets/templates/thin-lib-bin/src/main.rs",
    "workspace-root/Cargo.toml": "best-practices/skills/rust-project-architecture/assets/templates/workspace-root/Cargo.toml",
    "typed_http_client.rs": "best-practices/skills/rust-networking/assets/templates/typed_http_client.rs",
    "grpc_client.rs": "best-practices/skills/rust-networking/assets/templates/grpc_client.rs",
    "sqlx_pool.rs": "best-practices/skills/rust-networking/assets/templates/sqlx_pool.rs",
}


def _skill_directories() -> list[Path]:
    return sorted(RUST_ROOT.glob("*/skills/*"))


def test_archive_reference_and_asset_concepts_have_a_complete_preservation_ledger() -> None:
    assert len(REFERENCE_PRESERVATION_LEDGER) == 21
    assert len(ASSET_PRESERVATION_LEDGER) == 20
    for source, destinations in REFERENCE_PRESERVATION_LEDGER.items():
        assert destinations, source
        for destination in destinations:
            path = RUST_ROOT / destination
            assert path.is_file(), f"{source} -> {destination}"
            assert path.stat().st_size > 0
    for source, destination in ASSET_PRESERVATION_LEDGER.items():
        path = RUST_ROOT / destination
        assert path.is_file(), f"{source} -> {destination}"
        assert path.stat().st_size > 0


def test_rust_pack_manifests_have_exact_public_contracts() -> None:
    for pack_path, expected in PACKS.items():
        manifest = yaml.safe_load((pack_path / "skillpack.yaml").read_text(encoding="utf-8"))
        assert manifest["id"] == expected["id"]
        assert manifest["display-name"] == expected["display-name"]
        assert manifest["language"] == "rust"
        assert manifest["subject"] == expected["subject"]
        assert manifest["version"] == "1.0.0"
        assert manifest["license"] == "Apache-2.0"
        assert manifest["maintainers"] == [{"github": "jecsand838"}]
        assert manifest["skills"] == expected["skills"]
        assert manifest["targets"] == ["claude-code", "codex", "opencode"]
        assert manifest["category"] == "Developer Tools"
        assert "source-sha" not in manifest
        assert set(manifest["compatibility"]["runtimes"]) == {"cargo", "rust"}
        assert manifest["operations"] == {
            "network": "optional",
            "filesystem": "project-write",
            "command-execution": "optional-explicit",
            "external-writes": "none",
        }


def test_rust_openai_interfaces_are_exact_and_minimal() -> None:
    skill_dirs = _skill_directories()
    assert sorted(path.name for path in skill_dirs) == sorted(OPENAI_INTERFACES)
    for skill_dir in skill_dirs:
        data = yaml.safe_load((skill_dir / "agents/openai.yaml").read_text(encoding="utf-8"))
        assert set(data) == {"interface"}
        assert set(data["interface"]) == {
            "display_name",
            "short_description",
            "default_prompt",
        }
        display, summary = OPENAI_INTERFACES[skill_dir.name]
        assert data["interface"]["display_name"] == display
        assert data["interface"]["short_description"] == summary
        assert data["interface"]["default_prompt"].startswith(f"Use ${skill_dir.name} ")


def test_rust_skills_use_the_standard_operational_sections() -> None:
    required = (
        "## Outcome",
        "## Compatibility",
        "## Inputs",
        "## Safety",
        "## Procedure",
        "## Verification",
        "## Output contract",
        "## Resources",
    )
    for skill_dir in _skill_directories():
        text = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
        positions = [text.index(heading) for heading in required]
        assert positions == sorted(positions), skill_dir


def test_rust_evals_have_exact_case_shapes_and_no_scaffold_text() -> None:
    for skill_dir in _skill_directories():
        evals = json.loads((skill_dir / "evals/evals.json").read_text(encoding="utf-8"))
        assert evals["skill"] == skill_dir.name
        assert len(evals["routing"]) == 6
        assert [case["kind"] for case in evals["routing"]].count("explicit-positive") == 1
        assert [case["kind"] for case in evals["routing"]].count("implicit-positive") == 2
        assert [case["kind"] for case in evals["routing"]].count("contextual-positive") == 1
        assert [case["kind"] for case in evals["routing"]].count("negative") == 2
        assert [case["kind"] for case in evals["routing"]].count("overlap") == 0
        assert [case["kind"] for case in evals["behavior"]] == ["focused", "end-to-end"]
        serialized = json.dumps(evals)
        assert not any(placeholder in serialized for placeholder in SCAFFOLD_TEXT)


def test_rust_resources_are_shallow_linked_and_not_boilerplate() -> None:
    for skill_dir in _skill_directories():
        skill_text = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
        guide_text = (skill_dir / "references/guide.md").read_text(encoding="utf-8")
        for required in ("guide.md", "checklist.md", "sources.md"):
            path = skill_dir / "references" / required
            assert path.is_file(), path
            assert f"references/{required}" in skill_text

        for resource in sorted((skill_dir / "references").glob("*.md")):
            lines = resource.read_text(encoding="utf-8").splitlines()
            if len(lines) > 100:
                assert "## Contents" in lines, resource

        linked_text = f"{skill_text}\n{guide_text}"
        for asset in sorted((skill_dir / "assets").glob("**/*")):
            if asset.is_file():
                relative = asset.relative_to(skill_dir).as_posix()
                parents = [
                    f"{parent.relative_to(skill_dir).as_posix()}/"
                    for parent in asset.parents
                    if parent != skill_dir and skill_dir in parent.parents
                ]
                assert any(link in linked_text for link in (relative, *parents)), (
                    f"unlinked Rust asset: {relative}"
                )

    assert list(RUST_ROOT.glob("*/skills/*/assets/README.md")) == []
    assert list(RUST_ROOT.glob("*/skills/*/scripts/README.md")) == []
    assert list(RUST_ROOT.glob("*/skills/*/scripts/*.py")) == []


def test_rust_sources_use_current_primary_client_and_domain_documentation() -> None:
    shared_sources = (
        "https://agentskills.io/specification",
        "https://developers.openai.com/codex/build-skills",
        "https://code.claude.com/docs/en/skills",
        "https://opencode.ai/docs/skills/",
        "https://doc.rust-lang.org/",
    )
    skill_specific = {
        "rust-async-concurrency": ("https://docs.rs/tokio/", "https://tokio.rs/"),
        "rust-networking": (
            "https://docs.rs/reqwest/",
            "https://docs.rs/tonic/",
            "https://docs.rs/sqlx/",
        ),
        "rust-dependency-portability": (
            "https://doc.rust-lang.org/cargo/reference/rust-version.html",
            "https://rust-lang.github.io/rustup/",
        ),
        "rustdoc-maintenance": ("https://doc.rust-lang.org/rustdoc/",),
        "rust-cli-application-design": ("https://docs.rs/clap/",),
        "rust-cli-command-development": ("https://docs.rs/clap/",),
    }
    for skill_dir in _skill_directories():
        sources = (skill_dir / "references/sources.md").read_text(encoding="utf-8")
        for source in (*shared_sources, *skill_specific.get(skill_dir.name, ())):
            assert source in sources, f"{skill_dir.name}: missing primary source {source}"
        assert re.search(r"\b20\d{2}-\d{2}-\d{2}\b", sources) is None


def test_rust_canonical_text_has_no_archive_or_repository_specific_residue() -> None:
    forbidden = (
        "contract kit",
        "contract-kit",
        "conkit",
        ".agents/skills",
        "developers.openai.com/codex/skills",
        "use-rust-best-practices-",
        "rust-code-structuring-best-practices",
        "refresh-workspace-agentic-documentation",
        "refresh-workspace-rustdocs",
        "use-rust-shell-cli-best-practices",
        "add-new-cli-command",
    )
    for path in sorted(RUST_ROOT.glob("**/*")):
        assert not path.name.startswith("._"), path
        if path.is_file() and path.suffix in {".md", ".json", ".yaml", ".toml", ".rs"}:
            text = path.read_text(encoding="utf-8")
            for marker in forbidden:
                assert marker not in text.lower(), f"{path}: retained {marker!r}"


def test_rust_safety_regression_contracts_are_explicit() -> None:
    cli_safety = (
        RUST_ROOT
        / "cli-apps/skills/rust-cli-application-design/references/filesystem-output-safety.md"
    ).read_text(encoding="utf-8")
    for marker in (
        "Result<directories::ProjectDirs, AppError>",
        ".ok_or(AppError::ProjectDirectoriesUnavailable)",
        "Reject NaN, positive infinity, and negative infinity",
        "Do not represent money with `f32` or `f64`",
        "filesystem root",
        "home directory",
        "active worktree root",
        "contained within an authorized parent",
        "application ownership",
        "Preview the exact resolved target",
        "Require explicit confirmation",
        "symlink policy",
        "atomic *visibility*",
        "crash durability",
        "preservation of permissions",
        "return `std::process::ExitCode` from `main`",
        "never call `std::process::exit`",
    ):
        assert marker in cli_safety

    async_assets = RUST_ROOT / "best-practices/skills/rust-async-concurrency/assets/templates"
    fanout = (async_assets / "bounded_fanout.rs").read_text(encoding="utf-8")
    for marker in (
        "NonZeroUsize",
        "buffer_unordered(concurrency.get())",
        "cancellation.cancelled()",
        "sort_unstable_by_key",
    ):
        assert marker in fanout

    worker = (async_assets / "sync_worker_bridge.rs").read_text(encoding="utf-8")
    for marker in (
        "capacity: NonZeroUsize",
        "mpsc::channel(capacity.get())",
        "task::spawn_blocking(move || thread.join())",
    ):
        assert marker in worker

    network_assets = RUST_ROOT / "best-practices/skills/rust-networking/assets/templates"
    http = (network_assets / "typed_http_client.rs").read_text(encoding="utf-8")
    for marker in (
        "MAX_ERROR_BYTES",
        "authorization.set_sensitive(true)",
        "connect_timeout",
        ".timeout(",
        "validate_base_url",
        "url.username().is_empty()",
        "url.password().is_none()",
        "url.query().is_none()",
        "url.fragment().is_none()",
        "bounded_error_summary",
        "redact_diagnostic",
    ):
        assert marker in http

    grpc = (network_assets / "grpc_client.rs").read_text(encoding="utf-8")
    for marker in ("connect_timeout", ".timeout(", "request.set_timeout"):
        assert marker in grpc

    pool = (network_assets / "sqlx_pool.rs").read_text(encoding="utf-8")
    for marker in ("checked_sub", "maximum_replicas", "per_replica", "NonZeroU32"):
        assert marker in pool


def test_rust_complete_template_projects_have_required_files() -> None:
    complete_projects = {
        RUST_ROOT
        / "best-practices/skills/rust-core-best-practices/assets/templates/baseline-package": (
            "Cargo.toml",
            "src/lib.rs",
        ),
        RUST_ROOT
        / "best-practices/skills/rust-project-architecture/assets/templates/thin-lib-bin": (
            "Cargo.toml",
            "src/lib.rs",
            "src/main.rs",
        ),
        RUST_ROOT
        / "best-practices/skills/rust-project-architecture/assets/templates/workspace-root": (
            "Cargo.toml",
            "apps/tool/Cargo.toml",
            "apps/tool/src/main.rs",
            "crates/app-core/Cargo.toml",
            "crates/app-core/src/lib.rs",
        ),
    }
    for project, required_files in complete_projects.items():
        for relative in required_files:
            assert (project / relative).is_file(), project / relative


def test_rust_compatibility_fixtures_match_manifests_and_are_executable() -> None:
    for pack_path, expected in PACKS.items():
        inventory = json.loads(
            (pack_path / "tests/compatibility/expected-skills.json").read_text(encoding="utf-8")
        )
        assert inventory["pack"] == expected["id"]
        assert inventory["skills"] == expected["skills"]
        smoke = pack_path / "tests/compatibility/smoke.py"
        if os.name != "nt":
            assert smoke.stat().st_mode & 0o111
        else:
            assert smoke.read_bytes().startswith(b"#!/usr/bin/env python3\n")
