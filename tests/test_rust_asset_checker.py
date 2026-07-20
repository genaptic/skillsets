from __future__ import annotations

import json
import os
import shutil
import subprocess
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest

from skillpack_tools import rust_assets
from skillpack_tools.rust_assets import (
    MINIMUM_RUST,
    BehaviorHarnessMember,
    ExecutableSnippet,
    ProjectContract,
    RustAssetError,
    RustAssetInventory,
)

ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.rust_repository_contract


def inventory_document() -> dict[str, object]:
    return {
        "schemaVersion": 1,
        "minimumRustVersion": "1.85.0",
        "completeProjects": [
            {
                "path": "packs/rust/example/project",
                "cargoArgs": ["test"],
                "lockPolicy": "generate-in-scratch",
            }
        ],
        "executableSnippets": [
            {
                "path": "packs/rust/example/snippet.rs",
                "harness": "tests/rust-harness/src/snippet.rs",
            }
        ],
        "syntaxOnlyFragments": [],
        "behaviorHarness": {
            "manifest": "tests/rust-harness/Cargo.toml",
            "lockfile": "tests/rust-harness/Cargo.lock",
            "members": [
                {
                    "pack": "rust-example",
                    "package": "genaptic-rust-example-harness",
                    "manifest": "tests/rust-harness/rust-example/Cargo.toml",
                    "lockfile": "tests/rust-harness/rust-example/Cargo.lock",
                }
            ],
        },
        "cargoPolicyTrap": {
            "manifest": "tests/rust-cargo-policy-trap/Cargo.toml",
            "lockfile": "tests/rust-cargo-policy-trap/Cargo.lock",
        },
    }


def write_inventory(root: Path, document: dict[str, object]) -> None:
    (root / "tests").mkdir(parents=True)
    (root / "tests/rust-assets.json").write_text(json.dumps(document), encoding="utf-8")


def empty_runtime_inventory(*, projects: tuple[ProjectContract, ...] = ()) -> RustAssetInventory:
    return RustAssetInventory(
        minimum_rust_version="1.85.0",
        complete_projects=projects,
        executable_snippets=(),
        syntax_only_fragments=(),
        behavior_manifest="tests/rust-harness/Cargo.toml",
        behavior_lockfile="tests/rust-harness/Cargo.lock",
        cargo_policy_manifest="tests/rust-cargo-policy-trap/Cargo.toml",
        cargo_policy_lockfile="tests/rust-cargo-policy-trap/Cargo.lock",
    )


def test_repository_inventory_classifies_every_rust_asset_exactly_once() -> None:
    inventory = rust_assets.load_inventory(ROOT)
    discovered = rust_assets.discover_rust_assets(ROOT)
    assert rust_assets.validate_inventory(ROOT, inventory) == discovered
    assert len(discovered) >= 28


def test_selected_inventory_ignores_unrelated_pack_asset_drift(tmp_path: Path) -> None:
    shutil.copytree(ROOT / "packs/rust", tmp_path / "packs/rust")
    shutil.copytree(ROOT / "tests/rust-harness", tmp_path / "tests/rust-harness")
    shutil.copytree(
        ROOT / "tests/rust-cargo-policy-trap",
        tmp_path / "tests/rust-cargo-policy-trap",
    )
    shutil.copy2(ROOT / "tests/rust-assets.json", tmp_path / "tests/rust-assets.json")
    unrelated = tmp_path / "packs/rust/best-practices/unclassified.rs"
    unrelated.write_text("fn unrelated_drift() {}\n", encoding="utf-8")
    unrelated_harness = tmp_path / "tests/rust-harness/rust-best-practices/build.rs"
    unrelated_harness.write_text("fn main() {}\n", encoding="utf-8")

    inventory = rust_assets.load_inventory(tmp_path)
    selection = rust_assets.select_rust_pack(tmp_path, inventory, "rust-cli-apps")
    assert selection is not None
    selected = rust_assets.validate_inventory(
        tmp_path,
        inventory,
        selected_pack=selection[0],
    )
    assert selected
    assert all(path.startswith("packs/rust/cli-apps/") for path in selected)
    with pytest.raises(RustAssetError, match="unclassified"):
        rust_assets.validate_inventory(tmp_path, inventory)


