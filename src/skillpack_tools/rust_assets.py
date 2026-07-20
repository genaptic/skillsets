from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import stat
import subprocess
import tempfile
import tomllib
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .models import Pack, _load_repository_yaml, discover_packs

MINIMUM_RUST = (1, 85, 0)
ASSET_SUFFIXES = {".rs", ".toml"}
FORBIDDEN_UNIVERSAL_ARGS = {"--all-features", "--all-targets"}


class RustAssetError(RuntimeError):
    """A deterministic Rust asset contract failure."""


@dataclass(frozen=True)
class ProjectContract:
    path: str
    cargo_args: tuple[str, ...]
    lock_policy: str


@dataclass(frozen=True)
class ExecutableSnippet:
    path: str
    harness: str


@dataclass(frozen=True)
class BehaviorHarnessMember:
    pack_id: str
    package: str
    manifest: str
    lockfile: str


@dataclass(frozen=True)
class RustAssetInventory:
    minimum_rust_version: str
    complete_projects: tuple[ProjectContract, ...]
    executable_snippets: tuple[ExecutableSnippet, ...]
    syntax_only_fragments: tuple[str, ...]
    behavior_manifest: str
    behavior_lockfile: str
    cargo_policy_manifest: str
    cargo_policy_lockfile: str
    behavior_members: tuple[BehaviorHarnessMember, ...] = ()


def _object_without_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise RustAssetError(f"duplicate inventory key {key!r}")
        result[key] = value
    return result


