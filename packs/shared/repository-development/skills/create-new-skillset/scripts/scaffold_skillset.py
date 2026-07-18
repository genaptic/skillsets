#!/usr/bin/env python3
"""Safely preview or scaffold one new skillpack and its declared skills.

Requires Python 3.11 and only the standard library. Preview is read-only and prints a
repository-relative plan to stdout. Apply stages one complete canonical pack and requires
the reviewed plan digest. The helper never uses the network, runs external commands,
installs dependencies, generates client adapters, or performs Git/release operations.
Interrupted applies require worktree inspection before retrying.
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
TARGETS = {"claude-code", "codex", "opencode"}
NETWORK = {"none", "optional", "required"}
FILESYSTEM = {"read-only", "explicit-output", "project-write", "system-write"}
COMMANDS = {"none", "optional-explicit", "required"}
EXTERNAL_WRITES = {"none", "optional-explicit", "required"}
MAX_REQUEST_BYTES = 1024 * 1024
MAX_JSON_DEPTH = 64
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
class ExistingPack:
    id: str
    path: Path
    skills: tuple[str, ...]


@dataclass(frozen=True)
class SkillRequest:
    original_name: str
    name: str
    details: str
    scope: Any
    expected_output: str
    success_criteria: tuple[str, ...]
    constraints: tuple[str, ...]
    operations: dict[str, str]
    nearest_neighbor: str
    openai: dict[str, str]


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


def load_strict_json(path: Path) -> Any:
    safe_regular_file(path, label="request")
    if path.stat().st_size > MAX_REQUEST_BYTES:
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


def validate_source_requirements(value: Any, *, label: str) -> dict[str, Any]:
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


def validate_openai(value: Any, *, skill: str, label: str) -> dict[str, str]:
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


def validate_scope(value: Any, *, label: str, pack: bool = False) -> dict[str, Any]:
    fields = (
        {"owns", "excludes", "supportedEnvironments"}
        if pack
        else {"useWhen", "doNotUseWhen", "supportedEnvironments"}
    )
    data = expect_object(value, label=label, required=fields)
    first, second = ("owns", "excludes") if pack else ("useWhen", "doNotUseWhen")
    minimum = 1 if pack else 2
    string_list(
        data[first],
        label=f"{label}.{first}",
        minimum=minimum,
        maximum=20,
        item_min=10,
        item_max=1000,
    )
    string_list(
        data[second],
        label=f"{label}.{second}",
        minimum=minimum,
        maximum=20,
        item_min=10,
        item_max=1000,
    )
    string_list(
        data["supportedEnvironments"],
        label=f"{label}.supportedEnvironments",
        minimum=1,
        maximum=20,
        item_min=3,
        item_max=500,
    )
    return data


def validate_examples(value: Any, *, label: str) -> dict[str, Any]:
    data = expect_object(value, label=label, required={"shouldTrigger", "shouldNotTrigger"})
    for key in ("shouldTrigger", "shouldNotTrigger"):
        string_list(
            data[key], label=f"{label}.{key}", minimum=2, maximum=20, item_min=20, item_max=2000
        )
    return data


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


def public_plan(plan: dict[str, Any]) -> dict[str, Any]:
    result = {key: value for key, value in plan.items() if key not in {"details", "scope"}}
    result["skills"] = [
        {
            "name": skill["name"],
            "nearestNeighbor": skill["nearestNeighbor"],
            "openai": skill["openai"],
        }
        for skill in plan["skills"]
    ]
    return result


def canonical_digest(plan: dict[str, Any]) -> str:
    content = json.dumps(
        public_plan(plan), sort_keys=True, ensure_ascii=False, separators=(",", ":")
    ).encode()
    return hashlib.sha256(content).hexdigest()


def plan_with_digest(plan: dict[str, Any]) -> dict[str, Any]:
    return {**public_plan(plan), "planDigest": canonical_digest(plan)}


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


def parse_manifest(path: Path) -> ExistingPack:
    pack_id = ""
    skills: list[str] = []
    in_skills = False
    for raw in path.read_text(encoding="utf-8").splitlines():
        if raw == "skills:":
            in_skills = True
            continue
        if in_skills:
            if raw.startswith("- "):
                skills.append(raw[2:].strip().strip("'\""))
                continue
            if raw and not raw.startswith((" ", "\t")):
                in_skills = False
        match = re.match(r"^id:\s*(.+?)\s*$", raw)
        if match:
            pack_id = match.group(1).strip().strip("'\"")
    if not pack_id or not skills:
        raise ScaffoldError(f"cannot parse required id and skills from {path}")
    return ExistingPack(pack_id, path.parent, tuple(skills))


def discover_packs(root: Path) -> list[ExistingPack]:
    manifests = sorted((root / "packs").glob("*/*/skillpack.yaml"))
    if not manifests:
        raise ScaffoldError("no packs/*/*/skillpack.yaml manifests found")
    return [parse_manifest(path) for path in manifests]


def repository_maintainer(root: Path) -> str:
    text = (root / "repository.yaml").read_text(encoding="utf-8")
    match = re.search(r"(?m)^\s{2}github:\s*([^\s#]+)\s*$", text)
    if not match:
        raise ScaffoldError("cannot find maintainer.github in repository.yaml")
    return match.group(1).strip().strip("'\"")


def yaml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def render_manifest(plan: dict[str, Any], maintainer: str) -> str:
    compatibility = plan["compatibility"]
    operations = plan["operations"]
    lines = [
        "schema-version: 1",
        f"id: {yaml_string(plan['packId'])}",
        f"display-name: {yaml_string(plan['displayName'])}",
        f"description: {yaml_string(plan['description'])}",
        f"language: {yaml_string(plan['language'])}",
        f"subject: {yaml_string(plan['subject'])}",
        f"version: {yaml_string(plan['version'])}",
        "license: Apache-2.0",
        "maintainers:",
        f"- github: {yaml_string(maintainer)}",
        "skills:",
        *[f"- {yaml_string(skill['name'])}" for skill in plan["skills"]],
        "targets:",
        *[f"- {yaml_string(target)}" for target in plan["targets"]],
        f"category: {yaml_string(plan['category'])}",
        "keywords:",
        *[f"- {yaml_string(keyword)}" for keyword in plan["keywords"]],
        "compatibility:",
        "  runtimes:",
        *[
            f"    {runtime}: {yaml_string(requirement)}"
            for runtime, requirement in compatibility["runtimes"].items()
        ],
        f"  notes: {yaml_string(compatibility['notes'])}",
        "operations:",
        f"  network: {yaml_string(operations['network'])}",
        f"  filesystem: {yaml_string(operations['filesystem'])}",
        f"  command-execution: {yaml_string(operations['commandExecution'])}",
        f"  external-writes: {yaml_string(operations['externalWrites'])}",
    ]
    return "\n".join(lines) + "\n"


def markdown_cell(value: str) -> str:
    return " ".join(value.split()).replace("|", "\\|")


def render_readme(plan: dict[str, Any]) -> str:
    rows = "\n".join(
        f"| [`{skill['name']}`](skills/{skill['name']}/SKILL.md) | {markdown_cell(skill['details'])} |"
        for skill in plan["skills"]
    )
    return f"""# {plan["displayName"]}

