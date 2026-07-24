from __future__ import annotations

import ast
import datetime as dt
import json
import math
import os
import re
import stat
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator

from .evals import validate_eval_file, validate_routing_boundaries
from .evidence import (
    evidence_freshness_errors,
    reviewer_authorization_errors,
    strict_load_json,
)
from .generate import GeneratedFiles, _reconcile_generated_files, apply_generated_files
from .lifecycle import SEMVER_PATTERN, select_packs, validate_pack_lifecycle
from .models import (
    CompatibilityEvidencePolicy,
    Pack,
    RepositoryConfig,
    discover_packs,
    load_repository,
)
from .path_safety import (
    inspect_path,
    read_regular_bytes,
    read_regular_text,
    repository_relative,
    runtime_resource_is_allowed,
    same_identity,
    security_name_key,
    security_sensitive_path,
    walk_tree,
)
from .schema_validation import format_checker, load_json_schema, schema_errors
from .util import (
    SkillpackError,
    markdown_local_links_text,
    parse_skill_markdown_text,
    sha256_bytes,
)

KEBAB_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SEMVER_RE = re.compile(SEMVER_PATTERN)
PLACEHOLDER_PATTERNS = (
    "your-github-handle",
    "Your Name",
    "security@example.com",
    "example.invalid",
    "OWNER/REPO",
    "YOUR_",
    "AGENT_SKILLPACKS_",
    "community-agent-skillpacks",
    "Agent Skillpacks",
    "agent-skillpacks",
)
DISALLOWED_SCRIPT_PATTERNS = {
    r"\bpip\s+install\b": "must not install Python packages",
    r"\bcurl\b.*\|\s*(?:sh|bash)\b": "must not pipe downloads to a shell",
    r"\bwget\b.*\|\s*(?:sh|bash)\b": "must not pipe downloads to a shell",
    r"\bos\.system\s*\(": "must not use os.system",
    r"shell\s*=\s*True": "must not invoke a shell through subprocess",
    r"\burllib\.request\b": "must not access the network",
    r"\brequests\.(?:get|post|put|delete|request)\b": "must not access the network",
}
STANDARD_FRONTMATTER_FIELDS = {"name", "description", "license", "metadata"}
REQUIRED_HEADING_GROUPS = {
    "Outcome": {"# Outcome", "## Outcome"},
    "Compatibility": {"## Compatibility"},
    "Inputs": {"## Inputs"},
    "Safety": {"## Safety", "## Safety posture"},
    "Procedure": {"## Procedure"},
    "Verification": {"## Verification"},
    "Output contract": {"## Output contract"},
    "Resources": {"## Resources"},
}
MAX_SKILL_ASSET_JSON_BYTES = 1024 * 1024
MAX_SKILL_ASSET_JSON_NESTING = 64

PLACEHOLDER_SCAN_EXCLUDED_PARTS = {
    ".git",
    ".idea",
    ".venv",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "__pycache__",
    "releases",
    "tests",
    "tmp",
}
RESIDUE_SCAN_EXCLUDED_PARTS = {
    ".git",
    ".idea",
    ".venv",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "__pycache__",
    "releases",
    "tmp",
}
RESIDUE_LOCAL_DIRECTORIES = {
    Path(".git"),
    Path(".idea"),
    Path(".mypy_cache"),
    Path(".pytest_cache"),
    Path(".ruff_cache"),
    Path(".venv"),
    Path("dist/releases"),
    Path("tmp"),
}
RESIDUE_LOCAL_FILES = {Path(".DS_Store")}
_CREDENTIAL_NAMES = {
    ".env",
    ".netrc",
    ".npmrc",
    ".pgpass",
    "credentials.json",
    "id_ed25519",
    "id_rsa",
    "secrets.json",
}
_CREDENTIAL_SUFFIXES = {".key", ".p12", ".pem", ".pfx"}


def _missing_operational_sections(body: str) -> set[str]:
    """Return missing semantic sections while accepting established heading aliases."""

    headings = {line.strip() for line in body.splitlines() if line.startswith("#")}
    return {
        label
        for label, accepted in REQUIRED_HEADING_GROUPS.items()
        if headings.isdisjoint(accepted)
    }


def _tracked_repository_paths(root: Path) -> set[Path] | None:
    """Return tracked lexical paths, or ``None`` outside a usable Git worktree."""

    try:
        completed = subprocess.run(
            ["git", "-C", str(root), "ls-files", "-z"],
            check=False,
            capture_output=True,
        )
    except OSError:
        return None
    if completed.returncode != 0:
        return None
    try:
        return {Path(os.fsdecode(value)) for value in completed.stdout.split(b"\0") if value}
    except UnicodeError:
        return None


@dataclass
class ValidationResult:
    errors: list[str]
    warnings: list[str]

    @property
    def ok(self) -> bool:
        return not self.errors


# Keep the established private names for tests and downstream repository tooling while using
# the same schema and format behavior as configure-repository.
_format_checker = format_checker
_schema_errors = schema_errors


def _load_schema(root: Path, relative: str, errors: list[str]) -> dict[str, Any] | None:
    try:
        return load_json_schema(
            root / "schemas" / relative,
            label=f"schemas/{relative}",
            root=root,
        )
    except ValueError as exc:
        errors.append(str(exc))
        return None


def _skill_asset_schema_paths(root: Path) -> list[Path]:
    """Return canonical skill-owned JSON Schemas in stable repository order."""

    root = Path(os.path.abspath(os.fspath(root)))
    snapshot = walk_tree(root / "packs", root, allow_missing=True)
    paths: list[Path] = []
    for path, _metadata in snapshot.files:
        relative = path.relative_to(root / "packs")
        if (
            len(relative.parts) == 6
            and relative.parts[2] == "skills"
            and relative.parts[4] == "assets"
            and path.name.endswith(".schema.json")
        ):
            paths.append(path)
    return sorted(paths)


def _expected_skill_asset_schema_id(
    root: Path,
    config: RepositoryConfig,
    path: Path,
) -> str:
    relative = path.relative_to(root).as_posix()
    return (
        f"https://raw.githubusercontent.com/{config.owner}/{config.name}/"
        f"{config.default_branch}/{relative}"
    )


class _DuplicateJSONKeyError(ValueError):
    pass