def test_selected_inventory_requires_its_committed_member_lockfile(tmp_path: Path) -> None:
    shutil.copytree(ROOT / "packs/rust", tmp_path / "packs/rust")
    shutil.copytree(ROOT / "tests/rust-harness", tmp_path / "tests/rust-harness")
    shutil.copytree(
        ROOT / "tests/rust-cargo-policy-trap",
        tmp_path / "tests/rust-cargo-policy-trap",
    )
    shutil.copy2(ROOT / "tests/rust-assets.json", tmp_path / "tests/rust-assets.json")
    inventory = rust_assets.load_inventory(tmp_path)
    selection = rust_assets.select_rust_pack(tmp_path, inventory, "rust-cli-apps")
    assert selection is not None
    (tmp_path / selection[1].lockfile).unlink()

    with pytest.raises(RustAssetError, match="missing Rust behavior member lockfile"):
        rust_assets.validate_inventory(tmp_path, inventory, selected_pack=selection[0])


def test_repository_behavior_workspace_has_one_member_per_rust_pack() -> None:
    inventory = rust_assets.load_inventory(ROOT)
    members = {member.pack_id: member for member in inventory.behavior_members}

    assert set(members) == {"rust-best-practices", "rust-cli-apps"}
    assert members["rust-best-practices"].package == ("genaptic-rust-best-practices-harness")
    assert members["rust-cli-apps"].package == "genaptic-rust-cli-apps-harness"
    assert members["rust-best-practices"].lockfile == (
        "tests/rust-harness/rust-best-practices/Cargo.lock"
    )
    assert members["rust-cli-apps"].lockfile == ("tests/rust-harness/rust-cli-apps/Cargo.lock")


def test_pack_selection_accepts_rust_and_rejects_unknown_or_non_rust() -> None:
    inventory = rust_assets.load_inventory(ROOT)

    selection = rust_assets.select_rust_pack(ROOT, inventory, "rust-cli-apps")
    assert selection is not None
    assert selection[0].id == "rust-cli-apps"
    assert selection[1].package == "genaptic-rust-cli-apps-harness"

    with pytest.raises(RustAssetError, match="unknown pack"):
        rust_assets.select_rust_pack(ROOT, inventory, "not-a-pack")
    with pytest.raises(RustAssetError, match="is not a Rust pack"):
        rust_assets.select_rust_pack(ROOT, inventory, "python-best-practices")


def test_inventory_requires_one_adjacent_lockfile_per_behavior_member(tmp_path: Path) -> None:
    document = inventory_document()
    member = document["behaviorHarness"]["members"][0]  # type: ignore[index]
    member.pop("lockfile")  # type: ignore[union-attr]
    write_inventory(tmp_path, document)
    with pytest.raises(RustAssetError, match=r"keys must be .*lockfile"):
        rust_assets.load_inventory(tmp_path)


def test_workspace_member_rewrite_supports_multiline_arrays() -> None:
    source = """[workspace]
members = [
  "rust-best-practices",
  "rust-cli-apps",
]
default-members = ["rust-best-practices"]
resolver = "2"

[workspace.package]
version = "0.0.0"
"""
    rewritten = rust_assets._replace_workspace_member_array(
        source,
        key="members",
        member_name="rust-cli-apps",
        required=True,
    )
    rewritten = rust_assets._replace_workspace_member_array(
        rewritten,
        key="default-members",
        member_name="rust-cli-apps",
        required=False,
    )

    parsed = rust_assets.tomllib.loads(rewritten)
    assert parsed["workspace"]["members"] == ["rust-cli-apps"]
    assert parsed["workspace"]["default-members"] == ["rust-cli-apps"]
    assert parsed["workspace"]["resolver"] == "2"
    assert parsed["workspace"]["package"]["version"] == "0.0.0"


