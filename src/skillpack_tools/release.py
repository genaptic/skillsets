from __future__ import annotations

import io
import os
import re
import stat
import subprocess
import zipfile
from collections.abc import Mapping, Sequence
from pathlib import Path

from .evidence import strict_load_json, validate_evidence_asset
from .generate import (
    _portable_source_mode,
    _runtime_files,
    _tracked_source_modes,
    apply_generated_files,
)
from .lifecycle import semantic_version_key, validate_pack_lifecycle
from .models import Pack, get_pack, load_repository
from .path_safety import (
    inspect_path,
    read_regular_bytes,
    read_regular_text,
    repository_relative,
    safe_atomic_write_bytes,
    verify_preimage,
)
from .release_metadata import ReleaseEvidence, release_metadata, release_metadata_bytes
from .signing import VerifiedTag, verify_tag
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


def render_release_notes(
    pack: Pack,
    *,
    draft: bool,
    source_sha: str | None,
    signer: VerifiedTag | None,
    archive_digest: str,
    evidence_records: Sequence[Mapping[str, object]],
    changelog: str,
) -> bytes:
    """Render the one canonical deterministic release-note body."""

    mode = "DRAFT REHEARSAL — NOT FOR PUBLICATION" if draft else "PUBLISHABLE RELEASE"
    evidence_lines = (
        "\n".join(
            (
                f"- `{item['client']}`: report `{item['reportAsset']}` "
                f"(`{item['reportSha256']}`), envelope `{item['provenanceAsset']}` "
                f"(`{item['provenanceSha256']}`), attestation bundle "
                f"`{item['attestationBundleAsset']}` "
                f"(`{item['attestationBundleSha256']}`)"
            )
            for item in evidence_records
        )
        if evidence_records
        else "- Not required for a draft rehearsal; no compatibility claim is made."
    )
    signer_line = (
        f"{signer.kind} `{signer.fingerprint}`" if signer is not None else "not applicable"
    )
    source_label = source_sha if source_sha is not None else "not available (draft rehearsal)"
    return f"""# {pack.display_name} {pack.version}

**Mode: {mode}**

- Pack: `{pack.id}`
- Tag: `{pack.tag}`
- Source SHA: `{source_label}`
- Tag signer: {signer_line}
- License: `{pack.license}`
- Skills: {", ".join(f"`{skill}`" for skill in pack.skills)}
- Archive SHA-256: `{archive_digest}`

## Compatibility evidence

{evidence_lines}

## Pack changelog

{changelog.strip()}
""".encode()


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
        root / "schemas" / "release-metadata.schema.json",
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
    policy_root: Path,
    pack: Pack,
    files: list[tuple[Path, str, os.stat_result]],
) -> VerifiedTag:
    head = _git(root, "rev-parse", "HEAD")
    if len(head) != 40:
        raise SkillpackError("Publishable releases require a full 40-character HEAD SHA.")
    status = _git(root, "status", "--porcelain", "--untracked-files=all")
    if status:
        raise SkillpackError("Publishable releases require a completely clean Git worktree.")
    tag_type = _git(root, "cat-file", "-t", f"refs/tags/{pack.tag}")
    if tag_type != "tag":
        raise SkillpackError(f"Release tag {pack.tag!r} must be an annotated tag.")
    verified = verify_tag(root, pack.tag, load_repository(policy_root).trusted_signers)
    tagged_sha = verified.source_sha
    if tagged_sha != head:
        raise SkillpackError(f"Release tag {pack.tag!r} must resolve to HEAD {head}.")
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
    return verified


