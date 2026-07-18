#!/usr/bin/env python3
"""Safely preview or scaffold one skill inside an existing skillpack.

Requires Python 3.11 and only the standard library. Preview is read-only and prints a
repository-relative plan to stdout. Apply writes one canonical skill directory plus the
target manifest and compatibility inventory; it requires the reviewed plan digest. The
helper never uses the network, runs external commands, installs dependencies, generates
client adapters, or performs Git/release operations. Multi-file crash durability is
bounded: inspect the worktree before retrying an interrupted apply.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import sys
import tempfile
import unicodedata
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

KEBAB_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SEMVER_RE = re.compile(
    r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
    r"(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$"
)
MAX_REQUEST_BYTES = 1024 * 1024
MAX_JSON_DEPTH = 64
OPERATIONS = {
    "network": {"none", "optional", "required"},
    "filesystem": {"read-only", "explicit-output", "project-write", "system-write"},
    "commandExecution": {"none", "optional-explicit", "required"},
    "externalWrites": {"none", "optional-explicit", "required"},
}
OPERATION_RANKS = {
    "network": {"none": 0, "optional": 1, "required": 2},
    "filesystem": {"read-only": 0, "explicit-output": 1, "project-write": 2, "system-write": 3},
    "commandExecution": {"none": 0, "optional-explicit": 1, "required": 2},
    "externalWrites": {"none": 0, "optional-explicit": 1, "required": 2},
}
RESERVED_NAMES = {
    "con",
    "prn",
    "aux",
    "nul",
    *(f"com{i}" for i in range(1, 10)),
    *(f"lpt{i}" for i in range(1, 10)),
}
REJECTED_NAMES = {
    "__pycache__",
    ".cache",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".DS_Store",
}


class ScaffoldError(ValueError):
    """Raised for an invalid or unsafe scaffold request."""


@dataclass(frozen=True)
class Pack:
    id: str
    version: str
    path: Path
    skills: tuple[str, ...]
    source_sha: str | None
    operations: dict[str, str]


def _reject_constant(value: str) -> None:
    raise ScaffoldError(f"invalid non-finite JSON number: {value}")


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ScaffoldError(f"duplicate JSON key: {key!r}")
        result[key] = value
    return result


def _check_depth(value: Any, depth: int = 0) -> None:
    if depth > MAX_JSON_DEPTH:
        raise ScaffoldError(f"JSON nesting exceeds {MAX_JSON_DEPTH} levels")
    if isinstance(value, dict):
        for item in value.values():
            _check_depth(item, depth + 1)
    elif isinstance(value, list):
        for item in value:
            _check_depth(item, depth + 1)


def load_strict_json(path: Path) -> Any:
    safe_regular_file(path, label="request")
    size = path.stat().st_size
    if size > MAX_REQUEST_BYTES:
        raise ScaffoldError(f"request exceeds {MAX_REQUEST_BYTES} bytes")
    try:
        text = path.read_bytes().decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise ScaffoldError(f"request is not valid UTF-8: {exc}") from exc
    try:
        value = json.loads(text, object_pairs_hook=_pairs, parse_constant=_reject_constant)
    except json.JSONDecodeError as exc:
        raise ScaffoldError(f"invalid JSON request: {exc}") from exc
    _check_depth(value)
    return value


def expect_object(
    value: Any, *, label: str, required: set[str], optional: set[str] = set()
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ScaffoldError(f"{label} must be an object")
    missing = sorted(required - value.keys())
    unknown = sorted(value.keys() - required - optional)
    if missing:
        raise ScaffoldError(f"{label} is missing required fields: {', '.join(missing)}")
    if unknown:
        raise ScaffoldError(f"{label} has unknown fields: {', '.join(unknown)}")
    return value


def text_field(value: Any, *, label: str, minimum: int, maximum: int) -> str:
    if not isinstance(value, str) or value != value.strip() or not minimum <= len(value) <= maximum:
        raise ScaffoldError(
            f"{label} must be a trimmed string of {minimum} to {maximum} characters"
        )
    return value


def string_list(
    value: Any, *, label: str, minimum: int, maximum: int, item_min: int, item_max: int
) -> list[str]:
    if not isinstance(value, list) or not minimum <= len(value) <= maximum:
        raise ScaffoldError(f"{label} must contain {minimum} to {maximum} items")
    result = [
        text_field(item, label=f"{label}[]", minimum=item_min, maximum=item_max) for item in value
    ]
    if len(result) != len(set(result)):
        raise ScaffoldError(f"{label} must not contain duplicates")
    return result


def validate_operations(value: Any, *, label: str = "operations") -> dict[str, str]:
    data = expect_object(value, label=label, required=set(OPERATIONS))
    result: dict[str, str] = {}
    for key, allowed in OPERATIONS.items():
        item = data[key]
        if not isinstance(item, str) or item not in allowed:
            raise ScaffoldError(f"{label}.{key} must be one of: {', '.join(sorted(allowed))}")
        result[key] = item
    return result


def validate_scope(value: Any) -> dict[str, Any]:
    data = expect_object(
        value, label="scope", required={"useWhen", "doNotUseWhen", "supportedEnvironments"}
    )
    string_list(
        data["useWhen"], label="scope.useWhen", minimum=2, maximum=20, item_min=10, item_max=1000
    )
    string_list(
        data["doNotUseWhen"],
        label="scope.doNotUseWhen",
        minimum=2,
        maximum=20,
        item_min=10,
        item_max=1000,
    )
    string_list(
        data["supportedEnvironments"],
        label="scope.supportedEnvironments",
        minimum=1,
        maximum=20,
        item_min=3,
        item_max=500,
    )
    return data


def validate_examples(value: Any) -> dict[str, Any]:
    data = expect_object(value, label="examples", required={"shouldTrigger", "shouldNotTrigger"})
    for key in ("shouldTrigger", "shouldNotTrigger"):
        string_list(
            data[key], label=f"examples.{key}", minimum=2, maximum=20, item_min=20, item_max=2000
        )
    return data


def validate_sources(value: Any) -> list[str]:
    if not isinstance(value, list) or len(value) > 20:
        raise ScaffoldError("userSources must contain at most 20 items")
    if not all(isinstance(source, str) for source in value):
        raise ScaffoldError("userSources entries must be strings")
    result = list(value)
    if len(result) != len(set(result)):
        raise ScaffoldError("userSources must not contain duplicates")
    for source in result:
        parsed = urlsplit(source)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.netloc
            or parsed.username is not None
            or parsed.password is not None
            or any(ch.isspace() for ch in source)
        ):
            raise ScaffoldError(
                "userSources entries must be HTTP(S) URLs without credentials or whitespace"
            )
    return result


def validate_source_requirements(
    value: Any, *, label: str = "sourceRequirements"
) -> dict[str, Any]:
    data = expect_object(value, label=label, required={"freshness", "requiredAuthorities"})
    text_field(data["freshness"], label=f"{label}.freshness", minimum=10, maximum=1000)
    string_list(
        data["requiredAuthorities"],
        label=f"{label}.requiredAuthorities",
        minimum=1,
        maximum=12,
        item_min=3,
        item_max=300,
    )
    return data


def validate_openai(value: Any, *, skill: str, label: str = "openai") -> dict[str, str]:
    data = expect_object(
        value, label=label, required={"displayName", "shortDescription", "defaultPrompt"}
    )
    result = {
        "displayName": text_field(
            data["displayName"], label=f"{label}.displayName", minimum=3, maximum=80
        ),
        "shortDescription": text_field(
            data["shortDescription"], label=f"{label}.shortDescription", minimum=25, maximum=64
        ),
        "defaultPrompt": text_field(
            data["defaultPrompt"], label=f"{label}.defaultPrompt", minimum=20, maximum=300
        ),
    }
    if f"${skill}" not in result["defaultPrompt"]:
        raise ScaffoldError(f"{label}.defaultPrompt must explicitly name ${skill}")
    return result


def validate_request(request: Any) -> dict[str, Any]:
    required = {
        "schemaVersion",
        "skillName",
        "packId",
        "expectedPackVersion",
        "details",
        "scope",
        "expectedOutput",
        "successCriteria",
        "examples",
        "nearestNeighbor",
        "constraints",
        "operations",
        "sourceRequirements",
        "openai",
    }
    data = expect_object(request, label="request", required=required, optional={"userSources"})
    if type(data["schemaVersion"]) is not int or data["schemaVersion"] != 1:
        raise ScaffoldError("request.schemaVersion must be integer 1")
    for key in ("skillName", "packId", "nearestNeighbor"):
        value = text_field(data[key], label=key, minimum=1, maximum=64)
        if not KEBAB_RE.fullmatch(value):
            raise ScaffoldError(f"{key} must be lowercase kebab-case")
    version = data["expectedPackVersion"]
    if not isinstance(version, str) or not SEMVER_RE.fullmatch(version):
        raise ScaffoldError("expectedPackVersion must be Semantic Versioning")
    text_field(data["details"], label="details", minimum=40, maximum=12000)
    validate_scope(data["scope"])
    text_field(data["expectedOutput"], label="expectedOutput", minimum=20, maximum=3000)
    string_list(
        data["successCriteria"],
        label="successCriteria",
        minimum=2,
        maximum=20,
        item_min=10,
        item_max=1000,
    )
    validate_examples(data["examples"])
    string_list(
        data["constraints"], label="constraints", minimum=1, maximum=20, item_min=3, item_max=1000
    )
    validate_operations(data["operations"])
    validate_source_requirements(data["sourceRequirements"])
    validate_openai(data["openai"], skill=data["skillName"])
    validate_sources(data.get("userSources", []))
    return data


def _path_component_safe(name: str) -> bool:
    folded = unicodedata.normalize("NFC", name).casefold()
    stem = folded.split(".", 1)[0]
    return (
        name not in REJECTED_NAMES
        and stem not in RESERVED_NAMES
        and not name.endswith((" ", "."))
        and not any(ord(char) < 32 or char in '<>:"\\|?*' for char in name)
        and not name.endswith((".pyc", ".pyo", ".swp", "~"))
        and not re.search(
            r"(?i)(?:^|[._-])(secret|credential|private[-_]?key|id_rsa|id_ed25519)(?:$|[._-])", name
        )
    )


def safe_regular_file(path: Path, *, label: str) -> None:
    current = path
    while True:
        if current.is_symlink():
            raise ScaffoldError(f"{label} contains a symlink component")
        if current.parent == current:
            break
        current = current.parent
    try:
        mode = path.lstat().st_mode
    except FileNotFoundError as exc:
        raise ScaffoldError(f"{label} does not exist") from exc
    if not stat.S_ISREG(mode):
        raise ScaffoldError(f"{label} must be a regular file")


def inspect_tree(path: Path, *, label: str) -> list[Path]:
    if path.is_symlink() or not path.is_dir():
        raise ScaffoldError(f"{label} must be a real directory")
    files: list[Path] = []
    seen: dict[str, str] = {}
    for candidate in sorted(path.rglob("*"), key=lambda item: item.as_posix()):
        relative = candidate.relative_to(path).as_posix()
        normalized = unicodedata.normalize("NFC", relative).casefold()
        prior = seen.get(normalized)
        if prior is not None and prior != relative:
            raise ScaffoldError(
                f"{label} has a case/Unicode path collision: {prior!r} and {relative!r}"
            )
        seen[normalized] = relative
        if not all(_path_component_safe(part) for part in candidate.relative_to(path).parts):
            raise ScaffoldError(f"{label} contains a rejected path: {relative}")
        mode = candidate.lstat().st_mode
        if stat.S_ISLNK(mode):
            raise ScaffoldError(f"{label} contains a symlink: {relative}")
        if stat.S_ISDIR(mode):
            continue
        if not stat.S_ISREG(mode):
            raise ScaffoldError(f"{label} contains a non-regular file: {relative}")
        files.append(candidate)
    return files


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_digest(plan: dict[str, Any]) -> str:
    content = json.dumps(plan, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    return hashlib.sha256(content).hexdigest()


def plan_with_digest(plan: dict[str, Any]) -> dict[str, Any]:
    return {**plan, "planDigest": canonical_digest(plan)}


def parse_manifest(path: Path) -> Pack:
    lines = path.read_text(encoding="utf-8").splitlines()
    values: dict[str, str] = {}
    skills: list[str] = []
    in_skills = False
    in_operations = False
    operations: dict[str, str] = {}
    for raw in lines:
        if raw == "skills:":
            in_skills = True
            in_operations = False
            continue
        if raw == "operations:":
            in_operations = True
            in_skills = False
            continue
        if in_skills:
            if raw.startswith("- "):
                skills.append(raw[2:].strip().strip("'\""))
                continue
            if raw and not raw.startswith((" ", "\t")):
                in_skills = False
        if in_operations:
            nested = re.match(
                r"^\s{2}(network|filesystem|command-execution|external-writes):\s*(.+?)\s*$", raw
            )
            if nested:
                key = {
                    "command-execution": "commandExecution",
                    "external-writes": "externalWrites",
                }.get(nested.group(1), nested.group(1))
                operations[key] = nested.group(2).strip().strip("'\"")
                continue
            if raw and not raw.startswith((" ", "\t")):
                in_operations = False
        match = re.match(r"^(id|version|source-sha):\s*(.+?)\s*$", raw)
        if match:
            values[match.group(1)] = match.group(2).strip().strip("'\"")
    if (
        not values.get("id")
        or not values.get("version")
        or not skills
        or set(operations) != set(OPERATIONS)
    ):
        raise ScaffoldError(
            "cannot parse required id, version, skills, and operations from target manifest"
        )
    return Pack(
        values["id"],
        values["version"],
        path.parent,
        tuple(skills),
        values.get("source-sha"),
        operations,
    )


def discover_packs(root: Path) -> list[Pack]:
    manifests = sorted((root / "packs").glob("*/*/skillpack.yaml"))
    if not manifests:
        raise ScaffoldError("no packs/*/*/skillpack.yaml manifests found")
    return [parse_manifest(path) for path in manifests]


def update_manifest_text(text: str, *, skill: str) -> str:
    lines = text.splitlines()
    try:
        start = lines.index("skills:")
    except ValueError as exc:
        raise ScaffoldError("target manifest has no top-level skills list") from exc

    end = start + 1
    while end < len(lines) and lines[end].startswith("- "):
        end += 1
    listed = [line[2:].strip().strip("'\"") for line in lines[start + 1 : end]]
    if skill in listed:
        raise ScaffoldError(f"skill {skill!r} is already listed in the target manifest")
    lines.insert(end, f"- {skill}")
    return "\n".join(lines) + "\n"


def ensure_safe_repo_path(root: Path, path: Path, *, label: str) -> Path:
    """Return a resolved in-repository path and reject symlink traversal."""

    resolved_root = root.resolve()
    try:
        relative = path.relative_to(resolved_root)
    except ValueError as exc:
        raise ScaffoldError(f"{label} is outside the repository: {path}") from exc

    current = resolved_root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise ScaffoldError(f"{label} contains a symlink component: {current}")

    resolved = path.resolve(strict=False)
    try:
        resolved.relative_to(resolved_root)
    except ValueError as exc:
        raise ScaffoldError(f"{label} resolves outside the repository: {path}") from exc
    return resolved


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else 0o644
    handle, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
        temporary.chmod(mode)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def replace_template_tokens(
    directory: Path, *, name: str, pack: Pack, neighbor: str, openai: dict[str, str]
) -> None:
    replacements = {
        "replace-with-globally-unique-skill-name": name,
        "replace-with-pack-id": pack.id,
        "replace-with-neighbor-skill": neighbor,
        'version: "0.1.0"': f'version: "{pack.version}"',
    }
    for path in sorted(directory.rglob("*")):
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for old, new in replacements.items():
            text = text.replace(old, new)
        if path.relative_to(directory).as_posix() == "agents/openai.yaml":
            text = (
                "interface:\n"
                + "\n".join(
                    [
                        f"  display_name: {json.dumps(openai['displayName'], ensure_ascii=False)}",
                        f"  short_description: {json.dumps(openai['shortDescription'], ensure_ascii=False)}",
                        f"  default_prompt: {json.dumps(openai['defaultPrompt'], ensure_ascii=False)}",
                    ]
                )
                + "\n"
            )
        path.write_text(text, encoding="utf-8")


def tree_digest(path: Path) -> str:
    digest = hashlib.sha256()
    for candidate in inspect_tree(path, label="created destination"):
        relative = candidate.relative_to(path).as_posix().encode()
        digest.update(relative + b"\0" + candidate.read_bytes() + b"\0")
        digest.update(f"{stat.S_IMODE(candidate.stat().st_mode):03o}".encode())
    return digest.hexdigest()


def atomic_replace(path: Path, content: bytes) -> None:
    mode = stat.S_IMODE(path.stat().st_mode)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
        temporary.chmod(mode)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


@contextmanager
def repository_lock(root: Path):
    scratch = root / ".tmp"
    created_scratch = not scratch.exists()
    scratch.mkdir(mode=0o700, exist_ok=True)
    if scratch.is_symlink() or not scratch.is_dir():
        raise ScaffoldError(".tmp must be a real directory")
    lock = scratch / "repository-scaffold.lock"
    try:
        lock.mkdir(mode=0o700)
    except FileExistsError as exc:
        raise ScaffoldError(
            "another repository scaffold apply is active or left a stale lock"
        ) from exc
    try:
        yield scratch
    finally:
        lock.rmdir()
        if created_scratch:
            try:
                scratch.rmdir()
            except OSError:
                pass


def build_plan(root: Path, request_path: Path) -> tuple[dict[str, Any], Pack, Path, bytes, bytes]:
    repository_file = root / "repository.yaml"
    safe_regular_file(repository_file, label="repository.yaml")
    template = root / "templates" / "skill"
    template_files = inspect_tree(template, label="skill template")
    request = validate_request(load_strict_json(request_path))
    name = request["skillName"]
    pack_id = request["packId"]

    packs = discover_packs(root)
    matches = [pack for pack in packs if pack.id == pack_id]
    if len(matches) != 1:
        known = ", ".join(pack.id for pack in packs)
        raise ScaffoldError(f"unknown pack {pack_id!r}; known packs: {known}")
    pack = matches[0]
    if request["expectedPackVersion"] != pack.version:
        raise ScaffoldError(
            f"expectedPackVersion {request['expectedPackVersion']!r} does not match {pack.version!r}"
        )
    if pack.source_sha:
        raise ScaffoldError(
            "refusing to modify a pack with source-sha; begin an explicit unreleased cycle"
        )
    changelog = pack.path / "CHANGELOG.md"
    safe_regular_file(changelog, label="target changelog")
    if not re.search(r"(?m)^## \[Unreleased\]\s*$", changelog.read_text(encoding="utf-8")):
        raise ScaffoldError("target pack CHANGELOG.md has no explicit [Unreleased] section")
    for key, ranking in OPERATION_RANKS.items():
        if ranking[request["operations"][key]] > ranking[pack.operations[key]]:
            raise ScaffoldError(f"operations.{key} exceeds the target pack operation envelope")

    all_skills = {skill for candidate in packs for skill in candidate.skills}
    if name in all_skills:
        raise ScaffoldError(f"skill name {name!r} already exists in a pack manifest")
    if request["nearestNeighbor"] not in all_skills:
        raise ScaffoldError("nearestNeighbor must name an existing public skill")

    for candidate in packs:
        actual = {
            path.name
            for path in (candidate.path / "skills").iterdir()
            if path.is_dir() and not path.is_symlink()
        }
        if actual != set(candidate.skills):
            raise ScaffoldError(
                f"pack {candidate.id!r} has undeclared or missing canonical skill directories"
            )

    ensure_safe_repo_path(root, pack.path, label="target pack")
    destination = pack.path / "skills" / name
    ensure_safe_repo_path(root, destination, label="skill destination")
    if destination.exists() or destination.is_symlink():
        raise ScaffoldError(f"refusing existing destination: {destination}")

    if not (template / "SKILL.md").is_file():
        raise ScaffoldError("skill template is missing SKILL.md")

    expected_path = pack.path / "tests" / "compatibility" / "expected-skills.json"
    try:
        expected = json.loads(expected_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        raise ScaffoldError(f"cannot read compatibility inventory {expected_path}: {exc}") from exc
    if expected.get("pack") != pack.id or expected.get("version") != pack.version:
        raise ScaffoldError("compatibility inventory identity or version does not match the pack")
    if expected.get("skills") != list(pack.skills):
        raise ScaffoldError("compatibility inventory skill order does not match the pack manifest")

    manifest_path = pack.path / "skillpack.yaml"
    safe_regular_file(manifest_path, label="target manifest")
    manifest_after = update_manifest_text(
        manifest_path.read_text(encoding="utf-8"), skill=name
    ).encode()
    expected_after = dict(expected)
    expected_after["skills"] = [*pack.skills, name]
    expected_text = (json.dumps(expected_after, indent=2) + "\n").encode()

    preimages = {
        "request": sha256(request_path),
        "repository.yaml": sha256(repository_file),
        str(manifest_path.relative_to(root)): sha256(manifest_path),
        str(changelog.relative_to(root)): sha256(changelog),
        str(expected_path.relative_to(root)): sha256(expected_path),
    }
    preimages.update({str(path.relative_to(root)): sha256(path) for path in template_files})

    plan = {
        "schemaVersion": 1,
        "operation": "create-new-skill",
        "repository": ".",
        "request": "request",
        "skillName": name,
        "packId": pack.id,
        "packVersion": pack.version,
        "destination": str(destination.relative_to(root)),
        "canonicalUpdates": [
            str(manifest_path.relative_to(root)),
            str(expected_path.relative_to(root)),
        ],
        "newFiles": [
            str((destination / path.relative_to(template)).relative_to(root))
            for path in template_files
        ],
        "preimages": dict(sorted(preimages.items())),
        "notes": [
            "Preview is read-only; apply requires this exact plan digest.",
            "Scaffold content is not final and must be fully researched and rewritten.",
            "Pack README, changelog, generated artifacts, eval quality, and repository tests remain required.",
        ],
    }
    return plan, pack, destination, manifest_after, expected_text


def apply_plan(root: Path, request_path: Path, expected_digest: str) -> dict[str, Any]:
    initial, _, _, _, _ = build_plan(root, request_path)
    if canonical_digest(initial) != expected_digest:
        raise ScaffoldError("plan digest is stale or does not match this request and repository")
    with repository_lock(root) as scratch:
        plan, pack, destination, manifest_after, expected_after = build_plan(root, request_path)
        if canonical_digest(plan) != expected_digest:
            raise ScaffoldError("plan changed while acquiring the repository lock")
        staging_parent = Path(tempfile.mkdtemp(prefix="scaffold-skill-", dir=scratch))
        staged = staging_parent / plan["skillName"]
        manifest_path = pack.path / "skillpack.yaml"
        expected_path = pack.path / "tests" / "compatibility" / "expected-skills.json"
        manifest_before = manifest_path.read_bytes()
        expected_before = expected_path.read_bytes()
        destination_created = False
        created_digest = ""
        rollback_errors: list[str] = []
        try:
            shutil.copytree(root / "templates" / "skill", staged, copy_function=shutil.copy2)
            request = validate_request(load_strict_json(request_path))
            replace_template_tokens(
                staged,
                name=plan["skillName"],
                pack=pack,
                neighbor=request["nearestNeighbor"],
                openai=request["openai"],
            )
            created_digest = tree_digest(staged)
            final_plan, _, _, _, _ = build_plan(root, request_path)
            if canonical_digest(final_plan) != expected_digest:
                raise ScaffoldError("plan inputs changed while staging; nothing was applied")
            os.replace(staged, destination)
            destination_created = True
            atomic_replace(manifest_path, manifest_after)
            atomic_replace(expected_path, expected_after)
        except BaseException as exc:
            if sha256(expected_path) == hashlib.sha256(expected_after).hexdigest():
                try:
                    atomic_replace(expected_path, expected_before)
                except OSError as rollback:
                    rollback_errors.append(f"compatibility inventory: {rollback}")
            if sha256(manifest_path) == hashlib.sha256(manifest_after).hexdigest():
                try:
                    atomic_replace(manifest_path, manifest_before)
                except OSError as rollback:
                    rollback_errors.append(f"manifest: {rollback}")
            destination_moved = destination_created or (
                not staged.exists() and destination.is_dir() and not destination.is_symlink()
            )
            if destination_moved:
                try:
                    if tree_digest(destination) != created_digest:
                        rollback_errors.append(
                            "created destination changed concurrently and was preserved"
                        )
                    else:
                        shutil.rmtree(destination)
                except OSError as rollback:
                    rollback_errors.append(f"destination: {rollback}")
            prefix = "apply interrupted" if isinstance(exc, KeyboardInterrupt) else "apply failed"
            message = f"{prefix} and was rolled back where safe: {exc}"
            if rollback_errors:
                message += "; rollback issues: " + "; ".join(rollback_errors)
            raise ScaffoldError(message) from exc
        finally:
            shutil.rmtree(staging_parent, ignore_errors=True)
    return plan


def parser() -> argparse.ArgumentParser:
    argument_parser = argparse.ArgumentParser(
        description=(
            "Preview or scaffold one skill inside an existing repository skillpack. "
            "Requires Python 3.11 and the standard library; uses no network or external "
            "commands. Preview writes nothing and prints to stdout. Apply writes canonical "
            "repository files only after --plan-digest verification. Interrupted multi-file "
            "applies require worktree inspection before retrying."
        )
    )
    argument_parser.add_argument(
        "--repo",
        type=Path,
        default=Path.cwd(),
        help="Repository root (default: current directory).",
    )
    argument_parser.add_argument(
        "--request",
        type=Path,
        required=True,
        help="JSON request matching assets/skill-request.template.json.",
    )
    argument_parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply the previewed structural changes. Without this flag no files are changed.",
    )
    argument_parser.add_argument(
        "--plan-digest", help="Reviewed SHA-256 planDigest; required with --apply."
    )
    argument_parser.add_argument(
        "--json", action="store_true", help="Print the plan or result as JSON."
    )
    return argument_parser


def main(argv: list[str] | None = None) -> int:
    arguments = parser().parse_args(argv)
    root = arguments.repo.expanduser().absolute()
    request_path = arguments.request.expanduser().absolute()
    try:
        if arguments.apply:
            if not arguments.plan_digest or not re.fullmatch(
                r"[0-9a-f]{64}", arguments.plan_digest
            ):
                raise ScaffoldError(
                    "--apply requires --plan-digest with the reviewed 64-character lowercase SHA-256"
                )
            base = apply_plan(root, request_path, arguments.plan_digest)
            plan = {**plan_with_digest(base), "mode": "apply", "applied": True}
        else:
            if arguments.plan_digest:
                raise ScaffoldError("--plan-digest is only valid with --apply")
            base, _, _, _, _ = build_plan(root, request_path)
            plan = {**plan_with_digest(base), "mode": "preview", "applied": False}
    except (OSError, ScaffoldError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if arguments.json:
        print(json.dumps(plan, indent=2, sort_keys=True, ensure_ascii=False))
    else:
        print(f"{plan['mode']}: {plan['operation']}")
        print(f"repository: {plan['repository']}")
        print(f"pack: {plan['packId']}@{plan['packVersion']}")
        print(f"skill: {plan['skillName']}")
        print(f"destination: {plan['destination']}")
        print("canonical updates:")
        for item in plan["canonicalUpdates"]:
            print(f"  - {item}")
        print(f"new files: {len(plan['newFiles'])}")
        for item in plan["newFiles"]:
            print(f"  - {item}")
        for note in plan["notes"]:
            print(f"note: {note}")
        if not arguments.apply:
            print(f"plan digest: {plan['planDigest']}")
            print("No files changed. Re-run with --apply --plan-digest DIGEST after review.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