class _NonFiniteJSONNumberError(ValueError):
    pass


def _json_object_without_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateJSONKeyError(f"duplicate object key {key!r}")
        result[key] = value
    return result


def _finite_json_float(value: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise _NonFiniteJSONNumberError(f"non-finite number {value!r} is not permitted")
    return number


def _reject_json_constant(value: str) -> None:
    raise _NonFiniteJSONNumberError(f"non-finite number {value!r} is not permitted")


def _json_nesting_exceeds(value: Any, maximum: int) -> bool:
    stack: list[tuple[Any, int]] = [(value, 1)]
    while stack:
        current, depth = stack.pop()
        if not isinstance(current, (dict, list)):
            continue
        if depth > maximum:
            return True
        children = current.values() if isinstance(current, dict) else current
        stack.extend((child, depth + 1) for child in children)
    return False


def _load_json_value(
    path: Path,
    errors: list[str],
    *,
    root: Path | None = None,
) -> tuple[bool, Any]:
    """Load one bounded canonical contract document with strict JSON semantics."""

    try:
        content = read_regular_bytes(path, root) if root is not None else path.read_bytes()
    except FileNotFoundError:
        errors.append(f"Missing required JSON file: {path}")
        return False, None
    except (OSError, SkillpackError) as exc:
        errors.append(f"Could not read {path}: {exc}")
        return False, None

    if len(content) > MAX_SKILL_ASSET_JSON_BYTES:
        errors.append(
            f"{path}: canonical JSON document exceeds the 1 MiB "
            f"({MAX_SKILL_ASSET_JSON_BYTES}-byte) limit."
        )
        return False, None

    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as exc:
        errors.append(f"Invalid UTF-8 in {path}: {exc}")
        return False, None

    try:
        value = json.loads(
            text,
            object_pairs_hook=_json_object_without_duplicates,
            parse_float=_finite_json_float,
            parse_constant=_reject_json_constant,
        )
    except (_DuplicateJSONKeyError, _NonFiniteJSONNumberError) as exc:
        errors.append(f"Invalid JSON in {path}: {exc}")
        return False, None
    except json.JSONDecodeError as exc:
        errors.append(f"Invalid JSON in {path}: {exc}")
        return False, None
    except RecursionError:
        errors.append(
            f"{path}: JSON nesting exceeds the maximum of "
            f"{MAX_SKILL_ASSET_JSON_NESTING} container levels."
        )
        return False, None

    if _json_nesting_exceeds(value, MAX_SKILL_ASSET_JSON_NESTING):
        errors.append(
            f"{path}: JSON nesting exceeds the maximum of "
            f"{MAX_SKILL_ASSET_JSON_NESTING} container levels."
        )
        return False, None
    return True, value


def _validate_skill_asset_schemas(
    root: Path,
    config: RepositoryConfig,
    errors: list[str],
) -> None:
    """Validate canonical skill asset schemas and any colocated example documents."""

    for schema_path in _skill_asset_schema_paths(root):
        relative = schema_path.relative_to(root).as_posix()
        loaded, schema = _load_json_value(schema_path, errors, root=root)
        if not loaded:
            continue
        if not isinstance(schema, dict):
            errors.append(f"{relative}: JSON Schema must be an object.")
            continue

        expected_id = _expected_skill_asset_schema_id(root, config, schema_path)
        if schema.get("$id") != expected_id:
            errors.append(f"{relative}: $id must be {expected_id!r}.")

        try:
            Draft202012Validator.check_schema(schema)
        except Exception as exc:  # jsonschema exposes several schema-error subclasses
            errors.append(f"{relative}: invalid JSON Schema: {exc}")
            continue

        stem = schema_path.name.removesuffix(".schema.json")
        for kind in ("template", "example"):
            document_path = schema_path.with_name(f"{stem}.{kind}.json")
            try:
                document_metadata = inspect_path(
                    document_path,
                    root,
                    leaf_kind="file",
                    allow_missing=True,
                )
            except SkillpackError as exc:
                errors.append(str(exc))
                continue
            if document_metadata is None:
                errors.append(
                    f"{relative}: missing same-stem {kind} document "
                    f"{document_path.relative_to(root).as_posix()}."
                )
                continue
            document_loaded, document = _load_json_value(document_path, errors, root=root)
            if document_loaded:
                errors.extend(
                    _schema_errors(
                        document,
                        schema,
                        document_path.relative_to(root).as_posix(),
                    )
                )


def _load_json(
    path: Path,
    errors: list[str],
    *,
    root: Path | None = None,
) -> dict[str, Any] | None:
    try:
        text = (
            read_regular_text(path, root) if root is not None else path.read_text(encoding="utf-8")
        )
        data = json.loads(text)
    except FileNotFoundError:
        errors.append(f"Missing required JSON file: {path}")
        return None
    except SkillpackError as exc:
        errors.append(str(exc))
        return None
    except UnicodeDecodeError as exc:
        errors.append(f"Invalid UTF-8 in {path}: {exc}")
        return None
    except json.JSONDecodeError as exc:
        errors.append(f"Invalid JSON in {path}: {exc}")
        return None
    if not isinstance(data, dict):
        errors.append(f"Expected JSON object in {path}.")
        return None
    return data


def _validate_script(path: Path, errors: list[str], *, root: Path | None = None) -> None:
    text = read_regular_text(path, root) if root is not None else path.read_text(encoding="utf-8")
    for pattern, reason in DISALLOWED_SCRIPT_PATTERNS.items():
        if re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL):
            errors.append(f"{path}: helper script {reason}; matched {pattern!r}.")
    if path.suffix == ".py":
        try:
            compile(text, str(path), "exec")
            ast.parse(text, filename=str(path))
        except SyntaxError as exc:
            errors.append(f"{path}: Python syntax error: {exc}")


