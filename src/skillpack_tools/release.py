from __future__ import annotations

import io
import os
import stat
import subprocess
import zipfile
from pathlib import Path

from .generate import (
    _portable_source_mode,
    _runtime_files,
    _tracked_source_modes,
    apply_generated_files,
)
from .models import Pack, get_pack
from .path_safety import (
    inspect_path,
    read_regular_bytes,
    read_regular_text,
    repository_relative,
    safe_atomic_write_bytes,
    verify_preimage,
)
from .util import SkillpackError, parse_skill_markdown_text, sha256_bytes
from .validate import (
    raise_for_result,
    validate_compatibility_report,
    validate_repository,
)

FIXED_ZIP_TIME = (1980, 1, 1, 0, 0, 0)
RELEASE_ROOT_FILES = (
    "LICENSE",
    "NOTICE",
    "THIRD_PARTY_NOTICES.md",
    "COMPATIBILITY.md",
    "SECURITY.md",
)
REQUIRED_RELEASE_CLIENTS = {"claude-code", "codex", "opencode"}
UNRESOLVED_PACK_README_MARKERS = (
    "unpublished release candidate",
    "release-candidate manifest version",
    "expected release tag (not yet created)",
    "no public installation or native-client/model compatibility is claimed yet",
)


def _git(root: Path, *args: str) -> str:
    try:
        return subprocess.check_output(
            ["git", "-C", str(root), *args],
            text=True,
            stderr=subprocess.PIPE,
        ).strip()
    except OSError as exc:
        raise SkillpackError("Git is required for a publishable release.") from exc
    except subprocess.CalledProcessError as exc:
        detail = exc.stderr.strip() if exc.stderr else "git command failed"
        raise SkillpackError(f"Publishable release Git check failed: {detail}") from exc