@pytest.mark.skipif(shutil.which("cargo") is None, reason="Cargo is unavailable")
def test_selected_native_cargo_ignores_a_broken_unrelated_member(tmp_path: Path) -> None:
    shutil.copytree(ROOT / "packs/rust", tmp_path / "packs/rust")
    shutil.copytree(ROOT / "tests/rust-harness", tmp_path / "tests/rust-harness")
    shutil.copytree(
        ROOT / "tests/rust-cargo-policy-trap",
        tmp_path / "tests/rust-cargo-policy-trap",
    )
    shutil.copy2(ROOT / "tests/rust-assets.json", tmp_path / "tests/rust-assets.json")
    broken_manifest = tmp_path / "tests/rust-harness/rust-best-practices/Cargo.toml"
    broken_manifest.write_text("this is deliberately invalid TOML\n", encoding="utf-8")

    inventory = rust_assets.load_inventory(tmp_path)
    selection = rust_assets.select_rust_pack(tmp_path, inventory, "rust-cli-apps")
    assert selection is not None
    rust_assets.validate_inventory(tmp_path, inventory, selected_pack=selection[0])
    cargo_home = tmp_path / "cargo-home"
    cargo_home.mkdir()
    target = tmp_path / "target"
    environment = rust_assets._cargo_environment(cargo_home, target, offline=True)

    with rust_assets._behavior_harness_scope(
        tmp_path,
        inventory,
        selection,
    ) as (manifest, workspace_root):
        parsed = rust_assets.tomllib.loads(manifest.read_text(encoding="utf-8"))
        assert parsed["workspace"]["members"] == ["rust-cli-apps"]
        assert (workspace_root / "Cargo.lock").read_bytes() == (
            tmp_path / selection[1].lockfile
        ).read_bytes()
        assert not (workspace_root / "rust-best-practices").exists()
        rust_assets._run(
            [
                shutil.which("cargo") or "cargo",
                "test",
                "--frozen",
                "--workspace",
                "--manifest-path",
                str(manifest),
                "--color",
                "never",
            ],
            root=workspace_root,
            environment=environment,
            timeout=300,
        )

    assert broken_manifest.read_text(encoding="utf-8") == "this is deliberately invalid TOML\n"


def test_inventory_rejects_universal_cargo_feature_and_target_flags(tmp_path: Path) -> None:
    document = inventory_document()
    project = document["completeProjects"][0]  # type: ignore[index]
    project["cargoArgs"] = ["test", "--all-features"]  # type: ignore[index]
    write_inventory(tmp_path, document)
    with pytest.raises(RustAssetError, match="repository-specific test scope"):
        rust_assets.load_inventory(tmp_path)


def test_inventory_rejects_traversal_and_duplicate_json_keys(tmp_path: Path) -> None:
    document = inventory_document()
    document["syntaxOnlyFragments"] = ["../escape.rs"]
    write_inventory(tmp_path, document)
    with pytest.raises(RustAssetError, match="normalized repository-relative"):
        rust_assets.load_inventory(tmp_path)

    (tmp_path / "tests/rust-assets.json").write_text(
        '{"schemaVersion":1,"schemaVersion":1}', encoding="utf-8"
    )
    with pytest.raises(RustAssetError, match="duplicate inventory key"):
        rust_assets.load_inventory(tmp_path)


def test_strict_discovery_rejects_unclassified_assets(tmp_path: Path) -> None:
    rust_file = tmp_path / "packs/rust/example/unclassified.rs"
    rust_file.parent.mkdir(parents=True)
    rust_file.write_text("fn example() {}\n", encoding="utf-8")
    manifest = tmp_path / "tests/rust-harness/Cargo.toml"
    manifest.parent.mkdir(parents=True)
    manifest.write_text("[package]\nname='harness'\nversion='0.0.0'\n", encoding="utf-8")
    (manifest.parent / "Cargo.lock").write_text("version = 4\n", encoding="utf-8")
    inventory = RustAssetInventory(
        minimum_rust_version="1.85.0",
        complete_projects=(),
        executable_snippets=(),
        syntax_only_fragments=(),
        behavior_manifest="tests/rust-harness/Cargo.toml",
        behavior_lockfile="tests/rust-harness/Cargo.lock",
        cargo_policy_manifest="tests/rust-cargo-policy-trap/Cargo.toml",
        cargo_policy_lockfile="tests/rust-cargo-policy-trap/Cargo.lock",
    )
    with pytest.raises(RustAssetError, match="unclassified"):
        rust_assets.validate_inventory(tmp_path, inventory)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("rustc 1.85.0 (abc)", MINIMUM_RUST),
        ("cargo 1.94.1", (1, 94, 1)),
        ("1.85", (1, 85, 0)),
    ],
)
def test_semver_parser_handles_tool_output(value: str, expected: tuple[int, int, int]) -> None:
    assert rust_assets.parse_semver(value) == expected