def _validate_openai_sidecar(
    root: Path,
    skill: str,
    path: Path,
    errors: list[str],
) -> None:
    try:
        data = yaml.safe_load(read_regular_text(path, root))
    except (SkillpackError, UnicodeDecodeError, yaml.YAMLError) as exc:
        errors.append(str(exc))
        return
    if not isinstance(data, dict):
        errors.append(f"{path}: agents/openai.yaml must be a YAML mapping.")
        return
    if set(data) != {"interface"} or not isinstance(data.get("interface"), dict):
        errors.append(f"{path}: agents/openai.yaml must contain only an interface mapping.")
        return
    interface = data["interface"]
    required = {"display_name", "short_description", "default_prompt"}
    if set(interface) != required:
        errors.append(
            f"{path}: interface keys must be exactly {sorted(required)}; found {sorted(interface)}."
        )
        return
    for key in required:
        if not isinstance(interface[key], str) or not interface[key].strip():
            errors.append(f"{path}: interface.{key} must be a non-empty string.")
    short = interface.get("short_description")
    if isinstance(short, str) and not 25 <= len(short.strip()) <= 64:
        errors.append(f"{path}: interface.short_description must be 25 to 64 characters.")
    prompt = interface.get("default_prompt")
    if isinstance(prompt, str) and f"${skill}" not in prompt:
        errors.append(f"{path}: interface.default_prompt must explicitly name ${skill}.")


def _validate_skill(
    root: Path,
    pack_id: str,
    pack_version: str,
    pack_maturity: str,
    skill: str,
    skill_dir: Path,
    errors: list[str],
    warnings: list[str],
) -> None:
    try:
        skill_directory_metadata = inspect_path(
            skill_dir,
            root,
            leaf_kind="directory",
            allow_missing=True,
        )
        if skill_directory_metadata is None:
            errors.append(f"{pack_id}/{skill}: missing skill directory.")
            return
        snapshot = walk_tree(skill_dir, root)
    except SkillpackError as exc:
        errors.append(str(exc))
        return
    files = dict(snapshot.files)

    skill_file = skill_dir / "SKILL.md"
    if skill_file not in files:
        errors.append(f"{pack_id}/{skill}: missing SKILL.md.")
        return

    try:
        metadata, body = parse_skill_markdown_text(
            read_regular_text(skill_file, root),
            skill_file.relative_to(root),
        )
    except (SkillpackError, UnicodeDecodeError) as exc:
        errors.append(str(exc))
        return

    unknown = set(metadata) - STANDARD_FRONTMATTER_FIELDS
    if unknown:
        errors.append(f"{skill_file}: unsupported frontmatter fields: {sorted(unknown)}")
    for field in ("name", "description"):
        if field not in metadata:
            errors.append(f"{skill_file}: missing required frontmatter field {field!r}.")
    if metadata.get("name") != skill:
        errors.append(
            f"{skill_file}: name {metadata.get('name')!r} must match directory {skill!r}."
        )
    if not KEBAB_RE.fullmatch(skill) or len(skill) > 64:
        errors.append(f"{skill_file}: skill name must be kebab-case and at most 64 characters.")

    description = metadata.get("description")
    if not isinstance(description, str):
        errors.append(f"{skill_file}: description must be a string.")
    else:
        description = " ".join(description.split())
        if not 80 <= len(description) <= 1024:
            errors.append(
                f"{skill_file}: description must be 80 to 1024 characters; found {len(description)}."
            )
        if "Use when" not in description or "Do not use" not in description:
            errors.append(
                f"{skill_file}: description must include explicit 'Use when' and 'Do not use' routing clauses."
            )

    if metadata.get("license") != "Apache-2.0":
        errors.append(f"{skill_file}: license must be Apache-2.0.")
    skill_metadata = metadata.get("metadata")
    if not isinstance(skill_metadata, dict):
        errors.append(f"{skill_file}: metadata must be a mapping.")
    else:
        for key, value in skill_metadata.items():
            if not isinstance(key, str) or not isinstance(value, str):
                errors.append(f"{skill_file}: metadata keys and values must be strings.")
        if skill_metadata.get("skillpack") != pack_id:
            errors.append(f"{skill_file}: metadata.skillpack must be {pack_id!r}.")
        if skill_metadata.get("version") != pack_version:
            errors.append(f"{skill_file}: metadata.version must be {pack_version!r}.")
        if skill_metadata.get("maturity") != pack_maturity:
            errors.append(f"{skill_file}: metadata.maturity must be {pack_maturity!r}.")

    line_count = body.count("\n") + 1
    estimated_tokens = len(body) / 4
    if line_count > 500:
        errors.append(f"{skill_file}: body exceeds 500 lines ({line_count}).")
    if estimated_tokens > 5000:
        errors.append(
            f"{skill_file}: body is approximately {estimated_tokens:.0f} tokens; keep below 5000."
        )

    missing_headings = _missing_operational_sections(body)
    if missing_headings:
        errors.append(
            f"{skill_file}: missing required headings for operational sections: "
            f"{sorted(missing_headings)}"
        )

    for required in (
        "references/guide.md",
        "references/checklist.md",
        "references/sources.md",
        "evals/evals.json",
    ):
        if skill_dir / required not in files:
            errors.append(f"{skill_dir}: missing required file {required}.")

    sidecar = skill_dir / "agents" / "openai.yaml"
    if sidecar not in files:
        errors.append(f"{skill_dir}: missing required file agents/openai.yaml.")
    else:
        _validate_openai_sidecar(root, skill, sidecar, errors)

    skill_absolute = Path(os.path.abspath(os.fspath(skill_dir)))
    resource_files = {
        path
        for path in files
        if path.relative_to(skill_dir).parts
        and path.relative_to(skill_dir).parts[0] in {"assets", "references", "scripts"}
    }
    for resource_name in ("assets", "references", "scripts"):
        directory = skill_dir / resource_name
        members = [
            path for path in resource_files if path.relative_to(skill_dir).parts[0] == resource_name
        ]
        if directory in dict(snapshot.directories) and not members:
            errors.append(f"{directory}: resource directory must not be empty.")
        if members and all(path.name.casefold() == "readme.md" for path in members):
            errors.append(f"{directory}: README-only resource directories are prohibited.")

    link_graph: dict[Path, list[Path]] = {}
    linked_directories: set[Path] = set()
    for markdown in sorted(path for path in files if path.suffix == ".md"):
        try:
            markdown_text = read_regular_text(markdown, root)
        except (SkillpackError, UnicodeDecodeError) as exc:
            errors.append(str(exc))
            continue
        for target in markdown_local_links_text(markdown_text):
            target_path = Path(os.path.abspath(os.fspath(markdown.parent / target)))
            try:
                target_path.relative_to(skill_absolute)
            except ValueError:
                errors.append(f"{markdown}: link escapes the skill directory: {target}")
                continue
            try:
                target_metadata = inspect_path(
                    target_path,
                    root,
                    allow_missing=True,
                )
            except SkillpackError as exc:
                errors.append(str(exc))
                continue
            if target_metadata is None:
                errors.append(f"{markdown}: broken relative link: {target}")
                continue
            link_graph.setdefault(markdown, []).append(target_path)
            if stat.S_ISDIR(target_metadata.st_mode):
                linked_directories.add(target_path)

    reachable: set[Path] = {skill_file}
    pending = [skill_file]
    while pending:
        source = pending.pop()
        for target in link_graph.get(source, []):
            if target in reachable:
                continue
            reachable.add(target)
            if target.suffix == ".md":
                pending.append(target)
    for resource in resource_files:
        if any(
            directory in reachable and resource.is_relative_to(directory)
            for directory in linked_directories
        ):
            reachable.add(resource)
    for resource in sorted(resource_files - reachable):
        errors.append(
            f"{resource}: runtime resource is not reachable from SKILL.md through local links."
        )

    for path in sorted(files):
        relative = path.relative_to(skill_dir)
        if (
            relative.parts
            and relative.parts[0] == "scripts"
            and "__pycache__" not in tuple(security_name_key(part) for part in relative.parts)
            and path.suffix.lower() in {".py", ".sh", ".bash", ".ps1", ".md", ".txt"}
        ):
            _validate_script(path, errors, root=root)

    eval_path = skill_dir / "evals" / "evals.json"
    if eval_path in files:
        eval_errors, _ = validate_eval_file(root, eval_path)
        errors.extend(eval_errors)

    for path, path_metadata in (*snapshot.directories, *snapshot.files):
        relative = path.relative_to(skill_dir)
        normalized_parts = tuple(security_name_key(part) for part in relative.parts)
        if "__pycache__" in normalized_parts or security_name_key(path.suffix) in {
            ".pyc",
            ".pyo",
        }:
            errors.append(
                f"{path}: cache or bytecode residue must be removed from canonical skill content."
            )
        if (
            relative.parts
            and normalized_parts[0] in {"assets", "references", "scripts"}
            and not runtime_resource_is_allowed(relative)
        ):
            errors.append(
                f"{path}: runtime-excluded credential, cache, or editor residue must be "
                "removed from canonical skill content."
            )
        if path in files and path_metadata.st_size > 1_000_000:
            warnings.append(f"{path}: file exceeds 1 MB; confirm it is necessary.")