def _require_keys(value: object, *, required: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RustAssetError(f"{label} must be an object")
    actual = set(value)
    if actual != required:
        raise RustAssetError(f"{label} keys must be {sorted(required)}; found {sorted(actual)}")
    return value


def _safe_relative(value: object, *, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise RustAssetError(f"{label} must be a non-empty repository-relative path")
    path = Path(value)
    if path.is_absolute() or ".." in path.parts or path.as_posix() != value:
        raise RustAssetError(f"{label} must be a normalized repository-relative path: {value!r}")
    return value


def load_inventory(root: Path) -> RustAssetInventory:
    path = root / "tests" / "rust-assets.json"
    try:
        raw = json.loads(
            path.read_text(encoding="utf-8"), object_pairs_hook=_object_without_duplicates
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RustAssetError(f"cannot read {path.relative_to(root)}: {exc}") from exc
    data = _require_keys(
        raw,
        required={
            "schemaVersion",
            "minimumRustVersion",
            "completeProjects",
            "executableSnippets",
            "syntaxOnlyFragments",
            "behaviorHarness",
            "cargoPolicyTrap",
        },
        label="Rust asset inventory",
    )
    if data["schemaVersion"] != 1:
        raise RustAssetError("Rust asset inventory schemaVersion must be 1")
    minimum = data["minimumRustVersion"]
    if not isinstance(minimum, str) or parse_semver(minimum) != MINIMUM_RUST:
        raise RustAssetError("minimumRustVersion must be exactly 1.85.0")

    projects_raw = data["completeProjects"]
    if not isinstance(projects_raw, list) or not projects_raw:
        raise RustAssetError("completeProjects must be a non-empty array")
    projects: list[ProjectContract] = []
    for index, raw_project in enumerate(projects_raw):
        project = _require_keys(
            raw_project,
            required={"path", "cargoArgs", "lockPolicy"},
            label=f"completeProjects[{index}]",
        )
        relative = _safe_relative(project["path"], label=f"completeProjects[{index}].path")
        args = project["cargoArgs"]
        if (
            not isinstance(args, list)
            or not args
            or any(not isinstance(arg, str) or not arg for arg in args)
        ):
            raise RustAssetError(f"completeProjects[{index}].cargoArgs must be strings")
        if args[0] != "test" or FORBIDDEN_UNIVERSAL_ARGS.intersection(args):
            raise RustAssetError(
                f"completeProjects[{index}].cargoArgs must use repository-specific test scope"
            )
        if project["lockPolicy"] != "generate-in-scratch":
            raise RustAssetError(
                f"completeProjects[{index}].lockPolicy must be 'generate-in-scratch'"
            )
        projects.append(ProjectContract(relative, tuple(args), project["lockPolicy"]))

    executable_raw = data["executableSnippets"]
    if not isinstance(executable_raw, list) or not executable_raw:
        raise RustAssetError("executableSnippets must be a non-empty array")
    executable: list[ExecutableSnippet] = []
    for index, raw_snippet in enumerate(executable_raw):
        snippet = _require_keys(
            raw_snippet,
            required={"path", "harness"},
            label=f"executableSnippets[{index}]",
        )
        executable.append(
            ExecutableSnippet(
                path=_safe_relative(snippet["path"], label=f"executableSnippets[{index}].path"),
                harness=_safe_relative(
                    snippet["harness"], label=f"executableSnippets[{index}].harness"
                ),
            )
        )

    fragments_raw = data["syntaxOnlyFragments"]
    if not isinstance(fragments_raw, list) or any(
        not isinstance(item, str) for item in fragments_raw
    ):
        raise RustAssetError("syntaxOnlyFragments must be an array of paths")
    fragments = tuple(
        _safe_relative(item, label=f"syntaxOnlyFragments[{index}]")
        for index, item in enumerate(fragments_raw)
    )

    harness = _require_keys(
        data["behaviorHarness"],
        required={"manifest", "lockfile", "members"},
        label="behaviorHarness",
    )
    members_raw = harness["members"]
    if not isinstance(members_raw, list) or not members_raw:
        raise RustAssetError("behaviorHarness.members must be a non-empty array")
    members: list[BehaviorHarnessMember] = []
    for index, raw_member in enumerate(members_raw):
        member = _require_keys(
            raw_member,
            required={"pack", "package", "manifest", "lockfile"},
            label=f"behaviorHarness.members[{index}]",
        )
        pack_id = member["pack"]
        package = member["package"]
        if not isinstance(pack_id, str) or not pack_id:
            raise RustAssetError(f"behaviorHarness.members[{index}].pack must be a string")
        if not isinstance(package, str) or not package:
            raise RustAssetError(f"behaviorHarness.members[{index}].package must be a string")
        members.append(
            BehaviorHarnessMember(
                pack_id=pack_id,
                package=package,
                manifest=_safe_relative(
                    member["manifest"], label=f"behaviorHarness.members[{index}].manifest"
                ),
                lockfile=_safe_relative(
                    member["lockfile"], label=f"behaviorHarness.members[{index}].lockfile"
                ),
            )
        )
    for label, values in (
        ("pack", [member.pack_id for member in members]),
        ("package", [member.package for member in members]),
        ("manifest", [member.manifest for member in members]),
        ("lockfile", [member.lockfile for member in members]),
    ):
        duplicates = sorted(value for value in set(values) if values.count(value) > 1)
        if duplicates:
            raise RustAssetError(
                f"behaviorHarness.members contains duplicate {label} values: {duplicates}"
            )
    cargo_policy = _require_keys(
        data["cargoPolicyTrap"],
        required={"manifest", "lockfile"},
        label="cargoPolicyTrap",
    )
    return RustAssetInventory(
        minimum_rust_version=minimum,
        complete_projects=tuple(projects),
        executable_snippets=tuple(executable),
        syntax_only_fragments=fragments,
        behavior_manifest=_safe_relative(harness["manifest"], label="behaviorHarness.manifest"),
        behavior_lockfile=_safe_relative(harness["lockfile"], label="behaviorHarness.lockfile"),
        cargo_policy_manifest=_safe_relative(
            cargo_policy["manifest"], label="cargoPolicyTrap.manifest"
        ),
        cargo_policy_lockfile=_safe_relative(
            cargo_policy["lockfile"], label="cargoPolicyTrap.lockfile"
        ),
        behavior_members=tuple(members),
    )


def discover_rust_assets(root: Path) -> tuple[str, ...]:
    rust_root = root / "packs" / "rust"
    return tuple(
        path.relative_to(root).as_posix()
        for path in sorted(rust_root.rglob("*"))
        if path.is_file() and path.suffix.lower() in ASSET_SUFFIXES
    )


def _has_direct_canonical_include(
    harness_text: str,
    snippet_path: str,
    *,
    repository_prefix: str = "../..",
) -> bool:
    expected_path = re.escape(f"/{repository_prefix}/{snippet_path}")
    pattern = (
        r'include!\s*\(\s*concat!\s*\(\s*env!\s*\(\s*"CARGO_MANIFEST_DIR"\s*\)'
        rf'\s*,\s*"{expected_path}"\s*,?\s*\)\s*\)\s*;'
    )
    return re.search(pattern, harness_text) is not None


def _read_toml(root: Path, relative: str, *, label: str) -> dict[str, Any]:
    try:
        value = tomllib.loads((root / relative).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, tomllib.TOMLDecodeError) as exc:
        raise RustAssetError(f"invalid {label} {relative}: {exc}") from exc
    if not isinstance(value, dict):  # pragma: no cover - tomllib always returns a dict
        raise RustAssetError(f"{label} {relative} must be a TOML table")
    return value


def _rust_pack_map(root: Path) -> dict[str, Pack]:
    packs = [pack for pack in discover_packs(root) if pack.language == "rust"]
    result = {pack.id: pack for pack in packs}
    if len(result) != len(packs):
        raise RustAssetError("Rust pack IDs must be unique before harness selection")
    return result


def _pack_for_asset(relative: str, packs: dict[str, Pack]) -> Pack:
    matches = [
        pack
        for pack in packs.values()
        if relative == pack.relative_path or relative.startswith(f"{pack.relative_path}/")
    ]
    if len(matches) != 1:
        raise RustAssetError(
            f"Rust asset {relative!r} must belong to exactly one declared Rust pack"
        )
    return matches[0]


def _validate_behavior_workspace(
    root: Path,
    inventory: RustAssetInventory,
    *,
    selected_pack: Pack | None = None,
) -> dict[str, Pack]:
    if not inventory.behavior_members:
        raise RustAssetError("behaviorHarness.members must declare one member per Rust pack")
    packs = _rust_pack_map(root) if selected_pack is None else {selected_pack.id: selected_pack}
    all_members = {member.pack_id: member for member in inventory.behavior_members}
    members = all_members
    if selected_pack is not None:
        members = (
            {selected_pack.id: all_members[selected_pack.id]}
            if selected_pack.id in all_members
            else {}
        )
    if set(members) != set(packs):
        raise RustAssetError(
            "Rust behavior workspace members must match Rust packs exactly; "
            f"missing={sorted(set(packs) - set(members))}, "
            f"unknown={sorted(set(members) - set(packs))}"
        )

    workspace_manifest = root / inventory.behavior_manifest
    workspace_root = workspace_manifest.parent
    workspace = _read_toml(
        root,
        inventory.behavior_manifest,
        label="Rust behavior workspace manifest",
    ).get("workspace")
    if not isinstance(workspace, dict):
        raise RustAssetError("Rust behavior harness root must be a Cargo workspace")
    declared_members = workspace.get("members")
    if not isinstance(declared_members, list) or any(
        not isinstance(item, str) for item in declared_members
    ):
        raise RustAssetError("Rust behavior workspace members must be explicit paths")

    expected_member_paths: set[str] = set()
    actual_harnesses: set[str] = set()
    for member in members.values():
        member_manifest = root / member.manifest
        if not member_manifest.is_file():
            raise RustAssetError(f"missing Rust behavior harness member: {member.manifest}")
        try:
            member_relative = member_manifest.parent.relative_to(workspace_root).as_posix()
        except ValueError as exc:
            raise RustAssetError(
                f"Rust behavior harness member must be inside the workspace: {member.manifest}"
            ) from exc
        if member_relative in {"", "."} or "/" in member_relative:
            raise RustAssetError(
                f"Rust behavior harness members must be direct workspace children: {member.manifest}"
            )
        expected_lockfile = member_manifest.parent / "Cargo.lock"
        if root / member.lockfile != expected_lockfile:
            raise RustAssetError(
                f"{member.manifest}: member lockfile must be "
                f"{expected_lockfile.relative_to(root).as_posix()!r}"
            )
        if not expected_lockfile.is_file():
            raise RustAssetError(f"missing Rust behavior member lockfile: {member.lockfile}")
        lock_data = _read_toml(root, member.lockfile, label="Rust behavior member lockfile")
        packages = lock_data.get("package")
        if not isinstance(packages, list) or not any(
            isinstance(package_entry, dict) and package_entry.get("name") == member.package
            for package_entry in packages
        ):
            raise RustAssetError(
                f"{member.lockfile}: lockfile must contain package {member.package!r}"
            )
        expected_member_paths.add(member_relative)
        member_data = _read_toml(root, member.manifest, label="Rust behavior member manifest")
        package = member_data.get("package")
        if not isinstance(package, dict) or package.get("name") != member.package:
            raise RustAssetError(f"{member.manifest}: package.name must be {member.package!r}")
        if package.get("publish") is not False:
            raise RustAssetError(f"{member.manifest}: harness package must set publish = false")
        member_src = member_manifest.parent / "src"
        if not (member_src / "lib.rs").is_file():
            raise RustAssetError(f"{member.manifest}: harness member is missing src/lib.rs")
        actual_harnesses.update(
            path.relative_to(root).as_posix()
            for path in member_src.glob("*.rs")
            if path.name != "lib.rs"
        )

    declared_member_set = set(declared_members)
    if selected_pack is None and declared_member_set != expected_member_paths:
        raise RustAssetError(
            "Rust behavior Cargo workspace members differ from the inventory; "
            f"missing={sorted(expected_member_paths - declared_member_set)}, "
            f"unknown={sorted(declared_member_set - expected_member_paths)}"
        )
    if selected_pack is not None and not expected_member_paths <= declared_member_set:
        raise RustAssetError(
            f"Rust behavior Cargo workspace does not declare the {selected_pack.id} member"
        )
    if selected_pack is None:
        declared_lockfiles = {
            inventory.behavior_lockfile,
            *(member.lockfile for member in inventory.behavior_members),
        }
        discovered_lockfiles = {
            path.relative_to(root).as_posix()
            for path in workspace_root.rglob("Cargo.lock")
            if path.is_file()
        }
        if discovered_lockfiles != declared_lockfiles:
            raise RustAssetError(
                "Rust behavior lockfile inventory mismatch; "
                f"missing={sorted(declared_lockfiles - discovered_lockfiles)}, "
                f"unclassified={sorted(discovered_lockfiles - declared_lockfiles)}"
            )
    build_script_roots = (
        [workspace_root]
        if selected_pack is None
        else [workspace_root / member_path for member_path in expected_member_paths]
    )
    build_scripts = [
        path.relative_to(root).as_posix()
        for build_root in build_script_roots
        for path in sorted(build_root.rglob("build.rs"))
    ]
    workspace_build = workspace_root / "build.rs"
    if selected_pack is not None and workspace_build.is_file():
        build_scripts.append(workspace_build.relative_to(root).as_posix())
    build_scripts = sorted(set(build_scripts))
    if build_scripts:
        raise RustAssetError(
            f"Rust behavior build scripts are forbidden; harnesses import canonical bytes: {build_scripts}"
        )

    expected_harnesses = {
        snippet.harness
        for snippet in inventory.executable_snippets
        if selected_pack is None or _belongs_to_pack(snippet.path, selected_pack)
    }
    if actual_harnesses != expected_harnesses:
        raise RustAssetError(
            "Rust harness module mismatch; "
            f"missing={sorted(expected_harnesses - actual_harnesses)}, "
            f"unclassified={sorted(actual_harnesses - expected_harnesses)}"
        )
    for snippet in inventory.executable_snippets:
        if selected_pack is not None and not _belongs_to_pack(snippet.path, selected_pack):
            continue
        pack = _pack_for_asset(snippet.path, packs)
        member = members[pack.id]
        member_root = (root / member.manifest).parent
        harness_path = root / snippet.harness
        if harness_path.parent != member_root / "src":
            raise RustAssetError(
                f"{snippet.harness} must belong to the {pack.id} behavior harness member"
            )
        repository_prefix = "/".join(".." for _part in member_root.relative_to(root).parts)
        harness_text = harness_path.read_text(encoding="utf-8")
        if not _has_direct_canonical_include(
            harness_text,
            snippet.path,
            repository_prefix=repository_prefix,
        ):
            raise RustAssetError(
                f"{snippet.harness} does not directly import canonical snippet {snippet.path}"
            )
        lib_text = (member_root / "src" / "lib.rs").read_text(encoding="utf-8")
        module = harness_path.stem
        if not re.search(rf"(?m)^mod {re.escape(module)};$", lib_text):
            raise RustAssetError(
                f"{member.manifest}: src/lib.rs does not declare module {module!r}"
            )
    return packs


def validate_inventory(
    root: Path,
    inventory: RustAssetInventory,
    *,
    selected_pack: Pack | None = None,
) -> tuple[str, ...]:
    discovered = discover_rust_assets(root)
    actual = {
        relative
        for relative in discovered
        if selected_pack is None or _belongs_to_pack(relative, selected_pack)
    }
    snippets = tuple(
        snippet
        for snippet in inventory.executable_snippets
        if selected_pack is None or _belongs_to_pack(snippet.path, selected_pack)
    )
    fragments = tuple(
        relative
        for relative in inventory.syntax_only_fragments
        if selected_pack is None or _belongs_to_pack(relative, selected_pack)
    )
    projects = tuple(
        project
        for project in inventory.complete_projects
        if selected_pack is None or _belongs_to_pack(project.path, selected_pack)
    )
    classified: list[str] = [snippet.path for snippet in snippets]
    classified.extend(fragments)
    for project in projects:
        project_root = root / project.path
        manifest = project_root / "Cargo.toml"
        if not manifest.is_file():
            raise RustAssetError(f"complete project is missing Cargo.toml: {project.path}")
        classified.extend(
            path.relative_to(root).as_posix()
            for path in sorted(project_root.rglob("*"))
            if path.is_file() and path.suffix.lower() in ASSET_SUFFIXES
        )
    duplicates = sorted(path for path in set(classified) if classified.count(path) > 1)
    if duplicates:
        raise RustAssetError(f"Rust assets are classified more than once: {duplicates}")
    classified_set = set(classified)
    missing = sorted(classified_set - actual)
    unclassified = sorted(actual - classified_set)
    if missing or unclassified:
        raise RustAssetError(
            f"Rust asset inventory mismatch; missing={missing}, unclassified={unclassified}"
        )
    for relative in (
        inventory.behavior_manifest,
        inventory.behavior_lockfile,
        inventory.cargo_policy_manifest,
        inventory.cargo_policy_lockfile,
    ):
        if not (root / relative).is_file():
            raise RustAssetError(f"missing Rust behavior harness file: {relative}")
    harnesses = [snippet.harness for snippet in snippets]
    duplicate_harnesses = sorted(path for path in set(harnesses) if harnesses.count(path) > 1)
    if duplicate_harnesses:
        raise RustAssetError(f"executable snippets share harness modules: {duplicate_harnesses}")
    _validate_behavior_workspace(root, inventory, selected_pack=selected_pack)
    return tuple(sorted(actual))


def select_rust_pack(
    root: Path,
    inventory: RustAssetInventory,
    pack_id: str | None,
) -> tuple[Pack, BehaviorHarnessMember] | None:
    """Resolve an optional Rust pack to its one behavior-workspace member."""

    if pack_id is None:
        return None
    matches: list[Pack] = []
    if pack_id.startswith("rust-"):
        subject = pack_id.removeprefix("rust-")
        manifest = root / "packs" / "rust" / subject / "skillpack.yaml"
        if manifest.is_file():
            pack = Pack(root=root, path=manifest.parent, raw=_load_repository_yaml(manifest, root))
            if pack.id == pack_id and pack.language == "rust" and pack.subject == subject:
                matches = [pack]
    if not matches:
        packs = discover_packs(root)
        matches = [pack for pack in packs if pack.id == pack_id]
    if not matches:
        known = ", ".join(sorted(pack.id for pack in discover_packs(root))) or "(none)"
        raise RustAssetError(f"unknown pack {pack_id!r}; known packs: {known}")
    pack = matches[0]
    if pack.language != "rust":
        raise RustAssetError(
            f"pack {pack_id!r} is not a Rust pack and cannot use the Rust asset gate"
        )
    members = [member for member in inventory.behavior_members if member.pack_id == pack.id]
    if len(members) != 1:
        raise RustAssetError(
            f"Rust pack {pack.id!r} must map to exactly one behavior harness member"
        )
    return pack, members[0]


def _belongs_to_pack(relative: str, pack: Pack) -> bool:
    return relative == pack.relative_path or relative.startswith(f"{pack.relative_path}/")


def parse_semver(value: str) -> tuple[int, int, int]:
    match = re.search(r"(?<![0-9])(\d+)\.(\d+)(?:\.(\d+))?", value)
    if not match:
        raise RustAssetError(f"could not parse a semantic version from {value!r}")
    return tuple(int(part or 0) for part in match.groups())  # type: ignore[return-value]


def _run(
    command: Sequence[str],
    *,
    root: Path,
    environment: dict[str, str] | None = None,
    timeout: int = 180,
) -> str:
    try:
        completed = subprocess.run(
            list(command),
            cwd=root,
            env=environment,
            text=True,
            capture_output=True,
            check=False,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RustAssetError(f"could not run {' '.join(command)}: {exc}") from exc
    if completed.returncode:
        output = "\n".join(part for part in (completed.stdout, completed.stderr) if part).strip()
        raise RustAssetError(
            f"command failed ({completed.returncode}): {' '.join(command)}\n{output}"
        )
    return completed.stdout


def _run_expect_failure(
    command: Sequence[str],
    *,
    root: Path,
    environment: dict[str, str],
    sentinel: str,
    timeout: int = 180,
) -> None:
    try:
        completed = subprocess.run(
            list(command),
            cwd=root,
            env=environment,
            text=True,
            capture_output=True,
            check=False,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RustAssetError(f"could not run {' '.join(command)}: {exc}") from exc
    if completed.returncode == 0:
        raise RustAssetError(f"Cargo policy trap unexpectedly passed: {' '.join(command)}")
    output = "\n".join(part for part in (completed.stdout, completed.stderr) if part)
    sentinel_hits = set(re.findall(r"GENAPTIC_CARGO_POLICY_[A-Z_]+_SENTINEL", output))
    if sentinel_hits != {sentinel}:
        raise RustAssetError(
            "Cargo policy trap did not fail for exactly the expected policy: "
            f"expected={sentinel!r}, found={sorted(sentinel_hits)}, command={' '.join(command)}"
        )


def _required_tool(name: str) -> str:
    executable = shutil.which(name)
    if not executable:
        raise RustAssetError(
            f"required Rust development tool {name!r} is unavailable; install it explicitly"
        )
    return executable


def verify_toolchain(root: Path) -> dict[str, str]:
    tools = {name: _required_tool(name) for name in ("rustc", "cargo", "rustfmt")}
    versions = {
        name: _run([executable, "--version"], root=root, timeout=30).strip()
        for name, executable in tools.items()
    }
    if parse_semver(versions["rustc"]) < MINIMUM_RUST:
        raise RustAssetError(f"Rust 1.85.0 or newer is required; found {versions['rustc']}")
    if parse_semver(versions["cargo"]) < MINIMUM_RUST:
        raise RustAssetError(f"Cargo 1.85.0 or newer is required; found {versions['cargo']}")
    return {**tools, **{f"{name}Version": value for name, value in versions.items()}}


def _asset_snapshot(root: Path, paths: Sequence[str]) -> dict[str, tuple[bytes, int]]:
    return {
        relative: (
            (root / relative).read_bytes(),
            stat.S_IMODE((root / relative).stat().st_mode),
        )
        for relative in paths
    }


def _cargo_environment(cargo_home: Path, target_dir: Path, *, offline: bool) -> dict[str, str]:
    environment = os.environ.copy()
    environment.update(
        {
            "CARGO_HOME": str(cargo_home),
            "CARGO_TARGET_DIR": str(target_dir),
            "CARGO_INCREMENTAL": "0",
            "CARGO_TERM_COLOR": "never",
        }
    )
    if offline:
        environment["CARGO_NET_OFFLINE"] = "true"
    else:
        environment.pop("CARGO_NET_OFFLINE", None)
    return environment


def _check_toml(root: Path, assets: Sequence[str]) -> None:
    for relative in assets:
        if relative.endswith(".toml"):
            try:
                tomllib.loads((root / relative).read_text(encoding="utf-8"))
            except (OSError, UnicodeError, tomllib.TOMLDecodeError) as exc:
                raise RustAssetError(f"invalid TOML asset {relative}: {exc}") from exc


def _build_project_once(
    root: Path,
    project: ProjectContract,
    cargo: str,
) -> bytes:
    with tempfile.TemporaryDirectory(prefix="genaptic-rust-project-") as temporary_name:
        temporary = Path(temporary_name)
        project_copy = temporary / "project"
        shutil.copytree(root / project.path, project_copy, copy_function=shutil.copy2)
        cargo_home = temporary / "cargo-home"
        cargo_home.mkdir()
        environment = _cargo_environment(cargo_home, temporary / "target", offline=True)
        manifest = project_copy / "Cargo.toml"
        common = ["--manifest-path", str(manifest), "--color", "never"]
        _run(
            [cargo, *project.cargo_args, "--offline", *common],
            root=project_copy,
            environment=environment,
        )
        lockfile = project_copy / "Cargo.lock"
        if not lockfile.is_file():
            raise RustAssetError(f"Cargo did not create a scratch lockfile for {project.path}")
        locked = lockfile.read_bytes()
        _run(
            [cargo, *project.cargo_args, "--frozen", *common],
            root=project_copy,
            environment=environment,
        )
        if lockfile.read_bytes() != locked:
            raise RustAssetError(f"frozen Cargo check changed the lockfile for {project.path}")
        return locked


def _check_cargo_policy_trap(root: Path, inventory: RustAssetInventory, cargo: str) -> None:
    source = (root / inventory.cargo_policy_manifest).parent
    with tempfile.TemporaryDirectory(prefix="genaptic-rust-policy-") as temporary_name:
        temporary = Path(temporary_name)
        fixture = temporary / "fixture"
        shutil.copytree(source, fixture, copy_function=shutil.copy2)
        cargo_home = temporary / "cargo-home"
        cargo_home.mkdir()
        environment = _cargo_environment(cargo_home, temporary / "target", offline=True)
        manifest = fixture / "Cargo.toml"
        common = ["--frozen", "--manifest-path", str(manifest), "--color", "never"]
        _run([cargo, "test", *common], root=fixture, environment=environment)
        _run_expect_failure(
            [cargo, "test", "--all-features", *common],
            root=fixture,
            environment=environment,
            sentinel="GENAPTIC_CARGO_POLICY_ALL_FEATURES_SENTINEL",
        )
        _run_expect_failure(
            [cargo, "test", "--workspace", *common],
            root=fixture,
            environment=environment,
            sentinel="GENAPTIC_CARGO_POLICY_WORKSPACE_SENTINEL",
        )


def _replace_workspace_member_array(
    manifest_text: str,
    *,
    key: str,
    member_name: str,
    required: bool,
) -> str:
    """Replace one array in the root ``[workspace]`` table.

    Cargo has no command-line option that prevents it from parsing malformed
    unselected workspace members. The selected-pack gate therefore materializes
    a one-member workspace. Only the temporary copy is rewritten.
    """

    workspace_header = re.search(r"(?m)^\[workspace\][ \t]*(?:#.*)?$", manifest_text)
    if workspace_header is None:
        raise RustAssetError("Rust behavior harness root must contain [workspace]")
    next_table = re.search(r"(?m)^\[\[?[^\r\n]+", manifest_text[workspace_header.end() :])
    section_end = (
        workspace_header.end() + next_table.start()
        if next_table is not None
        else len(manifest_text)
    )
    section = manifest_text[workspace_header.end() : section_end]
    assignment = re.compile(
        rf"(?ms)^(?P<indent>[ \t]*){re.escape(key)}[ \t]*=[ \t]*"
        r"\[(?P<body>.*?)\]"
    )
    matches = list(assignment.finditer(section))
    if not matches:
        if required:
            raise RustAssetError(f"Rust behavior workspace must declare {key}")
        return manifest_text
    if len(matches) != 1:
        raise RustAssetError(f"Rust behavior workspace must declare {key} exactly once")
    match = matches[0]
    replacement = f"{match.group('indent')}{key} = [{json.dumps(member_name)}]"
    rewritten_section = section[: match.start()] + replacement + section[match.end() :]
    return manifest_text[: workspace_header.end()] + rewritten_section + manifest_text[section_end:]


@contextmanager
def _behavior_harness_scope(
    root: Path,
    inventory: RustAssetInventory,
    selection: tuple[Pack, BehaviorHarnessMember] | None,
) -> Iterator[tuple[Path, Path]]:
    """Yield a Cargo manifest and cwd for the requested harness scope.

    Full checks use the committed workspace directly. Selected checks copy only
    the chosen direct member into a temporary sibling workspace. Keeping the
    temporary workspace at the same path depth preserves every canonical
    ``include!(concat!(env!("CARGO_MANIFEST_DIR"), ...))`` path.
    """

    workspace_manifest = root / inventory.behavior_manifest
    workspace_root = workspace_manifest.parent
    if selection is None:
        yield workspace_manifest, workspace_root
        return

    _pack, member = selection
    member_manifest = root / member.manifest
    member_root = member_manifest.parent
    try:
        member_relative = member_root.relative_to(workspace_root)
    except ValueError as exc:  # pragma: no cover - enforced by inventory validation
        raise RustAssetError(f"behavior member escapes its workspace: {member.manifest}") from exc
    if len(member_relative.parts) != 1:
        raise RustAssetError(f"behavior member must be a direct workspace child: {member.manifest}")
    member_name = member_relative.as_posix()

    workspace_parent = workspace_root.parent
    with tempfile.TemporaryDirectory(
        prefix=".genaptic-selected-rust-harness-",
        dir=workspace_parent,
    ) as temporary_name:
        isolated_root = Path(temporary_name)
        isolated_member = isolated_root / member_name
        shutil.copytree(
            member_root,
            isolated_member,
            copy_function=shutil.copy2,
            ignore=shutil.ignore_patterns("Cargo.lock", "target"),
        )
        original_depth = len(member_root.relative_to(root).parts)
        isolated_depth = len(isolated_member.relative_to(root).parts)
        if isolated_depth != original_depth:  # pragma: no cover - construction invariant
            raise RustAssetError("isolated behavior member changed canonical include-path depth")

        try:
            manifest_text = workspace_manifest.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise RustAssetError(
                f"cannot read Rust behavior workspace manifest {inventory.behavior_manifest}: {exc}"
            ) from exc
        manifest_text = _replace_workspace_member_array(
            manifest_text,
            key="members",
            member_name=member_name,
            required=True,
        )
        manifest_text = _replace_workspace_member_array(
            manifest_text,
            key="default-members",
            member_name=member_name,
            required=False,
        )
        isolated_manifest = isolated_root / "Cargo.toml"
        isolated_manifest.write_text(manifest_text, encoding="utf-8", newline="\n")

        canonical_lock = root / member.lockfile
        isolated_lock = isolated_root / "Cargo.lock"
        shutil.copy2(canonical_lock, isolated_lock)
        lock_preimage = canonical_lock.read_bytes()
        try:
            yield isolated_manifest, isolated_root
        finally:
            if canonical_lock.read_bytes() != lock_preimage:
                raise RustAssetError(f"selected Rust harness mutated {member.lockfile}")
            if isolated_lock.read_bytes() != lock_preimage:
                raise RustAssetError(
                    f"selected Rust harness lock drifted from committed {member.lockfile}"
                )


def bootstrap_harness(root: Path, cargo_home: Path, *, pack_id: str | None = None) -> None:
    inventory = load_inventory(root)
    selection = select_rust_pack(root, inventory, pack_id)
    validate_inventory(
        root,
        inventory,
        selected_pack=selection[0] if selection is not None else None,
    )
    tools = verify_toolchain(root)
    cargo_home.mkdir(parents=True, exist_ok=True)
    environment = _cargo_environment(cargo_home, cargo_home / "target", offline=False)
    with _behavior_harness_scope(root, inventory, selection) as (manifest, workspace_root):
        _run(
            [
                tools["cargo"],
                "fetch",
                "--locked",
                "--manifest-path",
                str(manifest),
                "--color",
                "never",
            ],
            root=workspace_root,
            environment=environment,
            timeout=300,
        )
    scope = f" for {selection[0].id}" if selection else ""
    print(f"locked Rust harness dependencies fetched into {cargo_home}{scope}")


def check_rust_assets(root: Path, cargo_home: Path, *, pack_id: str | None = None) -> None:
    inventory = load_inventory(root)
    selection = select_rust_pack(root, inventory, pack_id)
    assets = validate_inventory(
        root,
        inventory,
        selected_pack=selection[0] if selection is not None else None,
    )
    tools = verify_toolchain(root)
    before = _asset_snapshot(root, assets)

    scoped_assets = assets
    rust_sources = [relative for relative in scoped_assets if relative.endswith(".rs")]
    _run(
        [
            tools["rustfmt"],
            "--edition",
            "2024",
            "--check",
            *rust_sources,
        ],
        root=root,
    )
    _check_toml(root, scoped_assets)

    projects = (
        inventory.complete_projects
        if selection is None
        else tuple(
            project
            for project in inventory.complete_projects
            if _belongs_to_pack(project.path, selection[0])
        )
    )
    for project in projects:
        first = _build_project_once(root, project, tools["cargo"])
        second = _build_project_once(root, project, tools["cargo"])
        if first != second:
            raise RustAssetError(f"nondeterministic scratch lockfile for {project.path}")
    _check_cargo_policy_trap(root, inventory, tools["cargo"])

    if not cargo_home.is_dir():
        raise RustAssetError(
            f"Rust harness cache is unavailable at {cargo_home}; run `make rust-bootstrap`"
        )
    with tempfile.TemporaryDirectory(prefix="genaptic-rust-harness-target-") as temporary_name:
        environment = _cargo_environment(cargo_home, Path(temporary_name), offline=True)
        with _behavior_harness_scope(root, inventory, selection) as (manifest, workspace_root):
            _run(
                [
                    tools["cargo"],
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

    after = _asset_snapshot(root, assets)
    if after != before:
        changed = sorted(path for path in assets if before.get(path) != after.get(path))
        raise RustAssetError(f"Rust asset check mutated canonical files: {changed}")
    residue = sorted(
        path.relative_to(root).as_posix()
        for path in (root / "packs" / "rust").rglob("*")
        if path.name == "Cargo.lock" or (path.is_dir() and path.name == "target")
    )
    if residue:
        raise RustAssetError(f"Rust asset check left canonical build residue: {residue}")
    print(
        "Rust assets passed: "
        f"{len(rust_sources)} formatted sources, {len(projects)} offline projects, "
        f"locked behavior harness ({selection[0].id if selection else 'full workspace'})"
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Check canonical Rust assets without modifying them. Normal checks are offline; "
            "--bootstrap explicitly fetches the locked harness dependencies."
        )
    )
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--cargo-home",
        type=Path,
        help="isolated Cargo cache populated explicitly by --bootstrap",
    )
    parser.add_argument(
        "--bootstrap",
        action="store_true",
        help="explicitly fetch the locked behavior-harness dependencies; never installs Rust",
    )
    parser.add_argument(
        "--pack",
        help="check one Rust pack member plus repository-wide Rust inventory invariants",
    )
    args = parser.parse_args(argv)
    root = args.root.resolve()
    cargo_home = (
        args.cargo_home.resolve()
        if args.cargo_home
        else (root / ".venv" / "rust-cargo-home").resolve()
    )
    try:
        if args.bootstrap:
            bootstrap_harness(root, cargo_home, pack_id=args.pack)
        else:
            check_rust_assets(root, cargo_home, pack_id=args.pack)
    except RustAssetError as exc:
        parser.exit(1, f"error: {exc}\n")
    return 0
