from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import stat
import subprocess
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Any

from .generate import (
    GeneratedFiles,
    _verify_generation_snapshot,
    apply_generated_files,
    build_generated_files,
)
from .lifecycle import semantic_version_key
from .models import Pack, discover_packs, get_pack, load_repository
from .path_safety import (
    inspect_path,
    read_regular_bytes,
    remove_empty_directory,
    safe_atomic_write_bytes,
    unlink_regular,
)
from .schema_validation import load_json_schema, schema_errors
from .util import SkillpackError, dump_yaml, rollback_after_failure, sha256_bytes
from .validate import raise_for_result, validate_repository


class _DuplicateKey(ValueError):
    pass


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise _DuplicateKey(f"duplicate object key {key!r}")
        value[key] = item
    return value


def _finite(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValueError(f"non-finite number {value!r} is not permitted")
    return parsed


def _constant(value: str) -> None:
    raise ValueError(f"non-finite number {value!r} is not permitted")


def strict_json_bytes(content: bytes, *, label: str) -> Any:
    try:
        return json.loads(
            content.decode("utf-8"),
            object_pairs_hook=_pairs,
            parse_float=_finite,
            parse_constant=_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, _DuplicateKey, ValueError) as exc:
        raise SkillpackError(f"{label}: invalid strict JSON: {exc}") from exc


def _schema(root: Path) -> dict[str, Any]:
    return load_json_schema(
        root / "schemas" / "publication-record.schema.json",
        root=root,
        label="schemas/publication-record.schema.json",
    )


def load_publication_record(root: Path, path: Path) -> dict[str, Any]:
    absolute = Path(os.path.abspath(os.fspath(path)))
    safety_root = root if absolute.is_relative_to(root) else absolute.parent
    content = read_regular_bytes(absolute, safety_root)
    record = strict_json_bytes(content, label=path.as_posix())
    if not isinstance(record, dict):
        raise SkillpackError(f"{path}: publication record must be a JSON object")
    errors = schema_errors(record, _schema(root), path.as_posix())
    if errors:
        raise SkillpackError("Publication record validation failed:\n" + "\n".join(errors))
    return record


def _record_snapshot(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "version": record["version"],
        "source-sha": record["sourceSha"],
        "release-id": record["releaseId"],
        "released-at": record["publishedAt"],
    }


def validate_publication_record(root: Path, record: dict[str, Any]) -> Pack:
    errors = schema_errors(record, _schema(root), "publication-record")
    if errors:
        raise SkillpackError("Publication record validation failed:\n" + "\n".join(errors))
    try:
        pack = get_pack(root, str(record["packId"]))
    except KeyError as exc:
        raise SkillpackError(str(exc)) from exc
    repository = load_repository(root)
    if record["repository"] != repository.slug:
        raise SkillpackError(
            f"publication record repository {record['repository']!r} does not match "
            f"{repository.slug!r}"
        )

    record_version = str(record["version"])
    expected_tag = f"{pack.id}-v{record_version}"
    if record["tag"] != expected_tag:
        raise SkillpackError(f"publication record tag must be {expected_tag}")
    expected_url = f"{repository.web_url}/releases/tag/{expected_tag}"
    if record["url"] != expected_url:
        raise SkillpackError(f"publication record URL must be {expected_url}")
    if semantic_version_key(record_version) > semantic_version_key(pack.version):
        raise SkillpackError(
            f"publication record version {record_version} is newer than canonical candidate "
            f"{pack.version}"
        )
    if pack.publication_state == "withdrawn":
        raise SkillpackError("publication records cannot automatically republish a withdrawn pack")

    latest = pack.latest_release
    if latest is not None:
        latest_version = str(latest["version"])
        record_key = semantic_version_key(record_version)
        latest_key = semantic_version_key(latest_version)
        if record_key < latest_key:
            raise SkillpackError(
                f"publication record version {record_version} precedes existing latest release "
                f"{latest_version}"
            )
        if record_key == latest_key and _record_snapshot(record) != latest:
            raise SkillpackError(
                "publication record conflicts with the existing release at the same Semantic "
                "Version precedence"
            )
    return pack


def _git_command(*arguments: str) -> list[str]:
    return ["git", "-c", "core.longpaths=true", *arguments]


def _git_head(root: Path) -> str:
    try:
        head = subprocess.check_output(
            _git_command("-C", str(root), "rev-parse", "HEAD"),
            text=True,
            stderr=subprocess.PIPE,
        ).strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise SkillpackError("Publication updates require a Git worktree.") from exc
    if len(head) != 40 or any(character not in "0123456789abcdef" for character in head):
        raise SkillpackError("Publication updates require a full lowercase Git HEAD SHA.")
    return head


def _require_clean(root: Path) -> None:
    status = subprocess.check_output(
        _git_command("-C", str(root), "status", "--porcelain", "--untracked-files=all"),
        text=True,
    ).strip()
    if status:
        raise SkillpackError("Publication updates require a clean worktree.")


def _content_bytes(content: str | bytes) -> bytes:
    return content if isinstance(content, bytes) else content.encode("utf-8")


def _generated_output_records(
    root: Path, generated: GeneratedFiles | None = None
) -> list[dict[str, str]]:
    if generated is None:
        generated = build_generated_files(root)
    else:
        _verify_generation_snapshot(root, generated)
    return [
        {
            "path": path,
            "sha256": sha256_bytes(_content_bytes(content)),
            "mode": f"{generated.modes[path]:04o}",
        }
        for path, content in sorted(generated.items())
    ]


def _git_patch_and_paths(root: Path, candidates: list[str]) -> tuple[str, list[str]]:
    """Return a full-index patch without mutating the worktree's real Git index."""

    with tempfile.TemporaryDirectory(prefix="publication-index-") as temporary:
        index = Path(temporary) / "index"
        git_index = subprocess.check_output(
            _git_command("-C", str(root), "rev-parse", "--git-path", "index"),
            text=True,
        ).strip()
        git_index_path = Path(git_index)
        if not git_index_path.is_absolute():
            git_index_path = root / git_index_path
        shutil.copyfile(git_index_path, index)
        environment = {**os.environ, "GIT_INDEX_FILE": str(index)}
        if candidates:
            pathspec = b"\0".join(path.encode("utf-8") for path in candidates) + b"\0"
            subprocess.run(
                _git_command(
                    "-C",
                    str(root),
                    "add",
                    "-N",
                    "-f",
                    "--pathspec-from-file=-",
                    "--pathspec-file-nul",
                ),
                input=pathspec,
                env=environment,
                check=True,
                capture_output=True,
            )
        arguments = _git_command(
            "-C",
            str(root),
            "diff",
            "--binary",
            "--full-index",
            "--no-ext-diff",
            "--no-renames",
        )
        patch = subprocess.check_output(arguments, env=environment).decode("utf-8")
        names = subprocess.check_output([*arguments, "--name-only", "-z"], env=environment)
    changed = [item.decode("utf-8") for item in names.split(b"\0") if item]
    return patch, changed


def _path_record(root: Path, relative: str) -> tuple[str | None, str | None]:
    path = root / relative
    metadata = inspect_path(path, root, leaf_kind="file", allow_missing=True)
    if metadata is None:
        return None, None
    return sha256_bytes(
        read_regular_bytes(path, root, expected=metadata)
    ), f"{stat.S_IMODE(metadata.st_mode):04o}"


def _preview_publication_changes(
    root: Path,
    *,
    base_commit: str,
    manifest_relative: str,
    proposed_manifest: bytes,
) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="publication-preview-") as temporary:
        preview = Path(temporary).resolve() / "repository"
        try:
            subprocess.run(
                _git_command(
                    "clone",
                    "--quiet",
                    "--shared",
                    "--no-checkout",
                    str(root),
                    str(preview),
                ),
                check=True,
                capture_output=True,
            )
            subprocess.run(
                _git_command("-C", str(preview), "checkout", "--quiet", "--detach", base_commit),
                check=True,
                capture_output=True,
            )
        except (OSError, subprocess.CalledProcessError) as exc:
            raise SkillpackError("Could not create the exact-base publication preview.") from exc

        manifest = preview / manifest_relative
        metadata = inspect_path(manifest, preview, leaf_kind="file")
        assert metadata is not None
        safe_atomic_write_bytes(
            manifest,
            proposed_manifest,
            preview,
            mode=0o644,
            expected=metadata,
        )
        generated_result = apply_generated_files(preview)
        generated = getattr(generated_result, "generated_files", None)
        raise_for_result(
            validate_repository(
                preview,
                check_generated=True,
                strict_placeholders=True,
                _generated_files=generated,
            )
        )
        generated_outputs = (
            _generated_output_records(preview, generated)
            if generated is not None
            else _generated_output_records(preview)
        )
        candidates = [manifest_relative, *(item["path"] for item in generated_outputs)]
        patch, changed_paths = _git_patch_and_paths(preview, candidates)
        changed_files: list[dict[str, str | None]] = []
        for relative in changed_paths:
            before_sha, before_mode = _path_record(root, relative)
            after_sha, after_mode = _path_record(preview, relative)
            changed_files.append(
                {
                    "path": relative,
                    "beforeSha256": before_sha,
                    "afterSha256": after_sha,
                    "beforeMode": before_mode,
                    "afterMode": after_mode,
                }
            )
        return {
            "unifiedPatch": patch,
            "changedFiles": changed_files,
            "generatedOutputs": generated_outputs,
            "generatedOutputSetSha256": sha256_bytes(
                json.dumps(generated_outputs, sort_keys=True, separators=(",", ":")).encode("utf-8")
            ),
        }