def _validate_workflows(root: Path, errors: list[str]) -> None:
    workflow_root = root / ".github" / "workflows"
    try:
        snapshot = walk_tree(workflow_root, root, allow_missing=True)
    except SkillpackError as exc:
        errors.append(str(exc))
        return
    if (
        inspect_path(
            workflow_root,
            root,
            leaf_kind="directory",
            allow_missing=True,
        )
        is None
    ):
        errors.append("Missing .github/workflows directory.")
        return
    workflows = sorted(
        path for path, _metadata in snapshot.files if path.suffix in {".yml", ".yaml"}
    )
    if not workflows:
        errors.append("No GitHub Actions workflows found.")
        return
    for path in workflows:
        text = read_regular_text(path, root)
        if re.search(r"(?m)^\s*pull_request_target\s*:", text):
            errors.append(
                f"{path.relative_to(root)}: pull_request_target is prohibited for this public repository."
            )
        if not re.search(r"(?m)^permissions\s*:", text):
            errors.append(f"{path.relative_to(root)}: declare explicit workflow permissions.")
        if "persist-credentials: true" in text:
            errors.append(f"{path.relative_to(root)}: checkout credentials must not persist.")
        for match in re.finditer(r"(?m)^\s*uses:\s*([^@\s]+)@([^\s#]+)", text):
            action, reference = match.groups()
            if action.startswith("./"):
                continue
            if not re.fullmatch(r"[0-9a-f]{40}", reference):
                errors.append(
                    f"{path.relative_to(root)}: action {action!r} must be pinned to a full lowercase commit SHA."
                )
        if re.search(r"(?m)^\s*contents:\s*write\s*$", text):
            try:
                workflow = yaml.safe_load(text)
            except yaml.YAMLError:
                workflow = None
            allowed_jobs = {
                "release.yml": {"release"},
                "release-recovery.yml": {"resume"},
            }.get(path.name, set())
            write_jobs: set[str] = set()
            top_write = False
            if isinstance(workflow, dict):
                permissions = workflow.get("permissions", {})
                top_write = isinstance(permissions, dict) and permissions.get("contents") == "write"
                jobs = workflow.get("jobs", {})
                if isinstance(jobs, dict):
                    for job_id, job in jobs.items():
                        if not isinstance(job, dict):
                            continue
                        job_permissions = job.get("permissions", {})
                        if (
                            isinstance(job_permissions, dict)
                            and job_permissions.get("contents") == "write"
                        ):
                            write_jobs.add(str(job_id))
                            if job.get("environment") != "release":
                                errors.append(
                                    f"{path.relative_to(root)}: contents: write job "
                                    f"{job_id!r} must use the release environment."
                                )
            if top_write or not write_jobs or not write_jobs <= allowed_jobs:
                errors.append(
                    f"{path.relative_to(root)}: only release.yml or guarded "
                    "release-recovery.yml mutation jobs may request contents: write."
                )
        if re.search(r"(?m)^\s*issues:\s*write\s*$", text):
            try:
                workflow = yaml.safe_load(text)
            except yaml.YAMLError:
                workflow = None
            allowed_issue_jobs = {
                "publication-handoff.yml": {"notify"},
            }.get(path.name, set())
            issue_jobs: set[str] = set()
            top_write = False
            if isinstance(workflow, dict):
                permissions = workflow.get("permissions", {})
                top_write = isinstance(permissions, dict) and permissions.get("issues") == "write"
                jobs = workflow.get("jobs", {})
                if isinstance(jobs, dict):
                    for job_id, job in jobs.items():
                        if not isinstance(job, dict):
                            continue
                        job_permissions = job.get("permissions", {})
                        if (
                            isinstance(job_permissions, dict)
                            and job_permissions.get("issues") == "write"
                        ):
                            issue_jobs.add(str(job_id))
                            if job_permissions != {"contents": "read", "issues": "write"}:
                                errors.append(
                                    f"{path.relative_to(root)}: issues: write job {job_id!r} "
                                    "must have only contents: read and issues: write."
                                )
            if top_write or not issue_jobs or issue_jobs != allowed_issue_jobs:
                errors.append(
                    f"{path.relative_to(root)}: only the exact post-publication tracking job "
                    "may request issues: write."
                )