{plan["description"]}

## Purpose and boundaries

This pack owns the approved scope documented in its skillset design record. Replace this
paragraph with a precise statement of what the pack owns, what it excludes, and which
existing packs remain preferred for neighboring outcomes before considering the pack
complete.

## Included skills

| Skill | Focus |
|---|---|
{rows}

## Prerequisites

Replace this section with the actual client, language, tool, version, environment, and
optional-helper prerequisites established by research. Do not imply that installation runs
bundled helpers or installs dependencies.

## Tools, network, and side effects

Replace this section with the pack-level operational envelope and per-skill approval
boundaries. The manifest summary is conservative; each skill must remain explicit about its
own reads, writes, commands, network use, external effects, verification, and rollback.

## Install, update, and uninstall

<!-- BEGIN GENERATED INSTALL COMMANDS -->
<!-- END GENERATED INSTALL COMMANDS -->

## Version and compatibility

Current pack version: `{plan["version"]}`.

Release state: unpublished release candidate.

Expected future tag (not created by this scaffold): `{plan["packId"]}-v{plan["version"]}`.

{plan["compatibility"]["notes"]}

See the root [`COMPATIBILITY.md`](../../../COMPATIBILITY.md) and this pack's compatibility
tests. Paths in this section are relative to the pack location when installed; root links
are intended for the source repository.