def _plan_payload(root: Path, record: dict[str, Any]) -> dict[str, Any]:
    _require_clean(root)
    base_commit = _git_head(root)
    if record.get("baseCommit") != base_commit:
        raise SkillpackError(
            "publication record baseCommit must equal the exact clean HEAD used for the patch"
        )
    apply_generated_files(root, check=True)
    pack = validate_publication_record(root, record)
    manifest_path = pack.path / "skillpack.yaml"
    before = read_regular_bytes(manifest_path, root)
    updated = deepcopy(pack.raw)
    updated.pop("source-sha", None)
    updated["publication"] = {
        "state": "published",
        "latest-release": _record_snapshot(record),
    }
    proposed = dump_yaml(updated).encode("utf-8")
    manifest_relative = manifest_path.relative_to(root).as_posix()
    preview = _preview_publication_changes(
        root,
        base_commit=base_commit,
        manifest_relative=manifest_relative,
        proposed_manifest=proposed,
    )
    payload: dict[str, Any] = {
        "schemaVersion": 2,
        "baseCommit": base_commit,
        "packId": pack.id,
        "manifestPath": manifest_relative,
        "manifestPreimageSha256": sha256_bytes(before),
        "proposedManifestSha256": sha256_bytes(proposed),
        "publicationRecordSha256": sha256_bytes(
            (json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n").encode()
        ),
        "record": record,
        "proposedManifest": proposed.decode("utf-8"),
        **preview,
    }
    digest_input = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    payload["planDigest"] = sha256_bytes(digest_input)
    return payload


def _snapshot_changed_files(
    root: Path, changed_files: list[dict[str, Any]]
) -> dict[str, tuple[bytes | None, int | None]]:
    snapshot: dict[str, tuple[bytes | None, int | None]] = {}
    for item in changed_files:
        relative = str(item["path"])
        path = root / relative
        metadata = inspect_path(path, root, leaf_kind="file", allow_missing=True)
        content = (
            read_regular_bytes(path, root, expected=metadata) if metadata is not None else None
        )
        mode = stat.S_IMODE(metadata.st_mode) if metadata is not None else None
        before_sha = sha256_bytes(content) if content is not None else None
        before_mode = f"{mode:04o}" if mode is not None else None
        if before_sha != item["beforeSha256"] or before_mode != item["beforeMode"]:
            raise SkillpackError(f"Refusing publication update because {relative} changed.")
        snapshot[relative] = (content, mode)
    return snapshot


def _rollback_changed_files(
    root: Path, snapshot: dict[str, tuple[bytes | None, int | None]]
) -> None:
    for relative, (content, mode) in snapshot.items():
        if content is None:
            continue
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        current = inspect_path(path, root, leaf_kind="file", allow_missing=True)
        safe_atomic_write_bytes(
            path,
            content,
            root,
            mode=mode if mode is not None else 0o644,
            expected=current,
        )
    absent_parents: set[Path] = set()
    for relative, (content, _mode) in snapshot.items():
        if content is not None:
            continue
        path = root / relative
        current = inspect_path(path, root, leaf_kind="file", allow_missing=True)
        if current is not None:
            unlink_regular(path, root, expected=current)
        absent_parents.add(path.parent)
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
    generated = (
        _generated_output_records(root, generated_files)
        if generated_files is not None
        else _generated_output_records(root)
    )
    if generated != plan["generatedOutputs"]:
        raise SkillpackError("Generated outputs do not match the reviewed publication plan.")
    digest = sha256_bytes(
        json.dumps(generated, sort_keys=True, separators=(",", ":")).encode("utf-8")
    )
    if digest != plan["generatedOutputSetSha256"]:
        raise SkillpackError("Generated output-set digest does not match the reviewed plan.")
    candidates = [str(item["path"]) for item in plan["changedFiles"]]
    patch, changed_paths = _git_patch_and_paths(root, candidates)
    if patch != plan["unifiedPatch"]:
        raise SkillpackError("Applied full-index patch differs from the reviewed publication plan.")
    if changed_paths != [str(item["path"]) for item in plan["changedFiles"]]:
        raise SkillpackError("Applied changed-file set differs from the reviewed publication plan.")
    for item in plan["changedFiles"]:
        after_sha, after_mode = _path_record(root, str(item["path"]))
        if after_sha != item["afterSha256"] or after_mode != item["afterMode"]:
            raise SkillpackError(
                f"Applied file {item['path']} differs from the reviewed publication plan."
            )


def prepare_publication_update(
    root: Path,
    record: dict[str, Any],
    *,
    apply: bool = False,
    plan_digest: str | None = None,
) -> dict[str, Any]:
    """Preview, or apply exactly, the deterministic canonical publication update."""

    root = Path(os.path.abspath(os.fspath(root)))
    plan = _plan_payload(root, record)
    if not apply:
        return plan
    if not plan_digest or plan_digest != plan["planDigest"]:
        raise SkillpackError(
            "Refusing publication update: --plan-digest must match the unchanged preview."
        )
    if _git_head(root) != plan["baseCommit"]:
        raise SkillpackError("Refusing publication update because HEAD changed after preview.")
    manifest = root / plan["manifestPath"]
    preimage = inspect_path(manifest, root, leaf_kind="file")
    assert preimage is not None
    if (
        sha256_bytes(read_regular_bytes(manifest, root, expected=preimage))
        != plan["manifestPreimageSha256"]
    ):
        raise SkillpackError("Refusing publication update because the manifest changed.")
    snapshot = _snapshot_changed_files(root, plan["changedFiles"])
    try:
        safe_atomic_write_bytes(
            manifest,
            plan["proposedManifest"].encode("utf-8"),
            root,
            mode=0o644,
            expected=preimage,
        )
        generated_result = apply_generated_files(root)
        generated = getattr(generated_result, "generated_files", None)
        raise_for_result(
            validate_repository(
                root,
                check_generated=True,
                strict_placeholders=True,
                _generated_files=generated,
            )
        )
        _verify_applied_plan(root, plan, generated)
    except BaseException as exc:
        rollback_after_failure(
            exc,
            lambda: _rollback_changed_files(root, snapshot),
            label="Publication update",
        )
        raise
    return plan


def _release_tag_match(tag: str, packs: dict[str, Pack]) -> tuple[Pack, str] | None:
    for pack_id in sorted(packs, key=len, reverse=True):
        prefix = f"{pack_id}-v"
        if tag.startswith(prefix):
            version = tag[len(prefix) :]
            try:
                semantic_version_key(version)
            except ValueError:
                return None
            return packs[pack_id], version
    return None


def _release_is_publishable(release: dict[str, Any]) -> bool:
    return all(
        (
            release.get("draft") is False,
            release.get("prerelease") is False,
            release.get("immutable") is True,
            release.get("annotated") is True,
            release.get("tagVerified") is True,
        )
    )


def _compare_release_to_manifest(
    drift: list[dict[str, str]], pack: Pack, version: str, release: dict[str, Any]
) -> None:
    publication = pack.raw.get("publication", {})
    latest_release = publication.get("latest-release", {})
    comparisons = {
        "state": "published",
        "version": version,
        "source-sha": release.get("sourceSha"),
        "release-id": release.get("releaseId", release.get("id")),
        "released-at": release.get("publishedAt", release.get("published_at")),
    }
    for field, expected in comparisons.items():
        actual = publication.get(field) if field == "state" else latest_release.get(field)
        if field == "state" and actual == "withdrawn" and version == pack.published_version:
            continue
        if actual != expected:
            drift.append(
                {
                    "kind": "release-manifest-mismatch",
                    "packId": pack.id,
                    "tag": str(release.get("tag", release.get("tag_name", ""))),
                    "field": field,
                    "expected": str(expected),
                    "actual": str(actual),
                }
            )


def _generated_output_drift(root: Path) -> list[dict[str, str]]:
    """Return deterministic generated-output drift without mutating the checkout."""

    try:
        apply_generated_files(root, check=True)
    except SkillpackError as exc:
        paths = sorted(
            line.removeprefix("  - ") for line in str(exc).splitlines() if line.startswith("  - ")
        )
        if paths:
            return [{"kind": "generated-output-drift", "path": path} for path in paths]
        return [{"kind": "generated-output-validation-error", "detail": str(exc)}]
    return []


def reconcile_publications(
    root: Path,
    releases: list[dict[str, Any]],
    tags: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Compare canonical publication state with normalized immutable release records."""

    packs = {pack.id: pack for pack in discover_packs(root)}
    seen_latest: set[str] = set()
    seen_tags: set[str] = set()
    drift: list[dict[str, str]] = _generated_output_drift(root)
    for release in releases:
        tag = str(release.get("tag", release.get("tag_name", "")))
        match = _release_tag_match(tag, packs)
        if match is None:
            candidate_ids = [pack_id for pack_id in packs if tag.startswith(f"{pack_id}-v")]
            if candidate_ids:
                drift.append({"kind": "invalid-pack-release-tag", "tag": tag})
            elif "-v" in tag:
                drift.append({"kind": "unknown-pack-release", "tag": tag})
            continue
        pack, version = match
        if tag in seen_tags:
            drift.append({"kind": "duplicate-release-tag", "packId": pack.id, "tag": tag})
            continue
        seen_tags.add(tag)

        if not _release_is_publishable(release):
            drift.append({"kind": "release-not-publishable", "packId": pack.id, "tag": tag})

        is_latest = version == pack.published_version
        version_key = semantic_version_key(version)
        published_key = (
            semantic_version_key(pack.published_version) if pack.published_version else None
        )
        if published_key is not None and version_key < published_key:
            continue
        if published_key is not None and version_key == published_key and not is_latest:
            drift.append(
                {
                    "kind": "release-version-conflict",
                    "packId": pack.id,
                    "tag": tag,
                    "publishedTag": str(pack.published_tag),
                }
            )
            continue
        if is_latest:
            seen_latest.add(pack.id)
        _compare_release_to_manifest(drift, pack, version, release)

    if tags is not None:
        tag_records: dict[str, dict[str, Any]] = {}
        duplicate_tags: set[str] = set()
        for tag_record in tags:
            tag = str(tag_record.get("tag", ""))
            if tag in tag_records:
                duplicate_tags.add(tag)
            else:
                tag_records[tag] = tag_record
        for tag in sorted(duplicate_tags):
            drift.append({"kind": "duplicate-repository-tag", "tag": tag})

        release_records = {
            str(release.get("tag", release.get("tag_name", ""))): release for release in releases
        }
        for tag, tag_record in sorted(tag_records.items()):
            match = _release_tag_match(tag, packs)
            if match is None:
                candidate_ids = [pack_id for pack_id in packs if tag.startswith(f"{pack_id}-v")]
                drift.append(
                    {
                        "kind": ("invalid-pack-tag" if candidate_ids else "unknown-pack-tag"),
                        "tag": tag,
                    }
                )
                continue
            pack, _version = match
            release = release_records.get(tag)
            if release is None:
                drift.append({"kind": "tag-release-missing", "packId": pack.id, "tag": tag})
                continue
            for field in ("sourceSha", "annotated", "tagVerified"):
                if release.get(field) != tag_record.get(field):
                    drift.append(
                        {
                            "kind": "release-tag-mismatch",
                            "packId": pack.id,
                            "tag": tag,
                            "field": field,
                            "expected": str(tag_record.get(field)),
                            "actual": str(release.get(field)),
                        }
                    )
        for tag, _release in sorted(release_records.items()):
            if _release_tag_match(tag, packs) is not None and tag not in tag_records:
                pack, _version = _release_tag_match(tag, packs) or (None, "")
                assert pack is not None
                drift.append({"kind": "release-tag-missing", "packId": pack.id, "tag": tag})

    for pack in packs.values():
        if pack.publication_state in {"published", "withdrawn"} and pack.id not in seen_latest:
            drift.append(
                {
                    "kind": "manifest-release-missing",
                    "packId": pack.id,
                    "tag": str(pack.published_tag),
                }
            )
    drift.sort(key=lambda item: tuple(item.get(key, "") for key in sorted(item)))
    return {"schemaVersion": 1, "ok": not drift, "drift": drift}


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Prepare or reconcile publication metadata.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare = subparsers.add_parser("prepare")
    prepare.add_argument("--root", type=Path, required=True)
    prepare.add_argument("--record", type=Path, required=True)
    prepare.add_argument("--output", type=Path, required=True)
    prepare.add_argument("--apply", action="store_true")
    prepare.add_argument("--plan-digest")
    reconcile = subparsers.add_parser("reconcile")
    reconcile.add_argument("--root", type=Path, required=True)
    reconcile.add_argument("--releases", type=Path, required=True)
    reconcile.add_argument("--tags", type=Path)
    reconcile.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        root = args.root.resolve()
        if args.command == "prepare":
            record = load_publication_record(root, args.record)
            plan = prepare_publication_update(
                root,
                record,
                apply=args.apply,
                plan_digest=args.plan_digest,
            )
            _write_json(args.output, plan)
            return 0
        releases = strict_json_bytes(args.releases.read_bytes(), label=str(args.releases))
        if not isinstance(releases, list) or not all(isinstance(item, dict) for item in releases):
            raise SkillpackError("release input must be an array of JSON objects")
        tags: list[dict[str, Any]] | None = None
        if args.tags is not None:
            loaded_tags = strict_json_bytes(args.tags.read_bytes(), label=str(args.tags))
            if not isinstance(loaded_tags, list) or not all(
                isinstance(item, dict) for item in loaded_tags
            ):
                raise SkillpackError("tag input must be an array of JSON objects")
            tags = loaded_tags
        report = reconcile_publications(root, releases, tags)
        _write_json(args.output, report)
        return 0 if report["ok"] else 1
    except (OSError, subprocess.CalledProcessError, SkillpackError, ValueError) as exc:
        if getattr(args, "command", None) == "reconcile":
            _write_json(
                args.output,
                {
                    "schemaVersion": 1,
                    "ok": False,
                    "drift": [{"kind": "reconciliation-error", "detail": str(exc)}],
                },
            )
        parser.exit(1, f"error: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