def validate_compatibility_report(
    root: Path,
    path: Path,
    *,
    pack: Pack | None = None,
    source_sha: str | None = None,
    now: dt.datetime | None = None,
    actor: str | None = None,
    actor_id: int | None = None,
    triggering_actor: str | None = None,
    policy: CompatibilityEvidencePolicy | None = None,
    schema_root: Path | None = None,
) -> tuple[list[str], dict[str, Any] | None]:
    """Validate a native-client report and its pack/SHA binding.

    Protected ingestion may supply the current protected policy and schema root while checking
    the pack and eval inventory from an older exact release-candidate commit.
    """

    errors: list[str] = []
    try:
        repository_relative(path, root)
        report_root = root
    except SkillpackError:
        report_root = Path(os.path.abspath(os.fspath(path.parent)))
    try:
        data = strict_load_json(path, root=report_root)
    except SkillpackError as exc:
        errors.append(str(exc))
        data = None
    schema = _load_schema(schema_root or root, "compatibility-report.schema.json", errors)
    if data is None or schema is None:
        return errors, data
    if data.get("schemaVersion") == 1:
        errors.append(
            f"{path}: compatibility report schemaVersion 1 is unsupported; "
            "migrate date/reviewer identity to the schemaVersion 2 testedAt contract."
        )
        return errors, data
    errors.extend(_schema_errors(data, schema, str(path)))
    if errors:
        return errors, data

    discovered_packs = discover_packs(root)
    skill_owners = {
        skill: candidate.id for candidate in discovered_packs for skill in candidate.skills
    }

    def owning_pack_ids(skills: tuple[str, str]) -> list[str]:
        return sorted({skill_owners[skill] for skill in skills if skill in skill_owners})

    boundary_errors, boundaries = validate_routing_boundaries(root, packs=discovered_packs)
    errors.extend(boundary_errors)
    boundaries_by_id = {boundary.id: boundary for boundary in boundaries}

    report_pack = data["pack"]
    if pack is None:
        pack = next(
            (candidate for candidate in discovered_packs if candidate.id == report_pack["id"]),
            None,
        )
        if pack is None:
            errors.append(f"{path}: pack.id names an unknown canonical pack.")
    if pack:
        expected = {
            "id": pack.id,
            "version": pack.version,
            "tag": pack.tag,
            "expectedSkills": pack.skills,
        }
        for key, value in expected.items():
            if report_pack[key] != value:
                errors.append(f"{path}: pack.{key} is {report_pack[key]!r}, expected {value!r}.")
        expected_routing: list[tuple[str, str]] = []
        expected_behavior: list[tuple[str, str]] = []
        for skill in pack.skills:
            eval_path = pack.path / "skills" / skill / "evals" / "evals.json"
            try:
                eval_data = json.loads(read_regular_text(eval_path, root))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError, SkillpackError) as exc:
                errors.append(f"{path}: could not load canonical evals for {skill}: {exc}")
                continue
            expected_routing.extend((skill, case["id"]) for case in eval_data.get("routing", []))
            expected_behavior.extend((skill, case["id"]) for case in eval_data.get("behavior", []))
        actual_routing = [(case["skill"], case["id"]) for case in data["cases"]["routing"]]
        actual_behavior = [(case["skill"], case["id"]) for case in data["cases"]["behavior"]]
        if actual_routing != expected_routing:
            errors.append(f"{path}: routing cases must cover every declared (skill, case ID).")
        if actual_behavior != expected_behavior:
            errors.append(f"{path}: behavior cases must cover every declared (skill, case ID).")
        pack_skill_set = set(pack.skills)
        expected_boundaries = [
            (
                boundary.id,
                case["id"],
                ("internal-pack" if len(owning_pack_ids(boundary.skills)) == 1 else "cross-pack"),
                list(boundary.skills),
                owning_pack_ids(boundary.skills),
                case["expectedSkills"],
            )
            for boundary in boundaries
            if set(boundary.skills) & pack_skill_set
            for case in boundary.cases
        ]
        actual_boundaries = [
            (
                case["boundaryId"],
                case["caseId"],
                case["scope"],
                case["boundarySkills"],
                case["installedPacks"],
                case["expectedSkills"],
            )
            for case in data["cases"]["boundaries"]
        ]
        if actual_boundaries != expected_boundaries:
            errors.append(
                f"{path}: boundary cases must cover every canonical boundary incident to the "
                "selected pack, including cross-pack cases, in canonical order with exact "
                "scope, skill, installed-pack, and expected-skill fields."
            )
    all_skill_names = set(skill_owners)
    for case in data["cases"]["boundaries"]:
        boundary = boundaries_by_id.get(case["boundaryId"])
        if boundary is None:
            errors.append(f"{path}: {case['caseId']} names an unknown canonical boundary.")
        else:
            canonical_cases = {item["id"]: item for item in boundary.cases}
            canonical_case = canonical_cases.get(case["caseId"])
            if canonical_case is None:
                errors.append(
                    f"{path}: {case['caseId']} is not a canonical case for {case['boundaryId']}."
                )
            owners = owning_pack_ids(boundary.skills)
            scope = "internal-pack" if len(owners) == 1 else "cross-pack"
            if case["scope"] != scope:
                errors.append(f"{path}: {case['caseId']} scope must be {scope!r}.")
            if case["boundarySkills"] != list(boundary.skills):
                errors.append(
                    f"{path}: {case['caseId']} boundarySkills must be {list(boundary.skills)!r}."
                )
            if case["installedPacks"] != owners:
                errors.append(f"{path}: {case['caseId']} installedPacks must be {owners!r}.")
            if (
                canonical_case is not None
                and case["expectedSkills"] != canonical_case["expectedSkills"]
            ):
                errors.append(
                    f"{path}: {case['caseId']} expectedSkills must match the canonical "
                    "boundary case."
                )
        expected_selection = case["expectedSkills"]
        observed = case["observedSkills"]
        if expected_selection != sorted(expected_selection):
            errors.append(f"{path}: {case['caseId']} expectedSkills must be sorted.")
        if observed != sorted(observed):
            errors.append(f"{path}: {case['caseId']} observedSkills must be sorted.")
        unknown = sorted((set(expected_selection) | set(observed)) - all_skill_names)
        if unknown:
            errors.append(f"{path}: {case['caseId']} names unknown skills {unknown!r}.")
        outside_boundary = sorted(
            (set(expected_selection) | set(observed)) - set(case["boundarySkills"])
        )
        if outside_boundary:
            errors.append(
                f"{path}: {case['caseId']} selections must be limited to boundarySkills; "
                f"found {outside_boundary!r}."
            )
        selection_matches = observed == expected_selection
        if case["passed"] is not selection_matches:
            errors.append(
                f"{path}: {case['caseId']} passed must equal the observed/expected "
                "selection comparison."
            )
    if source_sha and report_pack["sourceSha"] != source_sha:
        errors.append(
            f"{path}: pack.sourceSha is {report_pack['sourceSha']!r}, expected {source_sha!r}."
        )
    if report_pack["expectedSkills"] != data["installation"]["discoveredSkills"]:
        errors.append(f"{path}: discoveredSkills must exactly match expectedSkills order.")
    effective_policy = policy or load_repository(root).compatibility_evidence
    errors.extend(
        evidence_freshness_errors(
            data["testedAt"],
            effective_policy,
            now=now,
            label=str(path),
        )
    )
    maintainers = (
        [str(item["github"]) for item in pack.maintainers if item.get("github")] if pack else []
    )
    errors.extend(
        reviewer_authorization_errors(
            data["reviewer"],
            effective_policy,
            actor=actor,
            actor_id=actor_id,
            triggering_actor=triggering_actor,
            pack_maintainers=maintainers,
            label=str(path),
        )
    )
    all_cases = [
        *data["cases"]["routing"],
        *data["cases"]["behavior"],
        *data["cases"]["boundaries"],
    ]
    if data["verdict"]["status"] == "passed" and not all(case["passed"] for case in all_cases):
        errors.append(f"{path}: a passed verdict cannot contain failed cases.")
    if data["reviewer"]["verdict"] != data["verdict"]["status"]:
        errors.append(f"{path}: reviewer.verdict must match verdict.status.")
    return errors, data