## Changelog and migrations

See [`CHANGELOG.md`](CHANGELOG.md). Public skill names are stable API. A rename, removal,
broader permission requirement, or materially changed output contract requires a major
version and migration notes.
"""


def render_changelog(plan: dict[str, Any]) -> str:
    items = "\n".join(f"- Added `{skill['name']}`." for skill in plan["skills"])
    return f"""# Changelog

## [Unreleased]

### Added

- Prepared the `{plan["version"]}` release-candidate contents for the `{plan["packId"]}` skillpack.
{items}

`{plan["version"]}` has not been published. Freeze the candidate and collect exact-SHA
native/model compatibility evidence before creating a release.
"""


def render_compatibility_readme(plan: dict[str, Any]) -> str:
    lines = [
        f"# {plan['displayName']} compatibility fixture",
        "",
        "`expected-skills.json` is the exact ordered discovery contract for this pack. The root",
        "validator checks it against `skillpack.yaml`. Client smoke tests must compare their discovered",
        "skill names to this file and record client/model versions, exact source SHA, permissions,",
        "network/filesystem effects, and reviewer verdict in a schema-valid report.",
        "",
        "`smoke.py` is offline and checks that every declared canonical skill contains `SKILL.md`.",
        "No test here connects externally or installs a plugin. Passing is structural evidence only,",
        "not a native-client or model-backed compatibility claim.",
    ]
    return "\n".join(lines) + "\n"


def render_compatibility_smoke() -> str:
    lines = [
        "#!/usr/bin/env python3",
        '"""Offline structural smoke test for one installed or source pack."""',
        "from __future__ import annotations",
        "",
        "import argparse",
        "import json",
        "from pathlib import Path",
        "",
        "",
        "def main() -> int:",
        "    parser = argparse.ArgumentParser()",
        "    parser.add_argument(",
        '        "pack_root",',
        '        nargs="?",',
        "        default=str(Path(__file__).resolve().parents[2]),",
        '        help="Pack root containing skillpack.yaml and skills/.",',
        "    )",
        "    args = parser.parse_args()",
        "    pack_root = Path(args.pack_root).resolve()",
        '    expected_path = Path(__file__).with_name("expected-skills.json")',
        '    expected = json.loads(expected_path.read_text(encoding="utf-8"))',
        "    missing = []",
        '    for skill in expected["skills"]:',
        '        path = pack_root / "skills" / skill / "SKILL.md"',
        "        if not path.is_file():",
        "            missing.append(str(path))",
        "    if missing:",
        "        for path in missing:",
        '            print(f"missing: {path}")',
        "        return 1",
        "    print(f\"ok: {expected['pack']} exposes {len(expected['skills'])} expected skills\")",
        "    return 0",
        "",
        "",
        'if __name__ == "__main__":',
        "    raise SystemExit(main())",
    ]
    return "\n".join(lines) + "\n"


def replace_template_tokens(
    directory: Path,
    *,
    name: str,
    pack_id: str,
    version: str,
    neighbor: str,
    openai: dict[str, str],
) -> None:
    replacements = {
        "replace-with-globally-unique-skill-name": name,
        "replace-with-pack-id": pack_id,
        "replace-with-neighbor-skill": neighbor,
        'version: "0.1.0"': f'version: "{version}"',
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


OPERATION_RANKS = {
    "network": {"none": 0, "optional": 1, "required": 2},
    "filesystem": {"read-only": 0, "explicit-output": 1, "project-write": 2, "system-write": 3},
    "commandExecution": {"none": 0, "optional-explicit": 1, "required": 2},
    "externalWrites": {"none": 0, "optional-explicit": 1, "required": 2},
}


def validate_operation_envelope(
    pack: dict[str, str], skill: dict[str, str], *, skill_name: str
) -> None:
    for key, ranking in OPERATION_RANKS.items():
        if ranking[skill[key]] > ranking[pack[key]]:
            raise ScaffoldError(
                f"skill {skill_name!r} declares operations.{key}={skill[key]!r}, "
                f"which exceeds pack operations.{key}={pack[key]!r}"
            )


def validate_operations(value: Any) -> dict[str, str]:
    data = expect_object(
        value,
        label="operations",
        required={"network", "filesystem", "commandExecution", "externalWrites"},
    )
    result = dict(data)
    checks = {
        "network": NETWORK,
        "filesystem": FILESYSTEM,
        "commandExecution": COMMANDS,
        "externalWrites": EXTERNAL_WRITES,
    }
    for key, allowed in checks.items():
        if result[key] not in allowed:
            raise ScaffoldError(f"operations.{key} must be one of: {', '.join(sorted(allowed))}")
    return result


def build_plan(root: Path, request_path: Path) -> dict[str, Any]:
    repository_file = root / "repository.yaml"
    safe_regular_file(repository_file, label="repository.yaml")
    required = {
        "schemaVersion",
        "skillsetName",
        "packId",
        "displayName",
        "language",
        "subject",
        "description",
        "details",
        "scope",
        "version",
        "targets",
        "category",
        "keywords",
        "compatibility",
        "operations",
        "sourceRequirements",
        "skills",
    }
    request = expect_object(
        load_strict_json(request_path), label="request", required=required, optional={"userSources"}
    )
    if type(request["schemaVersion"]) is not int or request["schemaVersion"] != 1:
        raise ScaffoldError("request.schemaVersion must be integer 1")
    original_skillset_name = text_field(
        request["skillsetName"], label="skillsetName", minimum=3, maximum=100
    )
    details = text_field(request["details"], label="details", minimum=40, maximum=16000)
    scope = validate_scope(request["scope"], label="scope", pack=True)
    language = text_field(request["language"], label="language", minimum=1, maximum=32)
    subject = text_field(request["subject"], label="subject", minimum=1, maximum=48)
    if not KEBAB_RE.fullmatch(language) or not KEBAB_RE.fullmatch(subject):
        raise ScaffoldError("language and subject must be lowercase kebab-case")
    expected_id = subject if language == "shared" else f"{language}-{subject}"
    pack_id = text_field(request["packId"], label="packId", minimum=1, maximum=64)
    if not KEBAB_RE.fullmatch(pack_id):
        raise ScaffoldError("packId must be lowercase kebab-case")
    if pack_id != expected_id:
        raise ScaffoldError(
            f"packId must be {expected_id!r} for language={language!r} and subject={subject!r}"
        )

    display_name = text_field(request["displayName"], label="displayName", minimum=3, maximum=80)
    description = text_field(request["description"], label="description", minimum=40, maximum=500)

    version = request["version"]
    if not isinstance(version, str) or not SEMVER_RE.fullmatch(version):
        raise ScaffoldError(f"invalid Semantic Version: {version!r}")

    targets = string_list(
        request["targets"], label="targets", minimum=1, maximum=3, item_min=5, item_max=20
    )
    if not set(targets) <= TARGETS:
        raise ScaffoldError(f"unsupported targets: {sorted(set(targets) - TARGETS)}")

    category = text_field(request["category"], label="category", minimum=3, maximum=40)
    keywords = string_list(
        request["keywords"], label="keywords", minimum=3, maximum=12, item_min=1, item_max=32
    )
    if not all(KEBAB_RE.fullmatch(item) for item in keywords):
        raise ScaffoldError("keywords must be lowercase kebab-case")

    compatibility_raw = expect_object(
        request["compatibility"], label="compatibility", required={"runtimes", "notes"}
    )
    runtimes = compatibility_raw["runtimes"]
    if not isinstance(runtimes, dict) or not 1 <= len(runtimes) <= 12:
        raise ScaffoldError("compatibility.runtimes must contain 1 to 12 named runtimes")
    for runtime, requirement in runtimes.items():
        if not isinstance(runtime, str) or not KEBAB_RE.fullmatch(runtime):
            raise ScaffoldError("compatibility runtime names must be lowercase kebab-case")
        text_field(requirement, label=f"compatibility.runtimes.{runtime}", minimum=1, maximum=100)
    notes = text_field(
        compatibility_raw["notes"], label="compatibility.notes", minimum=20, maximum=500
    )
    compatibility = {"runtimes": dict(sorted(runtimes.items())), "notes": notes}

    operations = validate_operations(request["operations"])
    validate_source_requirements(request["sourceRequirements"], label="sourceRequirements")
    validate_sources(request.get("userSources", []))

    raw_skills = request.get("skills")
    if not isinstance(raw_skills, list) or not 1 <= len(raw_skills) <= 20:
        raise ScaffoldError("request field 'skills' must contain 1 to 20 detailed skill objects")
    skills: list[SkillRequest] = []
    for index, item in enumerate(raw_skills):
        label = f"skills[{index}]"
        required_skill = {
            "name",
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
        item = expect_object(item, label=label, required=required_skill)
        original_name = text_field(item["name"], label=f"{label}.name", minimum=1, maximum=64)
        name = original_name
        if not KEBAB_RE.fullmatch(name):
            raise ScaffoldError(f"{label}.name must be lowercase kebab-case")
        skill_details = text_field(
            item["details"], label=f"{label}.details", minimum=40, maximum=12000
        )
        skill_scope = validate_scope(item["scope"], label=f"{label}.scope")
        expected_output = text_field(
            item["expectedOutput"], label=f"{label}.expectedOutput", minimum=20, maximum=3000
        )
        success_criteria = tuple(
            string_list(
                item.get("successCriteria"),
                label=f"skills[{index}].successCriteria",
                minimum=1,
                maximum=20,
                item_min=10,
                item_max=1000,
            )
        )
        if len(success_criteria) < 2:
            raise ScaffoldError(f"{label}.successCriteria must contain at least 2 items")
        validate_examples(item["examples"], label=f"{label}.examples")
        constraints = string_list(
            item["constraints"],
            label=f"{label}.constraints",
            minimum=1,
            maximum=20,
            item_min=3,
            item_max=1000,
        )
        skill_operations = validate_operations(item["operations"])
        nearest_neighbor = text_field(
            item["nearestNeighbor"], label=f"{label}.nearestNeighbor", minimum=1, maximum=64
        )
        if not KEBAB_RE.fullmatch(nearest_neighbor):
            raise ScaffoldError(f"{label}.nearestNeighbor must be lowercase kebab-case")
        validate_source_requirements(
            item["sourceRequirements"], label=f"{label}.sourceRequirements"
        )
        openai = validate_openai(item["openai"], skill=name, label=f"{label}.openai")
        skills.append(
            SkillRequest(
                original_name,
                name,
                skill_details,
                skill_scope,
                expected_output,
                success_criteria,
                tuple(constraints),
                skill_operations,
                nearest_neighbor,
                openai,
            )
        )

    names = [skill.name for skill in skills]
    if len(names) != len(set(names)):
        raise ScaffoldError("skill names must be unique within the request")

    expected_operations: dict[str, str] = {}
    for key, ranking in OPERATION_RANKS.items():
        expected_rank = max(ranking[skill.operations[key]] for skill in skills)
        expected_operations[key] = next(
            value for value, rank in ranking.items() if rank == expected_rank
        )
    if operations != expected_operations:
        raise ScaffoldError(
            "pack operations must exactly equal the component-wise maximum of skill operations; "
            f"expected {expected_operations}"
        )

    existing = discover_packs(root)
    existing_pack_ids = {pack.id for pack in existing}
    existing_skill_names = {skill for pack in existing for skill in pack.skills}
    if pack_id in existing_pack_ids:
        raise ScaffoldError(f"pack ID {pack_id!r} already exists")
    collisions = sorted(set(names) & existing_skill_names)
    if collisions:
        raise ScaffoldError(f"skill names already exist: {', '.join(collisions)}")

    known_neighbors = existing_skill_names | set(names)
    resolved_skills: list[SkillRequest] = []
    for skill in skills:
        neighbor = skill.nearest_neighbor
        if neighbor == skill.name:
            raise ScaffoldError(f"skill {skill.name!r} cannot name itself as nearestNeighbor")
        if neighbor not in known_neighbors:
            raise ScaffoldError(
                f"skill {skill.name!r} names unknown nearestNeighbor {neighbor!r}; "
                "use an existing or proposed skill name"
            )
        resolved_skills.append(
            SkillRequest(
                skill.original_name,
                skill.name,
                skill.details,
                skill.scope,
                skill.expected_output,
                skill.success_criteria,
                skill.constraints,
                skill.operations,
                neighbor,
                skill.openai,
            )
        )
    skills = resolved_skills
    if len(skills) == 1 and skills[0].nearest_neighbor not in existing_skill_names:
        raise ScaffoldError(
            "a one-skill pack requires nearestNeighbor to name an existing skill outside the proposed pack"
        )

    destination = root / "packs" / language / subject
    ensure_safe_repo_path(root, destination, label="skillpack destination")
    if destination.exists() or destination.is_symlink():
        raise ScaffoldError(f"refusing existing destination: {destination}")
    template = root / "templates" / "skill"
    pack_template = root / "templates" / "skillpack"
    ensure_safe_repo_path(root, template, label="skill template")
    ensure_safe_repo_path(root, pack_template, label="skillpack template")
    template_files = inspect_tree(template, label="skill template")
    pack_template_files = inspect_tree(pack_template, label="skillpack template")
    if not (template / "SKILL.md").is_file():
        raise ScaffoldError("skill template is missing SKILL.md")
    required_pack_files = {
        "skillpack.yaml",
        "README.md",
        "CHANGELOG.md",
        "tests/compatibility/README.md",
        "tests/compatibility/expected-skills.json",
        "tests/compatibility/smoke.py",
    }
    actual_pack_files = {path.relative_to(pack_template).as_posix() for path in pack_template_files}
    if not required_pack_files <= actual_pack_files:
        raise ScaffoldError("skillpack template is missing compatibility fixture files")

    skill_dicts = [
        {
            "originalName": skill.original_name,
            "name": skill.name,
            "details": skill.details,
            "scope": skill.scope,
            "expectedOutput": skill.expected_output,
            "successCriteria": list(skill.success_criteria),
            "constraints": list(skill.constraints),
            "operations": skill.operations,
            "nearestNeighbor": skill.nearest_neighbor,
            "openai": skill.openai,
        }
        for skill in skills
    ]
    new_files = [
        str((destination / path.relative_to(pack_template)).relative_to(root))
        for path in pack_template_files
    ]
    for skill in skills:
        for path in template_files:
            new_files.append(
                str(
                    (destination / "skills" / skill.name / path.relative_to(template)).relative_to(
                        root
                    )
                )
            )

    preimages = {
        "request": sha256(request_path),
        "repository.yaml": sha256(repository_file),
    }
    preimages.update({path.relative_to(root).as_posix(): sha256(path) for path in template_files})
    preimages.update(
        {path.relative_to(root).as_posix(): sha256(path) for path in pack_template_files}
    )
    for pack in existing:
        manifest = pack.path / "skillpack.yaml"
        preimages[manifest.relative_to(root).as_posix()] = sha256(manifest)

    return {
        "schemaVersion": 1,
        "operation": "create-new-skillset",
        "repository": ".",
        "request": "request",
        "skillsetName": original_skillset_name,
        "packId": pack_id,
        "displayName": display_name,
        "description": description,
        "details": details,
        "scope": scope,
        "language": language,
        "subject": subject,
        "version": version,
        "targets": targets,
        "category": category,
        "keywords": keywords,
        "compatibility": compatibility,
        "operations": operations,
        "skills": skill_dicts,
        "destination": str(destination.relative_to(root)),
        "newFiles": new_files,
        "preimages": dict(sorted(preimages.items())),
        "notes": [
            "Preview is read-only; apply requires this exact plan digest.",
            "The user's skill list is preserved; the helper performs no merge, split, rename beyond shown normalization, addition, or omission.",
            "Scaffold content is not final and must be fully researched and rewritten.",
            "Generation, repository tests, client checks, and release actions are not run.",
        ],
    }


def tree_digest(path: Path) -> str:
    digest = hashlib.sha256()
    for candidate in inspect_tree(path, label="created destination"):
        digest.update(candidate.relative_to(path).as_posix().encode() + b"\0")
        digest.update(candidate.read_bytes() + b"\0")
        digest.update(f"{stat.S_IMODE(candidate.stat().st_mode):03o}".encode())
    return digest.hexdigest()


def apply_plan(root: Path, request_path: Path, expected_digest: str) -> dict[str, Any]:
    initial = build_plan(root, request_path)
    if canonical_digest(initial) != expected_digest:
        raise ScaffoldError("plan digest is stale or does not match this request and repository")
    with repository_lock(root) as scratch:
        plan = build_plan(root, request_path)
        if canonical_digest(plan) != expected_digest:
            raise ScaffoldError("plan changed while acquiring the repository lock")
        destination = root / plan["destination"]
        ensure_safe_repo_path(root, destination, label="skillpack destination")
        staging_parent = Path(tempfile.mkdtemp(prefix="scaffold-skillset-", dir=scratch))
        staged_pack = staging_parent / plan["subject"]
        destination_created = False
        created_digest = ""
        created_parents: list[Path] = []
        try:
            shutil.copytree(
                root / "templates" / "skillpack", staged_pack, copy_function=shutil.copy2
            )
            (staged_pack / "skills").mkdir()
            maintainer = repository_maintainer(root)
            (staged_pack / "skillpack.yaml").write_text(
                render_manifest(plan, maintainer), encoding="utf-8"
            )
            (staged_pack / "README.md").write_text(render_readme(plan), encoding="utf-8")
            (staged_pack / "CHANGELOG.md").write_text(render_changelog(plan), encoding="utf-8")
            expected = {
                "schemaVersion": 1,
                "pack": plan["packId"],
                "version": plan["version"],
                "skills": [skill["name"] for skill in plan["skills"]],
            }
            compatibility_dir = staged_pack / "tests" / "compatibility"
            (compatibility_dir / "expected-skills.json").write_text(
                json.dumps(expected, indent=2) + "\n", encoding="utf-8"
            )
            (compatibility_dir / "README.md").write_text(
                render_compatibility_readme(plan), encoding="utf-8"
            )
            smoke_path = compatibility_dir / "smoke.py"
            smoke_path.write_text(render_compatibility_smoke(), encoding="utf-8")
            smoke_path.chmod(0o755)

            for skill in plan["skills"]:
                skill_dir = staged_pack / "skills" / skill["name"]
                shutil.copytree(root / "templates" / "skill", skill_dir, copy_function=shutil.copy2)
                replace_template_tokens(
                    skill_dir,
                    name=skill["name"],
                    pack_id=plan["packId"],
                    version=plan["version"],
                    neighbor=skill["nearestNeighbor"],
                    openai=skill["openai"],
                )

            created_digest = tree_digest(staged_pack)
            if canonical_digest(build_plan(root, request_path)) != expected_digest:
                raise ScaffoldError("plan inputs changed while staging; nothing was applied")
            parent = destination.parent
            missing: list[Path] = []
            while not parent.exists() and parent != root:
                missing.append(parent)
                parent = parent.parent
            for candidate in reversed(missing):
                candidate.mkdir()
                created_parents.append(candidate)
            if destination.exists() or destination.is_symlink():
                raise ScaffoldError("skillpack destination appeared concurrently")
            os.replace(staged_pack, destination)
            destination_created = True
        except BaseException as exc:
            rollback_issues: list[str] = []
            if destination_created:
                try:
                    if tree_digest(destination) == created_digest:
                        shutil.rmtree(destination)
                    else:
                        rollback_issues.append(
                            "created destination changed concurrently and was preserved"
                        )
                except OSError as rollback:
                    rollback_issues.append(f"destination: {rollback}")
            for candidate in reversed(created_parents):
                try:
                    candidate.rmdir()
                except OSError:
                    pass
            message = f"apply failed and was rolled back where safe: {exc}"
            if rollback_issues:
                message += "; rollback issues: " + "; ".join(rollback_issues)
            raise ScaffoldError(message) from exc
        finally:
            shutil.rmtree(staging_parent, ignore_errors=True)
    return plan


def parser() -> argparse.ArgumentParser:
    argument_parser = argparse.ArgumentParser(
        description=(
            "Preview or scaffold one new skillpack and all declared skills. Requires Python "
            "3.11 and the standard library; uses no network or external commands. Preview "
            "writes nothing and prints to stdout. Apply stages canonical repository files "
            "and requires --plan-digest. Inspect the worktree after interruption."
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
        help="JSON request matching assets/skillset-request.template.json.",
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
            base = build_plan(root, request_path)
            plan = {**plan_with_digest(base), "mode": "preview", "applied": False}
    except (OSError, ScaffoldError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if arguments.json:
        print(json.dumps(plan, indent=2, sort_keys=True, ensure_ascii=False))
    else:
        print(f"{plan['mode']}: {plan['operation']}")
        print(f"repository: {plan['repository']}")
        print(f"skillset: {plan['skillsetName']} -> {plan['packId']}")
        print(f"path: {plan['destination']}")
        print(f"version: {plan['version']}")
        print("skills:")
        for skill in plan["skills"]:
            print(f"  - {skill['name']}")
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