def test_toolchain_validation_requires_rust_185(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(rust_assets, "_required_tool", lambda name: name)
    versions = {
        "rustc": "rustc 1.84.1",
        "cargo": "cargo 1.84.1",
        "rustfmt": "rustfmt 1.8.0",
    }
    monkeypatch.setattr(
        rust_assets,
        "_run",
        lambda command, **_kwargs: versions[command[0]],
    )
    with pytest.raises(RustAssetError, match=r"Rust 1\.85\.0 or newer"):
        rust_assets.verify_toolchain(tmp_path)


def test_toolchain_validation_requires_cargo_185(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(rust_assets, "_required_tool", lambda name: name)
    versions = {
        "rustc": "rustc 1.85.0",
        "cargo": "cargo 1.84.1",
        "rustfmt": "rustfmt 1.8.0",
    }
    monkeypatch.setattr(
        rust_assets,
        "_run",
        lambda command, **_kwargs: versions[command[0]],
    )
    with pytest.raises(RustAssetError, match=r"Cargo 1\.85\.0 or newer"):
        rust_assets.verify_toolchain(tmp_path)


def test_missing_rust_tool_is_an_actionable_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(rust_assets.shutil, "which", lambda _name: None)
    with pytest.raises(RustAssetError, match="install it explicitly"):
        rust_assets._required_tool("rustfmt")


def test_cargo_environment_is_offline_and_uses_isolated_paths(tmp_path: Path) -> None:
    cargo_home = tmp_path / "cargo-home"
    target = tmp_path / "target"
    environment = rust_assets._cargo_environment(cargo_home, target, offline=True)
    assert environment["CARGO_HOME"] == str(cargo_home)
    assert environment["CARGO_TARGET_DIR"] == str(target)
    assert environment["CARGO_NET_OFFLINE"] == "true"
    assert environment["CARGO_INCREMENTAL"] == "0"


def test_command_failures_are_actionable(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        rust_assets.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args, 7, "output", "failure"),
    )
    with pytest.raises(RustAssetError, match=r"command failed \(7\).+example"):
        rust_assets._run(["example", "--check"], root=tmp_path)


def test_command_timeout_is_actionable(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def timeout(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired(["slow-command"], 1)

    monkeypatch.setattr(rust_assets.subprocess, "run", timeout)
    with pytest.raises(RustAssetError, match="could not run slow-command"):
        rust_assets._run(["slow-command"], root=tmp_path, timeout=1)


def test_project_contract_forbids_implicit_universal_scope() -> None:
    project = ProjectContract(
        path="packs/rust/example",
        cargo_args=("test", "--workspace"),
        lock_policy="generate-in-scratch",
    )
    assert "--all-features" not in project.cargo_args
    assert "--all-targets" not in project.cargo_args


def test_executable_snippet_has_one_explicit_harness() -> None:
    snippet = ExecutableSnippet(
        path="packs/rust/example.rs",
        harness="tests/rust-harness/src/example.rs",
    )
    assert snippet.harness.endswith("/example.rs")


def test_harness_requires_a_direct_import_of_canonical_bytes() -> None:
    path = "packs/rust/example/assets/templates/example.rs"
    direct = """include!(concat!(
        env!("CARGO_MANIFEST_DIR"),
        "/../../packs/rust/example/assets/templates/example.rs"
    ));
    """
    generated_copy = """
    const _CANONICAL_SOURCE: &str =
        "/../../packs/rust/example/assets/templates/example.rs";
    include!(concat!(env!("OUT_DIR"), "/example.rs"));
    """
    assert rust_assets._has_direct_canonical_include(direct, path)
    assert not rust_assets._has_direct_canonical_include(generated_copy, path)


def test_expected_failure_requires_one_exact_policy_sentinel(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    expected = "GENAPTIC_CARGO_POLICY_WORKSPACE_SENTINEL"
    completed = subprocess.CompletedProcess(
        ["cargo", "test"],
        101,
        "",
        f"error: {expected}\n",
    )
    monkeypatch.setattr(rust_assets.subprocess, "run", lambda *_args, **_kwargs: completed)
    rust_assets._run_expect_failure(
        ["cargo", "test"],
        root=tmp_path,
        environment=os.environ.copy(),
        sentinel=expected,
    )

    completed.returncode = 0
    with pytest.raises(RustAssetError, match="unexpectedly passed"):
        rust_assets._run_expect_failure(
            ["cargo", "test"],
            root=tmp_path,
            environment=os.environ.copy(),
            sentinel=expected,
        )

    completed.returncode = 101
    completed.stderr = "error: unrelated compiler failure\n"
    with pytest.raises(RustAssetError, match="exactly the expected policy"):
        rust_assets._run_expect_failure(
            ["cargo", "test"],
            root=tmp_path,
            environment=os.environ.copy(),
            sentinel=expected,
        )


def test_complete_project_build_is_offline_frozen_and_lock_deterministic(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    project_path = tmp_path / "packs/rust/example"
    project_path.mkdir(parents=True)
    (project_path / "Cargo.toml").write_text("[package]\nname='example'\n", encoding="utf-8")
    project = ProjectContract(
        path="packs/rust/example",
        cargo_args=("test", "--workspace"),
        lock_policy="generate-in-scratch",
    )
    calls: list[tuple[list[str], dict[str, str]]] = []

    def fake_run(
        command: list[str], *, root: Path, environment: dict[str, str], **_kwargs: object
    ) -> str:
        calls.append((command, environment))
        if "--offline" in command:
            (root / "Cargo.lock").write_bytes(b"stable-lock\n")
        return ""

    monkeypatch.setattr(rust_assets, "_run", fake_run)
    assert rust_assets._build_project_once(tmp_path, project, "cargo") == b"stable-lock\n"
    assert ["--offline" in command for command, _environment in calls] == [True, False]
    assert ["--frozen" in command for command, _environment in calls] == [False, True]
    assert all(environment["CARGO_NET_OFFLINE"] == "true" for _, environment in calls)
    assert all(str(tmp_path) not in environment["CARGO_TARGET_DIR"] for _, environment in calls)


def test_complete_project_rejects_missing_and_drifting_scratch_locks(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    project_path = tmp_path / "packs/rust/example"
    project_path.mkdir(parents=True)
    (project_path / "Cargo.toml").write_text("[package]\nname='example'\n", encoding="utf-8")
    project = ProjectContract(
        path="packs/rust/example",
        cargo_args=("test",),
        lock_policy="generate-in-scratch",
    )
    monkeypatch.setattr(rust_assets, "_run", lambda *_args, **_kwargs: "")
    with pytest.raises(RustAssetError, match="did not create a scratch lockfile"):
        rust_assets._build_project_once(tmp_path, project, "cargo")

    def mutate_lock(command: list[str], *, root: Path, **_kwargs: object) -> str:
        lockfile = root / "Cargo.lock"
        lockfile.write_bytes(b"before\n" if "--offline" in command else b"after\n")
        return ""

    monkeypatch.setattr(rust_assets, "_run", mutate_lock)
    with pytest.raises(RustAssetError, match="frozen Cargo check changed"):
        rust_assets._build_project_once(tmp_path, project, "cargo")


def test_cargo_policy_trap_runs_separate_sentinel_checks(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fixture = tmp_path / "tests/rust-cargo-policy-trap"
    fixture.mkdir(parents=True)
    (fixture / "Cargo.toml").write_text("[workspace]\n", encoding="utf-8")
    (fixture / "Cargo.lock").write_text("version = 4\n", encoding="utf-8")
    inventory = empty_runtime_inventory()
    events: list[tuple[str, list[str], str | None]] = []
    monkeypatch.setattr(
        rust_assets,
        "_run",
        lambda command, **_kwargs: events.append(("success", command, None)) or "",
    )
    monkeypatch.setattr(
        rust_assets,
        "_run_expect_failure",
        lambda command, sentinel, **_kwargs: events.append(("failure", command, sentinel)),
    )

    rust_assets._check_cargo_policy_trap(tmp_path, inventory, "cargo")

    assert [event[0] for event in events] == ["success", "failure", "failure"]
    assert "--all-features" in events[1][1] and "--workspace" not in events[1][1]
    assert events[1][2] == "GENAPTIC_CARGO_POLICY_ALL_FEATURES_SENTINEL"
    assert "--workspace" in events[2][1] and "--all-features" not in events[2][1]
    assert events[2][2] == "GENAPTIC_CARGO_POLICY_WORKSPACE_SENTINEL"


def test_bootstrap_fetches_only_the_locked_harness_into_the_selected_cache(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    inventory = empty_runtime_inventory()
    cargo_home = tmp_path / "isolated-cargo-home"
    events: list[str] = []
    calls: list[tuple[list[str], dict[str, str], int]] = []
    selected_pack = next(
        pack for pack in rust_assets.discover_packs(ROOT) if pack.id == "rust-cli-apps"
    )
    member = BehaviorHarnessMember(
        pack_id="rust-cli-apps",
        package="genaptic-rust-cli-apps-harness",
        manifest="tests/rust-harness/rust-cli-apps/Cargo.toml",
        lockfile="tests/rust-harness/rust-cli-apps/Cargo.lock",
    )
    monkeypatch.setattr(rust_assets, "load_inventory", lambda _root: inventory)
    monkeypatch.setattr(
        rust_assets,
        "validate_inventory",
        lambda _root, _inventory, **_kwargs: events.append("validate") or (),
    )
    monkeypatch.setattr(
        rust_assets,
        "select_rust_pack",
        lambda _root, _inventory, pack_id: (
            events.append(f"select:{pack_id}") or (selected_pack, member)
        ),
    )
    monkeypatch.setattr(rust_assets, "verify_toolchain", lambda _root: {"cargo": "cargo"})

    isolated_manifest = tmp_path / "isolated/Cargo.toml"

    @contextmanager
    def fake_scope(
        _root: Path,
        _inventory: RustAssetInventory,
        selection: tuple[object, BehaviorHarnessMember] | None,
    ) -> Iterator[tuple[Path, Path]]:
        assert selection is not None and selection[1] == member
        yield isolated_manifest, isolated_manifest.parent

    monkeypatch.setattr(rust_assets, "_behavior_harness_scope", fake_scope)

    def fake_run(
        command: list[str],
        *,
        environment: dict[str, str],
        timeout: int,
        **_kwargs: object,
    ) -> str:
        events.append("fetch")
        calls.append((command, environment, timeout))
        return ""

    monkeypatch.setattr(rust_assets, "_run", fake_run)
    rust_assets.bootstrap_harness(tmp_path, cargo_home, pack_id="rust-cli-apps")

    assert events == ["select:rust-cli-apps", "validate", "fetch"]
    command, environment, timeout = calls[0]
    assert command[:3] == ["cargo", "fetch", "--locked"]
    assert command[command.index("--manifest-path") + 1] == os.fspath(isolated_manifest)
    assert environment["CARGO_HOME"] == str(cargo_home)
    assert "CARGO_NET_OFFLINE" not in environment
    assert timeout == 300


def test_check_orchestrates_format_projects_policy_and_frozen_harness_offline(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    rust_source = tmp_path / "packs/rust/example.rs"
    rust_source.parent.mkdir(parents=True)
    rust_source.write_text("fn example() {}\n", encoding="utf-8")
    toml_asset = tmp_path / "packs/rust/example.toml"
    toml_asset.write_text("value = 1\n", encoding="utf-8")
    project = ProjectContract("packs/rust/project", ("test",), "generate-in-scratch")
    inventory = empty_runtime_inventory(projects=(project,))
    cargo_home = tmp_path / "cargo-home"
    cargo_home.mkdir()
    events: list[str] = []
    commands: list[tuple[list[str], dict[str, str] | None, int]] = []
    monkeypatch.setattr(rust_assets, "load_inventory", lambda _root: inventory)
    monkeypatch.setattr(
        rust_assets,
        "validate_inventory",
        lambda _root, _inventory, **_kwargs: (
            "packs/rust/example.rs",
            "packs/rust/example.toml",
        ),
    )
    monkeypatch.setattr(
        rust_assets,
        "verify_toolchain",
        lambda _root: {"cargo": "cargo", "rustfmt": "rustfmt"},
    )

    def fake_run(
        command: list[str],
        *,
        environment: dict[str, str] | None = None,
        timeout: int = 180,
        **_kwargs: object,
    ) -> str:
        events.append("rustfmt" if command[0] == "rustfmt" else "harness")
        commands.append((command, environment, timeout))
        return ""

    monkeypatch.setattr(rust_assets, "_run", fake_run)
    monkeypatch.setattr(
        rust_assets,
        "_build_project_once",
        lambda *_args, **_kwargs: events.append("project") or b"stable-lock",
    )
    monkeypatch.setattr(
        rust_assets,
        "_check_cargo_policy_trap",
        lambda *_args, **_kwargs: events.append("policy"),
    )

    rust_assets.check_rust_assets(tmp_path, cargo_home)

    assert events == ["rustfmt", "project", "project", "policy", "harness"]
    assert commands[0][0][:4] == ["rustfmt", "--edition", "2024", "--check"]
    harness_command, harness_environment, harness_timeout = commands[1]
    assert "--frozen" in harness_command
    assert "--workspace" in harness_command
    assert harness_environment is not None
    assert harness_environment["CARGO_NET_OFFLINE"] == "true"
    assert harness_timeout == 300


def test_selected_check_runs_one_pack_member_and_keeps_shared_policy_invariants(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    selected_asset = "packs/rust/cli-apps/selected.rs"
    other_asset = "packs/rust/best-practices/other.rs"
    for relative in (selected_asset, other_asset):
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("fn example() {}\n", encoding="utf-8")
    selected_project = ProjectContract(
        "packs/rust/cli-apps/project", ("test",), "generate-in-scratch"
    )
    other_project = ProjectContract(
        "packs/rust/best-practices/project", ("test",), "generate-in-scratch"
    )
    inventory = empty_runtime_inventory(projects=(selected_project, other_project))
    cargo_home = tmp_path / "cargo-home"
    cargo_home.mkdir()
    selected_pack = next(
        pack for pack in rust_assets.discover_packs(ROOT) if pack.id == "rust-cli-apps"
    )
    member = BehaviorHarnessMember(
        pack_id="rust-cli-apps",
        package="genaptic-rust-cli-apps-harness",
        manifest="tests/rust-harness/rust-cli-apps/Cargo.toml",
        lockfile="tests/rust-harness/rust-cli-apps/Cargo.lock",
    )
    commands: list[list[str]] = []
    projects: list[str] = []
    shared_policy: list[bool] = []
    monkeypatch.setattr(rust_assets, "load_inventory", lambda _root: inventory)
    monkeypatch.setattr(
        rust_assets,
        "validate_inventory",
        lambda *_args, **_kwargs: (selected_asset,),
    )
    monkeypatch.setattr(rust_assets, "select_rust_pack", lambda *_args: (selected_pack, member))
    monkeypatch.setattr(
        rust_assets,
        "verify_toolchain",
        lambda _root: {"cargo": "cargo", "rustfmt": "rustfmt"},
    )

    isolated_manifest = tmp_path / "isolated/Cargo.toml"

    @contextmanager
    def fake_scope(
        _root: Path,
        _inventory: RustAssetInventory,
        selection: tuple[object, BehaviorHarnessMember] | None,
    ) -> Iterator[tuple[Path, Path]]:
        assert selection is not None and selection[1] == member
        yield isolated_manifest, isolated_manifest.parent

    monkeypatch.setattr(rust_assets, "_behavior_harness_scope", fake_scope)

    monkeypatch.setattr(
        rust_assets,
        "_run",
        lambda command, **_kwargs: commands.append(command) or "",
    )
    monkeypatch.setattr(
        rust_assets,
        "_build_project_once",
        lambda _root, project, _cargo: projects.append(project.path) or b"stable-lock",
    )
    monkeypatch.setattr(
        rust_assets,
        "_check_cargo_policy_trap",
        lambda *_args: shared_policy.append(True),
    )

    rust_assets.check_rust_assets(tmp_path, cargo_home, pack_id="rust-cli-apps")

    assert selected_asset in commands[0]
    assert other_asset not in commands[0]
    assert projects == [selected_project.path, selected_project.path]
    assert shared_policy == [True]
    assert "--workspace" in commands[1]
    assert "--package" not in commands[1]
    assert commands[1][commands[1].index("--manifest-path") + 1] == os.fspath(isolated_manifest)


def test_check_rejects_nondeterministic_project_locks(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    inventory = empty_runtime_inventory(
        projects=(ProjectContract("packs/rust/project", ("test",), "generate-in-scratch"),)
    )
    cargo_home = tmp_path / "cargo-home"
    cargo_home.mkdir()
    monkeypatch.setattr(rust_assets, "load_inventory", lambda _root: inventory)
    monkeypatch.setattr(rust_assets, "validate_inventory", lambda *_args, **_kwargs: ())
    monkeypatch.setattr(
        rust_assets,
        "verify_toolchain",
        lambda _root: {"cargo": "cargo", "rustfmt": "rustfmt"},
    )
    monkeypatch.setattr(rust_assets, "_run", lambda *_args, **_kwargs: "")
    locks = iter((b"first", b"second"))
    monkeypatch.setattr(rust_assets, "_build_project_once", lambda *_args: next(locks))

    with pytest.raises(RustAssetError, match="nondeterministic scratch lockfile"):
        rust_assets.check_rust_assets(tmp_path, cargo_home)


def test_check_detects_canonical_postimage_mutation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    asset = tmp_path / "packs/rust/example.rs"
    asset.parent.mkdir(parents=True)
    asset.write_text("fn before() {}\n", encoding="utf-8")
    inventory = empty_runtime_inventory()
    cargo_home = tmp_path / "cargo-home"
    cargo_home.mkdir()
    monkeypatch.setattr(rust_assets, "load_inventory", lambda _root: inventory)
    monkeypatch.setattr(
        rust_assets,
        "validate_inventory",
        lambda *_args, **_kwargs: ("packs/rust/example.rs",),
    )
    monkeypatch.setattr(
        rust_assets,
        "verify_toolchain",
        lambda _root: {"cargo": "cargo", "rustfmt": "rustfmt"},
    )
    monkeypatch.setattr(rust_assets, "_run", lambda *_args, **_kwargs: "")

    def mutate(*_args: object, **_kwargs: object) -> None:
        asset.write_text("fn after() {}\n", encoding="utf-8")

    monkeypatch.setattr(rust_assets, "_check_cargo_policy_trap", mutate)
    with pytest.raises(RustAssetError, match="mutated canonical files"):
        rust_assets.check_rust_assets(tmp_path, cargo_home)


@pytest.mark.parametrize("residue_name", ["Cargo.lock", "target"])
def test_check_rejects_canonical_build_residue(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, residue_name: str
) -> None:
    rust_root = tmp_path / "packs/rust/example"
    rust_root.mkdir(parents=True)
    residue = rust_root / residue_name
    if residue_name == "target":
        residue.mkdir()
    else:
        residue.write_text("version = 4\n", encoding="utf-8")
    inventory = empty_runtime_inventory()
    cargo_home = tmp_path / "cargo-home"
    cargo_home.mkdir()
    monkeypatch.setattr(rust_assets, "load_inventory", lambda _root: inventory)
    monkeypatch.setattr(rust_assets, "validate_inventory", lambda *_args, **_kwargs: ())
    monkeypatch.setattr(
        rust_assets,
        "verify_toolchain",
        lambda _root: {"cargo": "cargo", "rustfmt": "rustfmt"},
    )
    monkeypatch.setattr(rust_assets, "_run", lambda *_args, **_kwargs: "")
    monkeypatch.setattr(rust_assets, "_check_cargo_policy_trap", lambda *_args: None)

    with pytest.raises(RustAssetError, match="canonical build residue"):
        rust_assets.check_rust_assets(tmp_path, cargo_home)


def test_check_requires_an_explicitly_bootstrapped_cache(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    inventory = empty_runtime_inventory()
    monkeypatch.setattr(rust_assets, "load_inventory", lambda _root: inventory)
    monkeypatch.setattr(rust_assets, "validate_inventory", lambda *_args, **_kwargs: ())
    monkeypatch.setattr(
        rust_assets,
        "verify_toolchain",
        lambda _root: {"cargo": "cargo", "rustfmt": "rustfmt"},
    )
    monkeypatch.setattr(rust_assets, "_run", lambda *_args, **_kwargs: "")
    monkeypatch.setattr(rust_assets, "_check_cargo_policy_trap", lambda *_args: None)

    with pytest.raises(RustAssetError, match="run `make rust-bootstrap`"):
        rust_assets.check_rust_assets(tmp_path, tmp_path / "missing-cargo-home")


def test_main_routes_bootstrap_and_check_with_resolved_cache_paths(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[tuple[str, Path, Path]] = []
    monkeypatch.setattr(
        rust_assets,
        "bootstrap_harness",
        lambda root, cargo_home, *, pack_id=None: calls.append(
            (f"bootstrap:{pack_id}", root, cargo_home)
        ),
    )
    monkeypatch.setattr(
        rust_assets,
        "check_rust_assets",
        lambda root, cargo_home, *, pack_id=None: calls.append(
            (f"check:{pack_id}", root, cargo_home)
        ),
    )
    explicit_cache = tmp_path / "explicit-cache"

    assert (
        rust_assets.main(
            [
                "--root",
                str(tmp_path),
                "--cargo-home",
                str(explicit_cache),
                "--bootstrap",
                "--pack",
                "rust-cli-apps",
            ]
        )
        == 0
    )
    assert rust_assets.main(["--root", str(tmp_path)]) == 0
    assert calls == [
        ("bootstrap:rust-cli-apps", tmp_path.resolve(), explicit_cache.resolve()),
        ("check:None", tmp_path.resolve(), (tmp_path / ".venv/rust-cargo-home").resolve()),
    ]


def test_main_reports_checker_errors(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    def fail(_root: Path, _cargo_home: Path, *, pack_id: str | None = None) -> None:
        assert pack_id is None
        raise RustAssetError("deliberate checker failure")

    monkeypatch.setattr(rust_assets, "check_rust_assets", fail)
    with pytest.raises(SystemExit) as raised:
        rust_assets.main(["--root", str(tmp_path)])
    assert raised.value.code == 1
    assert "error: deliberate checker failure" in capsys.readouterr().err
