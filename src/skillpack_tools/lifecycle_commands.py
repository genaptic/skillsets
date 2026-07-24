from __future__ import annotations

import datetime as dt
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from .generate import GeneratedFiles, apply_generated_files, build_generated_files
from .lifecycle import semantic_version_key, validate_pack_lifecycle
from .models import Pack, get_pack
from .path_safety import (
    inspect_path,
    read_regular_bytes,
    remove_empty_directory,
    safe_atomic_write_bytes,
    unlink_regular,
    walk_tree,
)
from .schema_validation import load_json_schema, validate_schema_instance
from .util import (
    SkillpackError,
    dump_yaml,
    json_text,
    parse_skill_markdown_text,
    rollback_after_failure,
    sha256_bytes,
)

Operation = Literal["prepare-release", "begin-development"]
_DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")
_PREPARATION_BEGIN = "<!-- BEGIN RELEASE PREPARATION NOTE -->"
_PREPARATION_END = "<!-- END RELEASE PREPARATION NOTE -->"


@dataclass(frozen=True)
class _Snapshot:
    content: bytes | None
    mode: int


def _remove_readonly_and_retry(
    function: Callable[[str], object],
    path: str,
    error: BaseException,
) -> None:
    """Clear a Windows read-only bit and retry exactly one failed removal."""

    if os.name != "nt" or not isinstance(error, PermissionError):
        raise error
    os.chmod(path, stat.S_IWRITE)
    function(path)


def _remove_temporary_tree(path: Path) -> None:
    if sys.version_info >= (3, 12):
        shutil.rmtree(path, onexc=_remove_readonly_and_retry)
        return

    def legacy_callback(
        function: Callable[[str], object],
        failed_path: str,
        exc_info: tuple[type[BaseException], BaseException, object],
    ) -> None:
        _remove_readonly_and_retry(function, failed_path, exc_info[1])

    shutil.rmtree(path, onerror=legacy_callback)


def _isolated_git_environment() -> dict[str, str]:
    environment = {
        key: value for key, value in os.environ.items() if not key.upper().startswith("GIT_")
    }
    environment.update(
        {
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_LFS_SKIP_SMUDGE": "1",
            "GIT_TERMINAL_PROMPT": "0",
        }
    )
    return environment