def _validate_vendor_artifact_structure(root: Path, packs: list[Pack], errors: list[str]) -> None:
    """Structurally validate generated vendor artifacts without claiming native execution."""

    claude = _load_json(root / ".claude-plugin" / "marketplace.json", errors, root=root)
    codex = _load_json(root / ".agents" / "plugins" / "marketplace.json", errors, root=root)
    public_packs = select_packs(packs, "public")
    if claude:
        expected = [pack for pack in public_packs if "claude-code" in pack.targets]
        entries = claude.get("plugins")
        if not isinstance(entries, list) or [item.get("name") for item in entries] != [
            pack.id for pack in expected
        ]:
            errors.append(".claude-plugin/marketplace.json: plugins must match Claude targets.")
        else:
            for item, pack in zip(entries, expected, strict=True):
                wanted_source: str | dict[str, str]
                wanted_source = {
                    "source": "git-subdir",
                    "url": load_repository(root).git_url,
                    "path": pack.relative_path,
                    "ref": pack.published_tag,
                    "sha": pack.source_sha,
                }
                if item.get("source") != wanted_source:
                    errors.append(
                        f".claude-plugin/marketplace.json: {pack.id} has invalid source metadata."
                    )
    if codex:
        expected = [pack for pack in public_packs if "codex" in pack.targets]
        entries = codex.get("plugins")
        if not isinstance(entries, list) or [item.get("name") for item in entries] != [
            pack.id for pack in expected
        ]:
            errors.append(".agents/plugins/marketplace.json: plugins must match Codex targets.")
        else:
            for item, pack in zip(entries, expected, strict=True):
                source = item.get("source")
                if not isinstance(source, dict) or source.get("sha") != pack.source_sha:
                    errors.append(
                        f".agents/plugins/marketplace.json: {pack.id} must pin latest-release."
                    )

    for pack in packs:
        targets = {
            "claude-code": pack.path / ".claude-plugin" / "plugin.json",
            "codex": pack.path / ".codex-plugin" / "plugin.json",
        }
        for target, path in targets.items():
            if target in pack.targets:
                manifest = _load_json(path, errors, root=root)
                if manifest and manifest.get("name") != pack.id:
                    errors.append(f"{path}: manifest name must be {pack.id!r}.")
                if (
                    manifest
                    and target == "claude-code"
                    and manifest.get("description") != pack.short_description
                ):
                    errors.append(
                        f"{path}: description must match the pack's authored "
                        "interface.short-description."
                    )
                if manifest and target == "codex":
                    interface = manifest.get("interface")
                    expected_prompts = [item["prompt"] for item in pack.starter_prompts]
                    if not isinstance(interface, dict):
                        errors.append(f"{path}: interface must be an object.")
                    else:
                        expected = {
                            "shortDescription": pack.short_description,
                            "longDescription": pack.description,
                            "defaultPrompt": expected_prompts,
                        }
                        for key, value in expected.items():
                            if interface.get(key) != value:
                                errors.append(
                                    f"{path}: interface.{key} must match canonical pack metadata."
                                )
            else:
                try:
                    stale_metadata = inspect_path(
                        path,
                        root,
                        leaf_kind="file",
                        allow_missing=True,
                    )
                except SkillpackError as exc:
                    errors.append(str(exc))
                    continue
                if stale_metadata is not None:
                    errors.append(f"{path}: stale manifest exists for undeclared target {target}.")


