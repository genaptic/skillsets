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
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

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
class RustAssetInventory:
    minimum_rust_version: str
    complete_projects: tuple[ProjectContract, ...]
    executable_snippets: tuple[ExecutableSnippet, ...]
    syntax_only_fragments: tuple[str, ...]
    behavior_manifest: str
    behavior_lockfile: str
    cargo_policy_manifest: str
    cargo_policy_lockfile: str


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
        required={"manifest", "lockfile"},
        label="behaviorHarness",
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
    )


def discover_rust_assets(root: Path) -> tuple[str, ...]:
    rust_root = root / "packs" / "rust"
    return tuple(
        path.relative_to(root).as_posix()
        for path in sorted(rust_root.rglob("*"))
        if path.is_file() and path.suffix.lower() in ASSET_SUFFIXES
    )


def _has_direct_canonical_include(harness_text: str, snippet_path: str) -> bool:
    expected_path = re.escape(f"/../../{snippet_path}")
    pattern = (
        r'include!\s*\(\s*concat!\s*\(\s*env!\s*\(\s*"CARGO_MANIFEST_DIR"\s*\)'
        rf'\s*,\s*"{expected_path}"\s*,?\s*\)\s*\)\s*;'
    )
    return re.search(pattern, harness_text) is not None


def validate_inventory(root: Path, inventory: RustAssetInventory) -> tuple[str, ...]:
    actual = set(discover_rust_assets(root))
    classified: list[str] = [snippet.path for snippet in inventory.executable_snippets]
    classified.extend(inventory.syntax_only_fragments)
    for project in inventory.complete_projects:
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
    harnesses = [snippet.harness for snippet in inventory.executable_snippets]
    duplicate_harnesses = sorted(path for path in set(harnesses) if harnesses.count(path) > 1)
    if duplicate_harnesses:
        raise RustAssetError(f"executable snippets share harness modules: {duplicate_harnesses}")
    harness_root = (root / inventory.behavior_manifest).parent / "src"
    build_script = harness_root.parent / "build.rs"
    if build_script.exists():
        raise RustAssetError(
            f"{build_script.relative_to(root)} is forbidden; harnesses must import canonical bytes"
        )
    actual_harnesses = {
        path.relative_to(root).as_posix()
        for path in harness_root.glob("*.rs")
        if path.name != "lib.rs"
    }
    expected_harnesses = set(harnesses)
    if actual_harnesses != expected_harnesses:
        raise RustAssetError(
            "Rust harness module mismatch; "
            f"missing={sorted(expected_harnesses - actual_harnesses)}, "
            f"unclassified={sorted(actual_harnesses - expected_harnesses)}"
        )
    lib_text = (harness_root / "lib.rs").read_text(encoding="utf-8")
    for snippet in inventory.executable_snippets:
        harness_path = root / snippet.harness
        harness_text = harness_path.read_text(encoding="utf-8")
        if not _has_direct_canonical_include(harness_text, snippet.path):
            raise RustAssetError(
                f"{snippet.harness} does not directly import canonical snippet {snippet.path}"
            )
        module = harness_path.stem
        if not re.search(rf"(?m)^mod {re.escape(module)};$", lib_text):
            raise RustAssetError(f"behavior harness lib.rs does not declare module {module!r}")
    return tuple(sorted(actual))


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


def bootstrap_harness(root: Path, cargo_home: Path) -> None:
    inventory = load_inventory(root)
    validate_inventory(root, inventory)
    tools = verify_toolchain(root)
    cargo_home.mkdir(parents=True, exist_ok=True)
    environment = _cargo_environment(cargo_home, cargo_home / "target", offline=False)
    _run(
        [
            tools["cargo"],
            "fetch",
            "--locked",
            "--manifest-path",
            str(root / inventory.behavior_manifest),
            "--color",
            "never",
        ],
        root=root,
        environment=environment,
        timeout=300,
    )
    print(f"locked Rust harness dependencies fetched into {cargo_home}")


def check_rust_assets(root: Path, cargo_home: Path) -> None:
    inventory = load_inventory(root)
    assets = validate_inventory(root, inventory)
    tools = verify_toolchain(root)
    before = _asset_snapshot(root, assets)

    rust_sources = [relative for relative in assets if relative.endswith(".rs")]
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
    _check_toml(root, assets)

    for project in inventory.complete_projects:
        first = _build_project_once(root, project, tools["cargo"])
        second = _build_project_once(root, project, tools["cargo"])
        if first != second:
            raise RustAssetError(f"nondeterministic scratch lockfile for {project.path}")
    _check_cargo_policy_trap(root, inventory, tools["cargo"])

    if not cargo_home.is_dir():
        raise RustAssetError(
            f"Rust harness cache is unavailable at {cargo_home}; run `make rust-bootstrap`"
        )
    with tempfile.TemporaryDirectory(prefix="genaptic-rust-harness-") as temporary_name:
        environment = _cargo_environment(cargo_home, Path(temporary_name) / "target", offline=True)
        _run(
            [
                tools["cargo"],
                "test",
                "--frozen",
                "--manifest-path",
                str(root / inventory.behavior_manifest),
                "--color",
                "never",
            ],
            root=root,
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
        f"{len(rust_sources)} formatted sources, {len(inventory.complete_projects)} "
        "offline projects, locked behavior harness"
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
    args = parser.parse_args(argv)
    root = args.root.resolve()
    cargo_home = (
        args.cargo_home.resolve()
        if args.cargo_home
        else (root / ".venv" / "rust-cargo-home").resolve()
    )
    try:
        if args.bootstrap:
            bootstrap_harness(root, cargo_home)
        else:
            check_rust_assets(root, cargo_home)
    except RustAssetError as exc:
        parser.exit(1, f"error: {exc}\n")
    return 0