def _require_clean_worktree(root: Path) -> str:
    if not (root / ".git").exists():
        raise SkillpackError("Lifecycle preparation requires a Git worktree.")
    git_environment = _isolated_git_environment()
    completed = subprocess.run(
        [
            "git",
            "-c",
            "core.longpaths=true",
            "-C",
            str(root),
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
        ],
        check=False,
        capture_output=True,
        text=True,
        env=git_environment,
    )
    if completed.returncode != 0:
        raise SkillpackError(f"Could not inspect Git worktree: {completed.stderr.strip()}")
    if completed.stdout:
        raise SkillpackError("Lifecycle preparation requires a clean Git worktree.")
    head = subprocess.run(
        ["git", "-c", "core.longpaths=true", "-C", str(root), "rev-parse", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
        env=git_environment,
    )
    if head.returncode != 0 or not re.fullmatch(r"[0-9a-f]{40}\n?", head.stdout):
        raise SkillpackError("Lifecycle preparation requires a resolvable Git HEAD.")
    return head.stdout.strip()


def _frontmatter_text(metadata: dict[str, Any], body: str) -> str:
    return f"---\n{dump_yaml(metadata)}---\n{body}"


def _skill_updates(pack: Pack, *, version: str, maturity: str) -> dict[str, str]:
    changes: dict[str, str] = {}
    for skill in pack.skills:
        path = pack.path / "skills" / skill / "SKILL.md"
        text = path.read_text(encoding="utf-8")
        metadata, body = parse_skill_markdown_text(text, path.relative_to(pack.root))
        skill_metadata = metadata.get("metadata")
        if not isinstance(skill_metadata, dict):
            raise SkillpackError(f"{path.relative_to(pack.root)}: metadata must be a mapping.")
        if skill_metadata.get("skillpack") != pack.id:
            raise SkillpackError(
                f"{path.relative_to(pack.root)}: metadata.skillpack does not match {pack.id}."
            )
        skill_metadata["version"] = version
        skill_metadata["maturity"] = maturity
        changes[path.relative_to(pack.root).as_posix()] = _frontmatter_text(metadata, body)
    return changes


def _finalize_changelog(
    text: str,
    *,
    old_version: str,
    version: str,
    release_date: str,
) -> str:
    if text.count("## [Unreleased]") != 1:
        raise SkillpackError("CHANGELOG.md must contain exactly one ## [Unreleased] heading.")
    if re.search(rf"(?m)^## \[{re.escape(version)}\](?:\s|$)", text):
        raise SkillpackError(f"CHANGELOG.md already contains a {version} release section.")
    match = re.search(r"(?ms)^## \[Unreleased\]\s*\n(?P<body>.*?)(?=^## \[|\Z)", text)
    if match is None:
        raise SkillpackError("Could not isolate the exact [Unreleased] changelog block.")
    body = match.group("body").strip()
    if not body:
        raise SkillpackError("The [Unreleased] changelog block is empty.")
    if (
        body.count(_PREPARATION_BEGIN) != body.count(_PREPARATION_END)
        or body.count(_PREPARATION_BEGIN) > 1
    ):
        raise SkillpackError("CHANGELOG.md has malformed release-preparation note markers.")
    if _PREPARATION_BEGIN in body:
        body = re.sub(
            rf"(?ms)^\s*{re.escape(_PREPARATION_BEGIN)}\s*$.*?^\s*"
            rf"{re.escape(_PREPARATION_END)}\s*$\s*",
            "",
            body,
        ).strip()
    body = body.replace(f"`{old_version}`", f"`{version}`")
    body = body.replace("release-candidate", "release")
    body = body.replace("release candidate", "release")
    unresolved = (
        "has not been published",
        "before requesting exact-sha",
        "before creating a release",
        "freeze the candidate",
        "release-candidate",
    )
    if any(marker in body.casefold() for marker in unresolved):
        raise SkillpackError("CHANGELOG.md contains unresolved release-candidate wording.")
    replacement = f"## [Unreleased]\n\n## [{version}] - {release_date}\n\n{body}\n\n"
    return text[: match.start()] + replacement + text[match.end() :].lstrip("\n")


def _candidate_pack(pack: Pack, raw: dict[str, Any]) -> Pack:
    candidate = Pack(root=pack.root, path=pack.path, raw=raw)
    schema = load_json_schema(
        pack.root / "schemas" / "skillpack.schema.json",
        label="schemas/skillpack.schema.json",
        root=pack.root,
    )
    validate_schema_instance(raw, schema, label=f"{pack.relative_path}/skillpack.yaml")
    errors = validate_pack_lifecycle(candidate)
    if errors:
        raise SkillpackError("Invalid lifecycle transition:\n" + "\n".join(errors))
    return candidate


def _prepare_canonical_changes(
    root: Path,
    pack_id: str,
    *,
    operation: Operation,
    release_date: str | None = None,
    version: str | None = None,
) -> tuple[Pack, dict[str, str]]:
    pack = get_pack(root, pack_id)
    raw = json.loads(json.dumps(pack.raw))
    changes: dict[str, str] = {}
    if operation == "prepare-release":
        if pack.visibility != "public":
            raise SkillpackError("Maintainer-only packs cannot enter a formal release.")
        if pack.publication_state == "withdrawn":
            raise SkillpackError("Withdrawn packs cannot be prepared for release.")
        if release_date is None:
            raise SkillpackError("prepare-release requires an explicit release date.")
        try:
            parsed_date = dt.date.fromisoformat(release_date)
        except ValueError as exc:
            raise SkillpackError("Release date must use YYYY-MM-DD.") from exc
        if parsed_date > dt.date.today():
            raise SkillpackError("Release date cannot be in the future.")
        target_version = version or pack.version
        target_key = semantic_version_key(target_version)
        if target_key < semantic_version_key(pack.version):
            raise SkillpackError("prepare-release cannot lower the current pack version.")
        if pack.published_version is not None and target_key <= semantic_version_key(
            pack.published_version
        ):
            raise SkillpackError(
                "A new release version must exceed the immutable latest public release."
            )
        raw["version"] = target_version
        raw["maturity"] = "stable"
        candidate = _candidate_pack(pack, raw)
        changes.update(_skill_updates(pack, version=target_version, maturity="stable"))
        changelog_path = pack.path / "CHANGELOG.md"
        changelog = changelog_path.read_text(encoding="utf-8")
        changes[changelog_path.relative_to(root).as_posix()] = _finalize_changelog(
            changelog,
            old_version=pack.version,
            version=target_version,
            release_date=release_date,
        )
    else:
        if pack.publication_state != "published" or pack.latest_release is None:
            raise SkillpackError("begin-development requires an existing published release.")
        if pack.version != pack.published_version:
            raise SkillpackError(
                "The current source version is already ahead of latest-release; publish and "
                "reconcile it, or revert the prepared/candidate change, before beginning "
                "another development version."
            )
        if version is None:
            raise SkillpackError("begin-development requires --next-version.")
        if semantic_version_key(version) <= semantic_version_key(pack.published_version or ""):
            raise SkillpackError("The next development version must exceed the latest release.")
        if semantic_version_key(version) <= semantic_version_key(pack.version):
            raise SkillpackError("The next development version must exceed the current version.")
        raw["version"] = version
        raw["maturity"] = "release-candidate"
        candidate = _candidate_pack(pack, raw)
        changes.update(_skill_updates(pack, version=version, maturity="release-candidate"))
        changelog_path = pack.path / "CHANGELOG.md"
        changelog = changelog_path.read_text(encoding="utf-8")
        if changelog.count("## [Unreleased]") != 1:
            raise SkillpackError("CHANGELOG.md must retain exactly one [Unreleased] section.")

    manifest = pack.path / "skillpack.yaml"
    changes[manifest.relative_to(root).as_posix()] = dump_yaml(candidate.raw)
    return candidate, dict(sorted(changes.items()))


def _copy_for_preview(root: Path, changes: dict[str, str], *, head: str) -> Path:
    """Create an isolated preview without duplicating a Git object database."""

    temporary_parent = Path(os.path.realpath(tempfile.mkdtemp(prefix="skillpack-lifecycle-")))
    temporary = temporary_parent / "repository"
    hooks = temporary_parent / "empty-hooks"
    hooks.mkdir()
    git_environment = _isolated_git_environment()

    try:
        subprocess.run(
            [
                "git",
                "-c",
                f"core.hooksPath={hooks}",
                "-c",
                "core.longpaths=true",
                "clone",
                "--quiet",
                "--shared",
                "--no-checkout",
                "--",
                str(root),
                str(temporary),
            ],
            check=True,
            capture_output=True,
            env=git_environment,
        )
        subprocess.run(
            [
                "git",
                "-c",
                f"core.hooksPath={hooks}",
                "-c",
                "core.longpaths=true",
                "-C",
                str(temporary),
                "checkout",
                "--quiet",
                "--detach",
                head,
            ],
            check=True,
            capture_output=True,
            env=git_environment,
        )
        for relative, content in changes.items():
            path = temporary / relative
            metadata = inspect_path(path, temporary, leaf_kind="file", allow_missing=True)
            safe_atomic_write_bytes(
                path,
                content.encode("utf-8"),
                temporary,
                mode=(metadata.st_mode & 0o777) if metadata is not None else 0o644,
                expected=metadata,
            )
    except BaseException as exc:
        rollback_after_failure(
            exc,
            lambda: _remove_temporary_tree(temporary_parent),
            label="Lifecycle preview creation",
        )
        if isinstance(exc, (OSError, subprocess.CalledProcessError)):
            raise SkillpackError("Could not create the exact-HEAD lifecycle preview.") from exc
        raise
    return temporary


def _plan_digest(plan: dict[str, Any]) -> str:
    payload = json.dumps(plan, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return sha256_bytes(payload.encode("utf-8"))


def build_lifecycle_plan(
    root: Path,
    pack_id: str,
    *,
    operation: Operation,
    release_date: str | None = None,
    version: str | None = None,
) -> dict[str, Any]:
    root = Path(os.path.abspath(os.fspath(root)))
    head = _require_clean_worktree(root)
    root_result = apply_generated_files(root, check=True)
    root_generated = getattr(root_result, "generated_files", None)
    candidate, changes = _prepare_canonical_changes(
        root,
        pack_id,
        operation=operation,
        release_date=release_date,
        version=version,
    )
    preimages = {
        relative: sha256_bytes(read_regular_bytes(root / relative, root)) for relative in changes
    }
    preview_root = _copy_for_preview(root, changes, head=head)
    try:
        preview_result = apply_generated_files(preview_root)
        preview_generated = getattr(preview_result, "generated_files", None)
        from .publication import (
            _generated_output_records,
            _git_patch_and_paths,
            _path_record,
        )
        from .validate import validate_repository

        result = validate_repository(
            preview_root,
            check_generated=True,
            strict_placeholders=True,
            _generated_files=preview_generated,
        )
        if not result.ok:
            raise SkillpackError(
                "Lifecycle preview failed repository validation:\n" + "\n".join(result.errors)
            )
        candidates = sorted(
            _controlled_paths(root, list(changes), generated=root_generated)
            | _controlled_paths(preview_root, list(changes), generated=preview_generated)
        )
        patch, changed_paths = _git_patch_and_paths(preview_root, candidates)
        changed_files: list[dict[str, str | None]] = []
        for relative in changed_paths:
            before_sha, before_mode = _path_record(root, relative)
            after_sha, after_mode = _path_record(preview_root, relative)
            changed_files.append(
                {
                    "path": relative,
                    "beforeSha256": before_sha,
                    "afterSha256": after_sha,
                    "beforeMode": before_mode,
                    "afterMode": after_mode,
                }
            )
        generated_outputs = _generated_output_records(preview_root, preview_generated)
        generated_changes = [item for item in changed_files if item["path"] not in changes]
    except BaseException as exc:
        rollback_after_failure(
            exc,
            lambda: _remove_temporary_tree(preview_root.parent),
            label="Lifecycle preview",
        )
        raise
    else:
        _remove_temporary_tree(preview_root.parent)
    base = {
        "schemaVersion": 2,
        "operation": operation,
        "pack": candidate.id,
        "version": candidate.version,
        "maturity": candidate.maturity,
        "releaseDate": release_date,
        "baseCommit": head,
        "preimages": preimages,
        "canonicalChanges": list(changes),
        "generatedChanges": generated_changes,
        "changedFiles": changed_files,
        "generatedOutputs": generated_outputs,
        "generatedOutputSetSha256": sha256_bytes(
            json.dumps(generated_outputs, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ),
        "unifiedPatch": patch,
        "patch": patch,
    }
    return {**base, "planDigest": _plan_digest(base)}


def _controlled_paths(
    root: Path,
    canonical: list[str],
    *,
    generated: GeneratedFiles | set[str] | None = None,
) -> set[str]:
    paths = set(canonical)
    if generated is None:
        paths.update(build_generated_files(root))
    else:
        paths.update(generated)
    for generated_root in (
        root / ".claude-plugin",
        root / ".agents" / "plugins",
        root / "dist" / "public",
        root / "dist" / "preview",
        root / "dist" / "dev",
        root / "dist" / "install",
        root / "dist" / "opencode",
    ):
        snapshot = walk_tree(generated_root, root, allow_missing=True)
        paths.update(path.relative_to(root).as_posix() for path, _metadata in snapshot.files)
    legacy = root / "dist" / "index.html"
    if legacy.is_file():
        paths.add("dist/index.html")
    return paths


def _snapshots(root: Path, paths: set[str]) -> dict[str, _Snapshot]:
    result: dict[str, _Snapshot] = {}
    for relative in sorted(paths):
        path = root / relative
        metadata = inspect_path(path, root, leaf_kind="file", allow_missing=True)
        result[relative] = _Snapshot(
            content=read_regular_bytes(path, root) if metadata is not None else None,
            mode=(metadata.st_mode & 0o777) if metadata is not None else 0o644,
        )
    return result


def _restore(root: Path, snapshots: dict[str, _Snapshot]) -> None:
    absent_parents: set[Path] = set()
    for relative, snapshot in snapshots.items():
        path = root / relative
        current = inspect_path(path, root, leaf_kind="file", allow_missing=True)
        if snapshot.content is None:
            if current is not None:
                unlink_regular(path, root, expected=current)
            absent_parents.add(path.parent)
        else:
            safe_atomic_write_bytes(
                path,
                snapshot.content,
                root,
                mode=snapshot.mode,
                expected=current,
            )
    for directory in sorted(absent_parents, key=lambda item: len(item.parts), reverse=True):
        current = directory
        while current != root:
            metadata = inspect_path(current, root, leaf_kind="directory", allow_missing=True)
            if metadata is None:
                break
            try:
                remove_empty_directory(current, root, expected=metadata)
            except OSError:
                break
            current = current.parent


def _verify_applied_plan(
    root: Path,
    plan: dict[str, Any],
    generated_files: GeneratedFiles | None = None,
) -> None:
    from .publication import _generated_output_records, _git_patch_and_paths, _path_record

    generated = (
        _generated_output_records(root, generated_files)
        if generated_files is not None
        else _generated_output_records(root)
    )
    if generated != plan["generatedOutputs"]:
        raise SkillpackError("Generated outputs differ from the reviewed lifecycle plan.")
    digest = sha256_bytes(
        json.dumps(generated, sort_keys=True, separators=(",", ":")).encode("utf-8")
    )
    if digest != plan["generatedOutputSetSha256"]:
        raise SkillpackError("Generated output-set digest differs from the lifecycle plan.")
    candidates = [str(item["path"]) for item in plan["changedFiles"]]
    patch, changed_paths = _git_patch_and_paths(root, candidates)
    if patch != plan["unifiedPatch"]:
        raise SkillpackError("Applied full-index patch differs from the lifecycle plan.")
    if changed_paths != candidates:
        raise SkillpackError("Applied changed-file set differs from the lifecycle plan.")
    for item in plan["changedFiles"]:
        after_sha, after_mode = _path_record(root, str(item["path"]))
        if after_sha != item["afterSha256"] or after_mode != item["afterMode"]:
            raise SkillpackError(
                f"Applied file {item['path']} differs from the reviewed lifecycle plan."
            )


def apply_lifecycle_plan(
    root: Path,
    pack_id: str,
    *,
    operation: Operation,
    plan_digest: str | None,
    release_date: str | None = None,
    version: str | None = None,
) -> dict[str, Any]:
    if not plan_digest or not _DIGEST_RE.fullmatch(plan_digest):
        raise SkillpackError("--apply requires a reviewed lowercase 64-character plan digest.")
    plan = build_lifecycle_plan(
        root,
        pack_id,
        operation=operation,
        release_date=release_date,
        version=version,
    )
    if plan["planDigest"] != plan_digest:
        raise SkillpackError("Plan digest does not match the unchanged file preimages.")
    _candidate, changes = _prepare_canonical_changes(
        root,
        pack_id,
        operation=operation,
        release_date=release_date,
        version=version,
    )
    controlled = _controlled_paths(
        root,
        list(changes),
        generated={str(item["path"]) for item in plan["generatedOutputs"]},
    ) | {str(item["path"]) for item in plan["changedFiles"]}
    snapshots = _snapshots(root, controlled)
    try:
        for relative, content in changes.items():
            path = root / relative
            preimage = inspect_path(path, root, leaf_kind="file")
            assert preimage is not None
            expected_hash = plan["preimages"][relative]
            if sha256_bytes(read_regular_bytes(path, root, expected=preimage)) != expected_hash:
                raise SkillpackError(f"Preimage changed after preview: {relative}")
            safe_atomic_write_bytes(
                path,
                content.encode("utf-8"),
                root,
                mode=preimage.st_mode & 0o777,
                expected=preimage,
            )
        generated_result = apply_generated_files(root)
        generated = getattr(generated_result, "generated_files", None)
        from .validate import validate_repository

        result = validate_repository(
            root,
            check_generated=True,
            strict_placeholders=True,
            _generated_files=generated,
        )
        if not result.ok:
            raise SkillpackError(
                "Lifecycle result failed repository validation:\n" + "\n".join(result.errors)
            )
        _verify_applied_plan(root, plan, generated)
    except BaseException as exc:
        rollback_after_failure(
            exc,
            lambda: _restore(root, snapshots),
            label="Lifecycle update",
        )
        raise
    return {**plan, "mode": "apply", "applied": True}


def plan_text(plan: dict[str, Any]) -> str:
    return json_text({**plan, "mode": "preview", "applied": False})