def _placeholder_hits(root: Path) -> list[str]:
    hits: list[str] = []
    try:
        config = load_repository(root)
    except SkillpackError:
        config = None
    excluded = {security_name_key(part) for part in PLACEHOLDER_SCAN_EXCLUDED_PARTS}
    snapshot = walk_tree(
        root,
        root,
        prune_directory=lambda path: security_name_key(path.name) in excluded,
    )
    for path, _metadata in snapshot.files:
        relative = path.relative_to(root)
        # The placeholder constants themselves are remediation logic, not unresolved
        # repository identity.
        if relative.as_posix() in {
            "src/skillpack_tools/configure.py",
            "src/skillpack_tools/validate.py",
        }:
            continue
        try:
            text = read_regular_text(path, root)
        except (UnicodeDecodeError, OSError):
            continue
        for placeholder in PLACEHOLDER_PATTERNS:
            if placeholder == "agent-skillpacks" and config and config.name == placeholder:
                continue
            if placeholder == "Agent Skillpacks" and config and config.project_name == placeholder:
                continue
            if placeholder in text:
                hits.append(f"{relative} contains {placeholder!r}")
        if relative.as_posix() == "CITATION.cff":
            for misleading in ("version:", "date-released:"):
                if re.search(rf"(?m)^{re.escape(misleading)}", text):
                    hits.append(
                        f"{relative} contains misleading repository-wide {misleading.rstrip(':')}"
                    )
    return hits