def _require_release_readiness(pack: Pack) -> None:
    lifecycle_errors = validate_pack_lifecycle(pack)
    if lifecycle_errors:
        raise SkillpackError(
            f"{pack.id}: canonical lifecycle validation failed:\n"
            + "\n".join(f"  - {error}" for error in lifecycle_errors)
        )
    if pack.maturity != "stable":
        raise SkillpackError(
            f"{pack.id}: pack maturity must be 'stable' for a publishable release."
        )
    if pack.visibility != "public":
        raise SkillpackError(f"{pack.id}: maintainer-only packs cannot be published.")
    if pack.publication_state == "withdrawn":
        raise SkillpackError(f"{pack.id}: withdrawn packs cannot be published.")
    if pack.published_version is not None and semantic_version_key(
        pack.version
    ) <= semantic_version_key(pack.published_version):
        raise SkillpackError(
            f"{pack.id}: working version {pack.version} must be newer than the last public "
            f"release {pack.published_version}."
        )
    changelog = read_regular_text(pack.path / "CHANGELOG.md", pack.root)
    changelog = changelog.replace("\r\n", "\n").replace("\r", "\n")
    unreleased = list(re.finditer(r"(?m)^## \[Unreleased\][ \t]*$", changelog))
    if len(unreleased) != 1:
        raise SkillpackError(
            f"{pack.id}: changelog must contain exactly one ## [Unreleased] heading."
        )
    next_heading = re.search(r"(?m)^## ", changelog[unreleased[0].end() :])
    body_end = unreleased[0].end() + next_heading.start() if next_heading else len(changelog)
    if changelog[unreleased[0].end() : body_end].strip():
        raise SkillpackError(f"{pack.id}: finalize the changelog; ## [Unreleased] must be empty.")
    if "release-candidate" in changelog.lower():
        raise SkillpackError(f"{pack.id}: finalize release-candidate wording in the changelog.")
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
        version = metadata.get("metadata", {}).get("version")
        if maturity != pack.maturity:
            raise SkillpackError(
                f"{skill}: metadata.maturity must match pack maturity {pack.maturity!r}."
            )
        if version != pack.version:
            raise SkillpackError(
                f"{skill}: metadata.version must match pack version {pack.version!r}."
            )