def _resolved_source_sha(root: Path, fallback: str | None) -> str:
    """Return the checked-out commit when available without making a network call."""

    try:
        value = subprocess.check_output(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return fallback or "unavailable outside a Git worktree"
    return value if len(value) == 40 else fallback or "unavailable outside a Git worktree"


def _safe_release_files(
    root: Path,
    pack: Pack,
) -> list[tuple[Path, str, os.stat_result]]:
    """Return only explicitly allowlisted canonical and generated pack files."""

    candidates: list[Path] = [
        pack.path / "skillpack.yaml",
        pack.path / "README.md",
        pack.path / "CHANGELOG.md",
        pack.path / "tests" / "compatibility" / "expected-skills.json",
    ]
    if "claude-code" in pack.targets:
        candidates.append(pack.path / ".claude-plugin" / "plugin.json")
    if "codex" in pack.targets:
        candidates.append(pack.path / ".codex-plugin" / "plugin.json")

    for skill in pack.skills:
        skill_dir = pack.path / "skills" / skill
        candidates.extend(
            [
                skill_dir / "SKILL.md",
                skill_dir / "agents" / "openai.yaml",
                skill_dir / "evals" / "evals.json",
                *_runtime_files(root, skill_dir),
            ]
        )
    candidates.extend(root / relative for relative in RELEASE_ROOT_FILES)

    files: list[tuple[Path, str, os.stat_result]] = []
    seen: set[str] = set()
    for source in sorted(set(candidates)):
        metadata = inspect_path(source, root, leaf_kind="file")
        assert metadata is not None
        relative = repository_relative(source, root).as_posix()
        if relative in seen:
            continue
        seen.add(relative)
        files.append((source, relative, metadata))
    return files


def _require_publishable_git_state(
    root: Path,
    pack: Pack,
    files: list[tuple[Path, str, os.stat_result]],
) -> str:
    head = _git(root, "rev-parse", "HEAD")
    if len(head) != 40:
        raise SkillpackError("Publishable releases require a full 40-character HEAD SHA.")
    status = _git(root, "status", "--porcelain", "--untracked-files=all")
    if status:
        raise SkillpackError("Publishable releases require a completely clean Git worktree.")
    tag_type = _git(root, "cat-file", "-t", f"refs/tags/{pack.tag}")
    if tag_type != "tag":
        raise SkillpackError(f"Release tag {pack.tag!r} must be an annotated tag.")
    _git(root, "verify-tag", pack.tag)
    tagged_sha = _git(root, "rev-list", "-n", "1", pack.tag)
    if tagged_sha != head:
        raise SkillpackError(f"Release tag {pack.tag!r} must resolve to HEAD {head}.")
    if pack.source_sha and pack.source_sha != head:
        raise SkillpackError("skillpack.yaml source-sha must match the exact release commit.")

    relative_paths = [relative for _, relative, _ in files]
    try:
        subprocess.run(
            ["git", "-C", str(root), "ls-files", "--error-unmatch", "--", *relative_paths],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        detail = exc.stderr.strip() if exc.stderr else "an allowlisted input is untracked"
        raise SkillpackError(f"Every publishable release input must be tracked: {detail}") from exc
    return head


def _require_release_readiness(pack: Pack) -> None:
    changelog = read_regular_text(pack.path / "CHANGELOG.md", pack.root)
    if "[Unreleased]" in changelog or "release-candidate" in changelog.lower():
        raise SkillpackError(f"{pack.id}: finalize the changelog before a publishable release.")
    readme = read_regular_text(pack.path / "README.md", pack.root).lower()
    unresolved = [marker for marker in UNRESOLVED_PACK_README_MARKERS if marker in readme]
    if unresolved:
        raise SkillpackError(
            f"{pack.id}: finalize release-state wording in README.md before a publishable "
            f"release; unresolved markers: {', '.join(unresolved)}."
        )
    for skill in pack.skills:
        skill_file = pack.path / "skills" / skill / "SKILL.md"
        metadata, _ = parse_skill_markdown_text(
            read_regular_text(skill_file, pack.root),
            skill_file.relative_to(pack.root),
        )
        maturity = metadata.get("metadata", {}).get("maturity")
        if maturity != "stable":
            raise SkillpackError(
                f"{skill}: metadata.maturity must be 'stable' for a publishable release."
            )


def _require_compatibility_evidence(
    root: Path,
    pack: Pack,
    source_sha: str,
    report_paths: list[Path],
) -> list[Path]:
    accepted: dict[str, Path] = {}
    report_errors: list[str] = []
    lexical_paths = {Path(os.path.abspath(os.fspath(path))) for path in report_paths}
    for path in sorted(lexical_paths):
        errors, data = validate_compatibility_report(root, path, pack=pack, source_sha=source_sha)
        if errors:
            report_errors.extend(errors)
            continue
        assert data is not None
        if data["verdict"]["status"] == "passed":
            accepted[data["client"]["name"]] = path
    missing = sorted(REQUIRED_RELEASE_CLIENTS - set(accepted))
    if missing:
        detail = "\n".join(f"  - {item}" for item in report_errors)
        suffix = f"\nInvalid report details:\n{detail}" if detail else ""
        raise SkillpackError(
            "Publishable releases require passing exact-SHA reports for: "
            + ", ".join(missing)
            + suffix
        )
    return [accepted[client] for client in sorted(REQUIRED_RELEASE_CLIENTS)]


def build_release(
    root: Path,
    pack_id: str,
    *,
    draft: bool = False,
    reports: list[Path] | None = None,
) -> tuple[Path, Path, Path]:
    """Build a deterministic rehearsal or a fully evidence-gated release archive."""

    root = Path(os.path.abspath(os.fspath(root)))
    apply_generated_files(root, check=True)
    result = validate_repository(root, check_generated=True, strict_placeholders=True)
    raise_for_result(result)

    try:
        pack = get_pack(root, pack_id)
    except KeyError as exc:
        raise SkillpackError(str(exc)) from exc

    release_files = _safe_release_files(root, pack)
    evidence: list[Path] = []
    if draft:
        source_sha = _resolved_source_sha(root, pack.source_sha)
        artifact_stem = f"{pack.tag}-draft"
    else:
        _require_release_readiness(pack)
        source_sha = _require_publishable_git_state(root, pack, release_files)
        evidence = _require_compatibility_evidence(root, pack, source_sha, reports or [])
        artifact_stem = pack.tag

    output_dir = root / "dist" / "releases"
    archive = output_dir / f"{artifact_stem}.zip"
    checksum = output_dir / f"{artifact_stem}.zip.sha256"
    notes = output_dir / f"{artifact_stem}-release-notes.md"
    output_preimages = {
        path: inspect_path(path, root, leaf_kind="file", allow_missing=True)
        for path in (archive, checksum, notes)
    }
    tracked_modes = _tracked_source_modes(root)

    release_input_bytes: dict[Path, bytes] = {}
    for source, _archive_relative, preimage in release_files:
        release_input_bytes[source] = read_regular_bytes(
            source,
            root,
            expected=preimage,
        )
    for source, _archive_relative, preimage in release_files:
        verify_preimage(source, root, preimage)

    archive_buffer = io.BytesIO()
    with zipfile.ZipFile(
        archive_buffer,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
    ) as zf:
        for source, archive_relative, _preimage in release_files:
            info = zipfile.ZipInfo(f"{artifact_stem}/{archive_relative}", FIXED_ZIP_TIME)
            permission = _portable_source_mode(root, source, tracked_modes)
            info.create_system = 3
            info.external_attr = (stat.S_IFREG | permission) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(info, release_input_bytes[source])

    archive_bytes = archive_buffer.getvalue()
    digest = sha256_bytes(archive_bytes)
    checksum_bytes = f"{digest}  {archive.name}\n".encode()
    changelog = release_input_bytes[pack.path / "CHANGELOG.md"].decode("utf-8").strip()
    mode = "DRAFT REHEARSAL — NOT FOR PUBLICATION" if draft else "PUBLISHABLE RELEASE"
    evidence_lines = (
        "\n".join(
            f"- `{client}`: `{path.name}`"
            for client, path in zip(sorted(REQUIRED_RELEASE_CLIENTS), evidence, strict=True)
        )
        if evidence
        else "- Not required for a draft rehearsal; no compatibility claim is made."
    )
    notes_bytes = f"""# {pack.display_name} {pack.version}

**Mode: {mode}**

- Pack: `{pack.id}`
- Tag: `{pack.tag}`
- Source SHA: `{source_sha}`
- License: `{pack.license}`
- Skills: {", ".join(f"`{skill}`" for skill in pack.skills)}
- Archive SHA-256: `{digest}`

## Compatibility evidence

{evidence_lines}

## Pack changelog

{changelog}
""".encode()
    for source, _archive_relative, preimage in release_files:
        verify_preimage(source, root, preimage)
    for path, preimage in output_preimages.items():
        verify_preimage(path, root, preimage)
    for path, content in (
        (archive, archive_bytes),
        (checksum, checksum_bytes),
        (notes, notes_bytes),
    ):
        safe_atomic_write_bytes(
            path,
            content,
            root,
            mode=0o644,
            expected=output_preimages[path],
        )
    return archive, checksum, notes