def validate_repository(
    root: Path,
    *,
    check_generated: bool = False,
    strict_placeholders: bool = False,
    pack_filter: str | None = None,
    _generated_files: GeneratedFiles | None = None,
) -> ValidationResult:
    root = Path(os.path.abspath(os.fspath(root)))
    errors: list[str] = []
    warnings: list[str] = []
    try:
        config = load_repository(root)
    except SkillpackError as exc:
        return ValidationResult(errors=[str(exc)], warnings=[])
    _validate_workflows(root, errors)

    repo_schema = _load_schema(root, "repository.schema.json", errors)
    pack_schema = _load_schema(root, "skillpack.schema.json", errors)
    catalog_schema = _load_schema(root, "catalog.schema.json", errors)
    generated_schema = _load_schema(root, "generated-files.schema.json", errors)
    _load_schema(root, "eval-report.schema.json", errors)
    _load_schema(root, "routing-boundaries.schema.json", errors)
    _load_schema(root, "compatibility-report.schema.json", errors)
    _load_schema(root, "compatibility-evidence-envelope.schema.json", errors)
    _load_schema(root, "publication-record.schema.json", errors)
    _load_schema(root, "release-metadata.schema.json", errors)
    _load_schema(root, "release-intent.schema.json", errors)
    repository_configuration_errors = (
        _schema_errors(config.raw, repo_schema, "repository.yaml") if repo_schema else []
    )
    errors.extend(repository_configuration_errors)
    if repo_schema is None or repository_configuration_errors:
        return ValidationResult(errors=sorted(set(errors)), warnings=sorted(set(warnings)))

    try:
        canonical_before = walk_tree(root / "packs", root, allow_missing=True)
        packs = discover_packs(root)
    except SkillpackError as exc:
        errors.append(str(exc))
        return ValidationResult(errors=sorted(set(errors)), warnings=sorted(set(warnings)))
    if not packs:
        errors.append("No skillpack manifests found under packs/*/*/.")
    if pack_filter is not None and pack_filter not in {pack.id for pack in packs}:
        errors.append(f"Unknown pack filter: {pack_filter!r}.")

    _validate_skill_asset_schemas(root, config, errors)

    pack_ids: set[str] = set()
    all_skill_names: set[str] = set()
    for pack in packs:
        label = f"{pack.relative_path}/skillpack.yaml"
        manifest_errors: list[str] = []
        if pack_schema:
            manifest_errors = _schema_errors(pack.raw, pack_schema, label)
            errors.extend(manifest_errors)
        if not manifest_errors:
            errors.extend(validate_pack_lifecycle(pack))
        if pack.id in pack_ids:
            errors.append(f"Duplicate pack ID: {pack.id}")
        pack_ids.add(pack.id)

        expected_id = (
            pack.subject if pack.language == "shared" else f"{pack.language}-{pack.subject}"
        )
        if pack.id != expected_id:
            errors.append(f"{label}: id must be {expected_id!r} for this language/subject path.")
        expected_path = root / "packs" / pack.language / pack.subject
        if repository_relative(pack.path, root) != repository_relative(expected_path, root):
            errors.append(f"{label}: path must be packs/{pack.language}/{pack.subject}/.")
        if not SEMVER_RE.fullmatch(pack.version):
            errors.append(f"{label}: invalid Semantic Version {pack.version!r}.")
        skills_root = pack.path / "skills"
        try:
            skills_metadata = inspect_path(
                skills_root,
                root,
                leaf_kind="directory",
                allow_missing=True,
            )
            skill_snapshot = walk_tree(skills_root, root) if skills_metadata is not None else None
        except SkillpackError as exc:
            errors.append(str(exc))
            skill_snapshot = None
        actual_skill_dirs = (
            {
                path.name
                for path, _metadata in skill_snapshot.directories
                if len(path.relative_to(skills_root).parts) == 1 and not path.name.startswith(".")
            }
            if skill_snapshot is not None
            else set()
        )
        declared = set(pack.skills)
        for missing in sorted(declared - actual_skill_dirs):
            errors.append(f"{label}: declared skill directory is missing: {missing}")
        for undeclared in sorted(actual_skill_dirs - declared):
            errors.append(f"{label}: undeclared skill directory exists: {undeclared}")
        for skill in pack.skills:
            if skill in all_skill_names:
                errors.append(f"Skill name is not globally unique: {skill}")
            all_skill_names.add(skill)

        for required in ("README.md", "CHANGELOG.md", "tests/compatibility/expected-skills.json"):
            try:
                required_metadata = inspect_path(
                    pack.path / required,
                    root,
                    leaf_kind="file",
                    allow_missing=True,
                )
            except SkillpackError as exc:
                errors.append(str(exc))
                continue
            if required_metadata is None:
                errors.append(f"{pack.relative_path}: missing required file {required}.")

    boundary_errors, _boundaries = validate_routing_boundaries(root, packs=packs)
    errors.extend(boundary_errors)

    for pack in packs:
        if pack_filter is not None and pack.id != pack_filter:
            continue
        for skill in pack.skills:
            _validate_skill(
                root,
                pack.id,
                pack.version,
                pack.maturity,
                skill,
                pack.path / "skills" / skill,
                errors,
                warnings,
            )

    catalog = _load_json(root / "catalog.json", errors, root=root)
    if catalog is not None and catalog_schema is not None:
        errors.extend(_schema_errors(catalog, catalog_schema, "catalog.json"))
    generated_manifest = _load_json(
        root / "dist" / "generated-files.json",
        errors,
        root=root,
    )
    if generated_manifest is not None and generated_schema is not None:
        errors.extend(
            _schema_errors(
                generated_manifest,
                generated_schema,
                "dist/generated-files.json",
            )
        )
        entries = generated_manifest.get("files", [])
        if isinstance(entries, list):
            paths = [item.get("path") for item in entries if isinstance(item, dict)]
            if paths != sorted(paths) or len(paths) != len(set(paths)):
                errors.append("dist/generated-files.json: file paths must be unique and sorted.")
            for item in entries:
                if not isinstance(item, dict) or not isinstance(item.get("path"), str):
                    continue
                generated_path = root / item["path"]
                try:
                    metadata = inspect_path(
                        generated_path,
                        root,
                        leaf_kind="file",
                        allow_missing=True,
                    )
                except SkillpackError as exc:
                    errors.append(str(exc))
                    continue
                if metadata is None:
                    errors.append(
                        f"dist/generated-files.json: missing generated file {item['path']}."
                    )
                    continue
                try:
                    generated_bytes = read_regular_bytes(generated_path, root)
                except SkillpackError as exc:
                    errors.append(str(exc))
                    continue
                if item.get("sha256") != sha256_bytes(generated_bytes):
                    errors.append(f"dist/generated-files.json: hash mismatch for {item['path']}.")
                if item.get("size") != len(generated_bytes):
                    errors.append(f"dist/generated-files.json: size mismatch for {item['path']}.")
                mode = f"{metadata.st_mode & 0o777:04o}"
                if os.name != "nt" and item.get("mode") != mode:
                    errors.append(f"dist/generated-files.json: mode mismatch for {item['path']}.")

    _validate_vendor_artifact_structure(root, packs, errors)

    try:
        report_snapshot = walk_tree(
            root / "compatibility" / "reports",
            root,
            allow_missing=True,
        )
    except SkillpackError as exc:
        errors.append(str(exc))
        report_paths: list[Path] = []
    else:
        report_paths = sorted(
            path
            for path, _metadata in report_snapshot.files
            if path.parent == root / "compatibility" / "reports" and path.suffix == ".json"
        )
    for report_path in report_paths:
        report_errors, _ = validate_compatibility_report(root, report_path)
        errors.extend(report_errors)

    expected_catalog_skills = {pack.id: pack.skills for pack in packs}
    for pack in packs:
        expected_path = pack.path / "tests" / "compatibility" / "expected-skills.json"
        data = _load_json(expected_path, errors, root=root)
        if data and data.get("skills") != expected_catalog_skills[pack.id]:
            errors.append(f"{expected_path}: skills must exactly match skillpack.yaml order.")

    if check_generated:
        try:
            if _generated_files is None:
                apply_generated_files(root, check=True)
            else:
                _reconcile_generated_files(root, check=True, expected=_generated_files)
        except SkillpackError as exc:
            errors.append(str(exc))

    try:
        placeholder_hits = _placeholder_hits(root)
    except SkillpackError as exc:
        errors.append(str(exc))
    else:
        if placeholder_hits:
            target = errors if strict_placeholders else warnings
            target.extend(placeholder_hits)

    excluded = {security_name_key(part) for part in RESIDUE_SCAN_EXCLUDED_PARTS}
    tracked_paths = _tracked_repository_paths(root)
    unsafe_directories: list[Path] = []

    def prune_residue_directory(path: Path) -> bool:
        relative = path.relative_to(root)
        key = security_name_key(path.name)
        if relative in RESIDUE_LOCAL_DIRECTORIES:
            return True
        if key not in excluded and not security_sensitive_path(relative):
            return False
        tracked_descendant = tracked_paths is None or any(
            tracked == relative or relative in tracked.parents for tracked in tracked_paths
        )
        if tracked_descendant:
            unsafe_directories.append(relative)
        return True

    try:
        residue = walk_tree(
            root,
            root,
            prune_directory=prune_residue_directory,
        )
    except SkillpackError as exc:
        errors.append(str(exc))
    else:
        for relative in unsafe_directories:
            errors.append(
                f"{relative.as_posix()}: tracked cache, credential, or editor directory "
                "must not be committed."
            )
        for path, _metadata in residue.files:
            relative = path.relative_to(root)
            if relative in RESIDUE_LOCAL_FILES:
                continue
            name = security_name_key(path.name)
            suffix = security_name_key(path.suffix)
            unsafe_environment = name.startswith(".env.") and path.name != ".env.example"
            if name in _CREDENTIAL_NAMES or suffix in _CREDENTIAL_SUFFIXES or unsafe_environment:
                errors.append(f"{relative.as_posix()}: credential file must not be committed.")
            elif security_sensitive_path(relative, allow_env_example_file=True) and (
                tracked_paths is None or relative in tracked_paths
            ):
                errors.append(
                    f"{relative.as_posix()}: tracked cache, credential, or editor file "
                    "must not be committed."
                )

    try:
        canonical_after = walk_tree(root / "packs", root, allow_missing=True)
    except SkillpackError as exc:
        errors.append(str(exc))
    else:
        before_nodes = {
            repository_relative(path, root): metadata
            for path, metadata in (*canonical_before.directories, *canonical_before.files)
        }
        after_nodes = {
            repository_relative(path, root): metadata
            for path, metadata in (*canonical_after.directories, *canonical_after.files)
        }
        if set(before_nodes) != set(after_nodes) or any(
            not same_identity(metadata, after_nodes[path])
            for path, metadata in before_nodes.items()
        ):
            errors.append("Canonical pack content changed during repository validation.")

    return ValidationResult(errors=sorted(set(errors)), warnings=sorted(set(warnings)))


def raise_for_result(result: ValidationResult) -> None:
    if result.errors:
        raise SkillpackError(
            "Repository validation failed:\n" + "\n".join(f"  - {e}" for e in result.errors)
        )