def _require_compatibility_evidence(
    root: Path,
    policy_root: Path,
    pack: Pack,
    source_sha: str,
    report_paths: list[Path],
) -> list[ReleaseEvidence]:
    accepted: dict[str, ReleaseEvidence] = {}
    duplicate_clients: set[str] = set()
    report_errors: list[str] = []
    repository = load_repository(policy_root)
    lexical_paths = {Path(os.path.abspath(os.fspath(path))) for path in report_paths}
    for path in sorted(lexical_paths):
        errors, data = validate_compatibility_report(
            root,
            path,
            pack=pack,
            source_sha=source_sha,
            policy=repository.compatibility_evidence,
            schema_root=policy_root,
        )
        if errors:
            report_errors.extend(errors)
            continue
        assert data is not None
        client = data["client"]["name"]
        asset_errors, validated = validate_evidence_asset(
            policy_root,
            path,
            source_sha=source_sha,
            client=client,
            pack_id=pack.id,
            repository_slug=repository.slug,
        )
        if asset_errors or validated is None:
            report_errors.extend(asset_errors)
            continue
        sidecar = path.with_name(f"{client}.artifact.json")
        try:
            artifact = strict_load_json(sidecar)
        except SkillpackError as exc:
            report_errors.append(str(exc))
            continue
        expected_keys = {
            "ingestionRunId",
            "ingestionArtifactId",
            "ingestionArtifactDigest",
        }
        if set(artifact) != expected_keys:
            report_errors.append(f"{sidecar}: expected exactly {', '.join(sorted(expected_keys))}.")
            continue
        if artifact["ingestionRunId"] != validated.envelope["workflow"]["runId"]:
            report_errors.append(f"{sidecar}: ingestionRunId does not match the evidence envelope.")
            continue
        artifact_id = artifact["ingestionArtifactId"]
        artifact_digest = artifact["ingestionArtifactDigest"]
        if not isinstance(artifact_id, int) or isinstance(artifact_id, bool) or artifact_id < 1:
            report_errors.append(f"{sidecar}: ingestionArtifactId must be a positive integer.")
            continue
        if not isinstance(artifact_digest, str) or not re.fullmatch(
            r"sha256:[0-9a-f]{64}", artifact_digest
        ):
            report_errors.append(
                f"{sidecar}: ingestionArtifactDigest must be a full sha256 digest."
            )
            continue
        if data["verdict"]["status"] == "passed":
            if client in accepted or client in duplicate_clients:
                accepted.pop(client, None)
                duplicate_clients.add(client)
                report_errors.append(
                    f"{path}: duplicate passing evidence supplied for client {client!r}."
                )
                continue
            accepted[client] = ReleaseEvidence(
                client=client,
                tested_at=data["testedAt"],
                report_path=validated.assets.report,
                provenance_path=validated.assets.envelope,
                attestation_bundle_path=validated.assets.attestation_bundle,
                ingestion_run_id=artifact["ingestionRunId"],
                ingestion_artifact_id=artifact_id,
                ingestion_artifact_digest=artifact_digest,
            )
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
    policy_root: Path | None = None,
) -> tuple[Path, Path, Path]:
    """Build a deterministic rehearsal or a fully evidence-gated release archive."""

    root = Path(os.path.abspath(os.fspath(root)))
    if draft and policy_root is not None:
        raise SkillpackError("--policy-root is not valid for a draft rehearsal.")
    if not draft and policy_root is None:
        raise SkillpackError("Publishable releases require an explicit protected policy root.")
    resolved_policy_root = (
        Path(os.path.abspath(os.fspath(policy_root))) if policy_root is not None else None
    )
    generated_result = apply_generated_files(root, check=True)
    generated = getattr(generated_result, "generated_files", None)
    result = validate_repository(
        root,
        check_generated=True,
        strict_placeholders=True,
        _generated_files=generated,
    )
    raise_for_result(result)

    try:
        pack = get_pack(root, pack_id)
    except KeyError as exc:
        raise SkillpackError(str(exc)) from exc

    release_files = _safe_release_files(root, pack)
    evidence: list[ReleaseEvidence] = []
    signer: VerifiedTag | None = None
    if draft:
        source_sha = None
        artifact_stem = f"{pack.tag}-draft"
    else:
        assert resolved_policy_root is not None
        _require_release_readiness(pack)
        signer = _require_publishable_git_state(root, resolved_policy_root, pack, release_files)
        source_sha = signer.source_sha
        evidence = _require_compatibility_evidence(
            root,
            resolved_policy_root,
            pack,
            source_sha,
            reports or [],
        )
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

    metadata = release_metadata(
        root,
        pack,
        mode="draft-rehearsal" if draft else "publishable",
        source_sha=source_sha,
        signer=signer,
        evidence=evidence,
    )
    archive_entries = [
        (
            archive_relative,
            release_input_bytes[source],
            _portable_source_mode(root, source, tracked_modes),
        )
        for source, archive_relative, _preimage in release_files
    ]
    archive_entries.append(("RELEASE-METADATA.json", release_metadata_bytes(metadata), 0o644))

    archive_buffer = io.BytesIO()
    with zipfile.ZipFile(
        archive_buffer,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
    ) as zf:
        for archive_relative, content, permission in sorted(archive_entries):
            info = zipfile.ZipInfo(f"{artifact_stem}/{archive_relative}", FIXED_ZIP_TIME)
            info.create_system = 3
            info.external_attr = (stat.S_IFREG | permission) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(info, content)

    archive_bytes = archive_buffer.getvalue()
    digest = sha256_bytes(archive_bytes)
    checksum_bytes = f"{digest}  {archive.name}\n".encode()
    changelog = release_input_bytes[pack.path / "CHANGELOG.md"].decode("utf-8").strip()
    notes_bytes = render_release_notes(
        pack,
        draft=draft,
        source_sha=source_sha,
        signer=signer,
        archive_digest=digest,
        evidence_records=metadata["compatibilityEvidence"]["reports"],
        changelog=changelog,
    )
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
