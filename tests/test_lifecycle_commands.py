from __future__ import annotations

import datetime as dt
import json
import os
import re
import stat
import subprocess
import sys
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import yaml
from conftest import (
    _configure_fixture_repository,
    _create_reusable_repository,
    _exclusive_file_lock,
    _isolated_git_environment,
    _repository_head_and_status,
    _restore_reusable_repository,
    _ReusableRepository,
    _template_head,
)

import skillpack_tools.lifecycle_commands as lifecycle_commands
from skillpack_tools.generate import apply_generated_files
from skillpack_tools.lifecycle_commands import (
    _prepare_canonical_changes,
    apply_lifecycle_plan,
    build_lifecycle_plan,
)
from skillpack_tools.models import get_pack
from skillpack_tools.release import _require_release_readiness
from skillpack_tools.util import SkillpackError, parse_skill_markdown_text, sha256_bytes
from skillpack_tools.validate import validate_repository

ROOT = Path(__file__).resolve().parents[1]
GIT = ("git", "-c", "core.longpaths=true")
_CANDIDATE_PACK_ID = "python-best-practices"
_CANDIDATE_READY_SCHEMA_VERSION = 1
_CANDIDATE_COORDINATION_TIMEOUT_SECONDS = 300.0


def _normalize_candidate_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    """Return the lifecycle state required by the synthetic candidate fixture."""

    publication = manifest.get("publication")
    if not isinstance(publication, dict):
        raise AssertionError("candidate fixture source has invalid publication metadata")
    manifest["maturity"] = "release-candidate"
    publication["state"] = "unpublished"
    publication.pop("latest-release", None)
    return manifest


def _make_release_candidate(root: Path, environment: dict[str, str]) -> Path:
    pack = get_pack(root, "python-best-practices")
    if pack.maturity == "release-candidate" and pack.publication_state == "unpublished":
        if pack.visibility != "public" or pack.latest_release is not None:
            raise AssertionError("candidate fixture source has invalid publication state")
        for skill in pack.skills:
            skill_path = pack.path / "skills" / skill / "SKILL.md"
            frontmatter, _body = parse_skill_markdown_text(
                skill_path.read_text(encoding="utf-8"),
                skill_path.relative_to(root),
            )
            metadata = frontmatter.get("metadata")
            if (
                not isinstance(metadata, dict)
                or metadata.get("skillpack") != pack.id
                or metadata.get("version") != pack.version
                or metadata.get("maturity") != pack.maturity
            ):
                raise AssertionError(f"{skill_path.relative_to(root)} has lifecycle mirror drift")
        changelog = (pack.path / "CHANGELOG.md").read_text(encoding="utf-8")
        if "## [Unreleased]" not in changelog or "release-candidate" not in changelog:
            raise AssertionError("candidate fixture source has an invalid candidate changelog")
        apply_generated_files(root, check=True)
        return root
    assert pack.maturity in {"stable", "release-candidate"}
    assert pack.visibility == "public"

    manifest_path = pack.path / "skillpack.yaml"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    manifest = _normalize_candidate_manifest(manifest)
    manifest_path.write_bytes(yaml.safe_dump(manifest, sort_keys=False, width=1000).encode("utf-8"))
    for relative, content in lifecycle_commands._skill_updates(
        pack,
        version=pack.version,
        maturity="release-candidate",
    ).items():
        (root / relative).write_bytes(content.encode("utf-8"))
    (pack.path / "CHANGELOG.md").write_bytes(
        (
            "# Changelog\n\n"
            "## [Unreleased]\n\n"
            "### Added\n\n"
            f"- Prepared the `{pack.version}` release-candidate contents with "
            "`python-project-layout`,\n"
            "  `python-test-architecture`, and `python-domain-exception-policy`.\n\n"
            "<!-- BEGIN RELEASE PREPARATION NOTE -->\n"
            f"`{pack.version}` has not been published. Before requesting exact-SHA "
            "native/model evidence, freeze\n"
            "the candidate by moving these notes under "
            f"`## [{pack.version}]` and removing release-candidate\n"
            "wording. The protected release gate runs only after that frozen commit "
            "passes evidence.\n"
            "<!-- END RELEASE PREPARATION NOTE -->\n"
        ).encode()
    )
    apply_generated_files(root)
    subprocess.run(
        [*GIT, "-C", str(root), "add", "-A"],
        check=True,
        env=environment,
    )
    subprocess.run(
        [
            *GIT,
            "-C",
            str(root),
            "commit",
            "-q",
            "--no-gpg-sign",
            "-m",
            "release-candidate fixture",
        ],
        check=True,
        env=environment,
    )
    assert get_pack(root, "python-best-practices").maturity == "release-candidate"
    assert (
        subprocess.run(
            [*GIT, "-C", str(root), "status", "--porcelain=v1", "--untracked-files=all"],
            check=True,
            capture_output=True,
            text=True,
            env=environment,
        ).stdout
        == ""
    )
    return root


@pytest.fixture(scope="session")
def candidate_repository_template(
    tmp_path_factory: pytest.TempPathFactory,
    generated_repository_template: Path,
    worker_id: str,
) -> Path:
    """Materialize one immutable release-candidate template across all workers."""

    if worker_id == "master":
        shared_root = tmp_path_factory.getbasetemp()
    else:
        shared_root = tmp_path_factory.getbasetemp().parent
    return _coordinated_candidate_template(
        shared_root,
        generated_repository_template,
        source_root=ROOT,
    )


def _canonical_candidate_file(
    path: Path,
    root: Path,
) -> dict[str, str | int]:
    metadata = path.stat()
    return {
        "path": path.relative_to(root).as_posix(),
        "sha256": sha256_bytes(path.read_bytes()),
        "size": metadata.st_size,
        "mode": f"{stat.S_IMODE(metadata.st_mode):04o}",
    }


def _candidate_readiness(
    root: Path,
    *,
    source_head: str,
    template_head: str,
    expected_version: str,
    expected_skills: tuple[str, ...],
) -> dict[str, Any]:
    environment = _isolated_git_environment()
    candidate_head, status = _repository_head_and_status(root, environment)
    if status:
        raise AssertionError(f"shared candidate template is dirty:\n{status}")

    pack = get_pack(root, _CANDIDATE_PACK_ID)
    expected_lifecycle = {
        "id": _CANDIDATE_PACK_ID,
        "version": expected_version,
        "maturity": "release-candidate",
        "visibility": "public",
        "publicationState": "unpublished",
        "skills": list(expected_skills),
    }
    actual_lifecycle = {
        "id": pack.id,
        "version": pack.version,
        "maturity": pack.maturity,
        "visibility": pack.visibility,
        "publicationState": pack.publication_state,
        "skills": list(pack.skills),
    }
    if actual_lifecycle != expected_lifecycle or pack.latest_release is not None:
        raise AssertionError("shared candidate template has the wrong lifecycle state")

    manifest = pack.path / "skillpack.yaml"
    changelog = pack.path / "CHANGELOG.md"
    generated_manifest = root / "dist/generated-files.json"
    canonical_text = [manifest, changelog]
    skill_mirrors: list[dict[str, str | int]] = []
    for skill in expected_skills:
        skill_path = pack.path / "skills" / skill / "SKILL.md"
        canonical_text.append(skill_path)
        frontmatter, _body = parse_skill_markdown_text(
            skill_path.read_text(encoding="utf-8"),
            skill_path.relative_to(root),
        )
        metadata = frontmatter.get("metadata")
        if not isinstance(metadata, dict):
            raise AssertionError(f"{skill_path.relative_to(root)} lacks lifecycle metadata")
        mirror = {
            "id": skill,
            "version": str(metadata.get("version", "")),
            "maturity": str(metadata.get("maturity", "")),
            **_canonical_candidate_file(skill_path, root),
        }
        if (
            metadata.get("skillpack") != _CANDIDATE_PACK_ID
            or mirror["version"] != expected_version
            or mirror["maturity"] != "release-candidate"
        ):
            raise AssertionError(f"{skill_path.relative_to(root)} has lifecycle mirror drift")
        skill_mirrors.append(mirror)

    if any(b"\r\n" in path.read_bytes() for path in canonical_text):
        raise AssertionError("shared candidate template contains non-canonical line endings")
    changelog_text = changelog.read_text(encoding="utf-8")
    if "## [Unreleased]" not in changelog_text or "release-candidate" not in changelog_text:
        raise AssertionError("shared candidate template has an invalid candidate changelog")
    try:
        generated = json.loads(generated_manifest.read_bytes())
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise AssertionError("shared candidate template has invalid generated state") from exc
    if (
        not isinstance(generated, dict)
        or generated.get("schemaVersion") != 1
        or not isinstance(generated.get("files"), list)
    ):
        raise AssertionError("shared candidate template has invalid generated state")
    declared_files = json.dumps(
        generated["files"],
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")

    return {
        "schemaVersion": _CANDIDATE_READY_SCHEMA_VERSION,
        "sourceHead": source_head,
        "templateHead": template_head,
        "candidateHead": candidate_head,
        "pack": actual_lifecycle,
        "manifest": _canonical_candidate_file(manifest, root),
        "skillMirrors": skill_mirrors,
        "changelog": _canonical_candidate_file(changelog, root),
        "generatedManifest": {
            **_canonical_candidate_file(generated_manifest, root),
            "declaredFileCount": len(generated["files"]),
            "declaredFilesSha256": sha256_bytes(declared_files),
            "verifiedAgainstGenerator": True,
        },
        "cleanStatus": "",
    }


def _write_candidate_readiness(path: Path, readiness: dict[str, Any]) -> None:
    temporary = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    payload = (json.dumps(readiness, indent=2, sort_keys=True) + "\n").encode("utf-8")
    try:
        with temporary.open("wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _require_ready_candidate_template(
    fixture_root: Path,
    generated_repository_template: Path,
    *,
    source_root: Path,
) -> Path:
    ready = fixture_root / ".ready"
    if not ready.is_file() or ready.is_symlink():
        raise AssertionError("shared candidate template has no regular readiness marker")
    try:
        recorded = json.loads(ready.read_bytes())
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise AssertionError("shared candidate readiness metadata is invalid") from exc
    if not isinstance(recorded, dict):
        raise AssertionError("shared candidate readiness metadata is invalid")

    source_head = _template_head(source_root)
    template_head = _template_head(generated_repository_template)
    template_pack = get_pack(generated_repository_template, _CANDIDATE_PACK_ID)
    expected = _candidate_readiness(
        fixture_root / "w",
        source_head=source_head,
        template_head=template_head,
        expected_version=template_pack.version,
        expected_skills=tuple(template_pack.skills),
    )
    if recorded != expected:
        raise AssertionError("shared candidate readiness metadata does not match exact state")
    return fixture_root / "w"


def _materialize_shared_candidate_template(
    fixture_root: Path,
    generated_repository_template: Path,
    *,
    source_root: Path,
    prepare: Callable[[Path, dict[str, str]], object] = _make_release_candidate,
    verify_generated_state: Callable[[Path], object] | None = None,
) -> Path:
    """Build the candidate once, publish readiness last, and clean partial state."""

    ready = fixture_root / ".ready"
    if ready.exists() or fixture_root.exists():
        try:
            return _require_ready_candidate_template(
                fixture_root,
                generated_repository_template,
                source_root=source_root,
            )
        except Exception:
            lifecycle_commands._remove_temporary_tree(fixture_root)

    fixture_root.mkdir(parents=True)
    source_head = _template_head(source_root)
    template_head = _template_head(generated_repository_template)
    template_pack = get_pack(generated_repository_template, _CANDIDATE_PACK_ID)
    try:
        repository = _create_reusable_repository(
            generated_repository_template,
            fixture_root,
            prepare=prepare,
        )
        if (
            _template_head(source_root) != source_head
            or _template_head(generated_repository_template) != template_head
        ):
            raise AssertionError("candidate fixture source changed during preparation")
        if verify_generated_state is None:
            apply_generated_files(repository.root, check=True)
        else:
            verify_generated_state(repository.root)
        readiness = _candidate_readiness(
            repository.root,
            source_head=source_head,
            template_head=template_head,
            expected_version=template_pack.version,
            expected_skills=tuple(template_pack.skills),
        )
        _write_candidate_readiness(ready, readiness)
    except BaseException:
        if fixture_root.exists():
            lifecycle_commands._remove_temporary_tree(fixture_root)
        raise
    return _require_ready_candidate_template(
        fixture_root,
        generated_repository_template,
        source_root=source_root,
    )


def _coordinated_candidate_template(
    shared_root: Path,
    generated_repository_template: Path,
    *,
    source_root: Path,
    prepare: Callable[[Path, dict[str, str]], object] = _make_release_candidate,
    verify_generated_state: Callable[[Path], object] | None = None,
) -> Path:
    fixture_root = shared_root / "candidate-shared"
    with _exclusive_file_lock(
        shared_root / "candidate-shared.lock",
        timeout_seconds=_CANDIDATE_COORDINATION_TIMEOUT_SECONDS,
    ):
        return _materialize_shared_candidate_template(
            fixture_root,
            generated_repository_template,
            source_root=source_root,
            prepare=prepare,
            verify_generated_state=verify_generated_state,
        )


@pytest.fixture(scope="session")
def candidate_reusable_repository(
    tmp_path_factory: pytest.TempPathFactory,
    candidate_repository_template: Path,
    worker_id: str,
) -> _ReusableRepository:
    """Create one restorable candidate checkout per pytest worker."""

    fixture_root = tmp_path_factory.mktemp(f"candidate-worker-{worker_id}")
    return _create_reusable_repository(candidate_repository_template, fixture_root)


@pytest.fixture
def candidate_repo_copy(
    candidate_reusable_repository: _ReusableRepository,
) -> Path:
    _restore_reusable_repository(candidate_reusable_repository)
    return candidate_reusable_repository.root


@pytest.fixture
def lifecycle_repository_template(candidate_repo_copy: Path) -> Path:
    return candidate_repo_copy


@pytest.fixture
def prepared_release_plan(lifecycle_repository_template: Path) -> dict[str, Any]:
    return build_lifecycle_plan(
        lifecycle_repository_template,
        "python-best-practices",
        operation="prepare-release",
        release_date=dt.date.today().isoformat(),
    )


def _status(root: Path) -> str:
    return subprocess.check_output(
        [*GIT, "-C", str(root), "status", "--porcelain=v1", "--untracked-files=all"],
        text=True,
    )


def _transaction_failure_plan(
    root: Path,
    *,
    generated_paths: tuple[str, ...] = (),
) -> dict[str, Any]:
    release_date = dt.date.today().isoformat()
    _candidate, changes = _prepare_canonical_changes(
        root,
        "python-best-practices",
        operation="prepare-release",
        release_date=release_date,
    )
    return {
        "planDigest": "a" * 64,
        "preimages": {
            relative: sha256_bytes((root / relative).read_bytes()) for relative in changes
        },
        "generatedOutputs": [{"path": relative} for relative in generated_paths],
        "changedFiles": [{"path": relative} for relative in generated_paths],
    }


def test_candidate_manifest_normalizes_published_stable_source() -> None:
    manifest = yaml.safe_load(
        (ROOT / "packs/python/best-practices/skillpack.yaml").read_text(encoding="utf-8")
    )
    manifest["maturity"] = "stable"
    manifest["publication"] = {
        "state": "published",
        "latest-release": {
            "version": "1.0.0",
            "source-sha": "a" * 40,
            "release-id": 123456,
            "released-at": "2026-07-24T18:30:00Z",
        },
    }
    expected_version = manifest["version"]
    expected_visibility = manifest["distribution"]

    normalized = _normalize_candidate_manifest(manifest)

    assert normalized["version"] == expected_version
    assert normalized["distribution"] == expected_visibility
    assert normalized["maturity"] == "release-candidate"
    assert normalized["publication"] == {"state": "unpublished"}


def _initialize_lightweight_candidate_source(root: Path) -> Path:
    root.mkdir()
    hooks = root.parent / f"{root.name}-hooks"
    hooks.mkdir()
    environment = _isolated_git_environment()
    subprocess.run([*GIT, "init", "-q", str(root)], check=True, env=environment)
    _configure_fixture_repository(root, hooks, environment)

    pack_path = root / "packs/python/best-practices"
    skill_path = pack_path / "skills/python-project-layout"
    skill_path.mkdir(parents=True)
    (pack_path / "skillpack.yaml").write_text(
        yaml.safe_dump(
            {
                "schema-version": 2,
                "id": _CANDIDATE_PACK_ID,
                "display-name": "Python Best Practices",
                "description": "Fixture pack.",
                "language": "python",
                "subject": "best-practices",
                "version": "1.0.0",
                "maturity": "stable",
                "distribution": {"visibility": "public"},
                "publication": {"state": "unpublished"},
                "skills": ["python-project-layout"],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
        newline="\n",
    )
    (skill_path / "SKILL.md").write_text(
        (
            "---\n"
            "name: python-project-layout\n"
            "description: Lightweight candidate fixture.\n"
            "license: Apache-2.0\n"
            "metadata:\n"
            f"  skillpack: {_CANDIDATE_PACK_ID}\n"
            "  version: 1.0.0\n"
            "  maturity: stable\n"
            "---\n"
            "# Fixture\n"
        ),
        encoding="utf-8",
        newline="\n",
    )
    (pack_path / "CHANGELOG.md").write_text(
        "# Changelog\n\n## [Unreleased]\n\n## [1.0.0] - 2026-07-24\n",
        encoding="utf-8",
        newline="\n",
    )
    generated_manifest = root / "dist/generated-files.json"
    generated_manifest.parent.mkdir()
    generated_manifest.write_text(
        '{\n  "schemaVersion": 1,\n  "files": []\n}\n',
        encoding="utf-8",
        newline="\n",
    )
    executable = root / "tool.sh"
    executable.write_bytes(b"#!/bin/sh\nexit 0\n")
    executable.chmod(0o755)
    subprocess.run([*GIT, "-C", str(root), "add", "-A"], check=True, env=environment)
    subprocess.run(
        [*GIT, "-C", str(root), "update-index", "--chmod=+x", "--", "tool.sh"],
        check=True,
        env=environment,
    )
    subprocess.run(
        [*GIT, "-C", str(root), "commit", "-q", "--no-gpg-sign", "-m", "source"],
        check=True,
        env=environment,
    )
    return root


def _prepare_lightweight_candidate(root: Path, environment: dict[str, str]) -> Path:
    pack = get_pack(root, _CANDIDATE_PACK_ID)
    manifest_path = pack.path / "skillpack.yaml"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    manifest = _normalize_candidate_manifest(manifest)
    manifest_path.write_text(
        yaml.safe_dump(manifest, sort_keys=False),
        encoding="utf-8",
        newline="\n",
    )
    skill_path = pack.path / "skills/python-project-layout/SKILL.md"
    skill_path.write_text(
        skill_path.read_text(encoding="utf-8").replace(
            "maturity: stable",
            "maturity: release-candidate",
        ),
        encoding="utf-8",
        newline="\n",
    )
    (pack.path / "CHANGELOG.md").write_text(
        (
            "# Changelog\n\n"
            "## [Unreleased]\n\n"
            "### Added\n\n"
            "- Prepared the `1.0.0` release-candidate fixture.\n"
        ),
        encoding="utf-8",
        newline="\n",
    )
    subprocess.run([*GIT, "-C", str(root), "add", "-A"], check=True, env=environment)
    subprocess.run(
        [*GIT, "-C", str(root), "commit", "-q", "--no-gpg-sign", "-m", "candidate"],
        check=True,
        env=environment,
    )
    return root


def _verify_lightweight_generated_state(root: Path) -> None:
    generated = json.loads((root / "dist/generated-files.json").read_bytes())
    if generated != {"schemaVersion": 1, "files": []}:
        raise AssertionError("lightweight generated state drifted")


def test_candidate_template_is_produced_once_for_four_concurrent_consumers(
    tmp_path: Path,
) -> None:
    source = _initialize_lightweight_candidate_source(tmp_path / "source")
    shared_root = tmp_path / "shared"
    shared_root.mkdir()
    barrier = threading.Barrier(4)
    count_lock = threading.Lock()
    preparations = 0

    def counted_prepare(root: Path, environment: dict[str, str]) -> Path:
        nonlocal preparations
        with count_lock:
            preparations += 1
        return _prepare_lightweight_candidate(root, environment)

    def consume(_index: int) -> Path:
        barrier.wait()
        return _coordinated_candidate_template(
            shared_root,
            source,
            source_root=source,
            prepare=counted_prepare,
            verify_generated_state=_verify_lightweight_generated_state,
        )

    with ThreadPoolExecutor(max_workers=4) as executor:
        candidates = list(executor.map(consume, range(4)))

    assert preparations == 1
    assert candidates == [shared_root / "candidate-shared/w"] * 4
    readiness = json.loads((shared_root / "candidate-shared/.ready").read_bytes())
    source_head = _template_head(source)
    assert readiness["schemaVersion"] == _CANDIDATE_READY_SCHEMA_VERSION
    assert readiness["sourceHead"] == source_head
    assert readiness["templateHead"] == source_head
    assert readiness["pack"] == {
        "id": _CANDIDATE_PACK_ID,
        "version": "1.0.0",
        "maturity": "release-candidate",
        "visibility": "public",
        "publicationState": "unpublished",
        "skills": ["python-project-layout"],
    }
    assert readiness["skillMirrors"][0]["version"] == "1.0.0"
    assert readiness["skillMirrors"][0]["maturity"] == "release-candidate"
    assert readiness["changelog"]["sha256"]
    assert readiness["generatedManifest"]["declaredFileCount"] == 0
    assert readiness["cleanStatus"] == ""


def test_candidate_template_rebuilds_corrupt_or_mismatched_readiness(
    tmp_path: Path,
) -> None:
    source = _initialize_lightweight_candidate_source(tmp_path / "source")
    shared_root = tmp_path / "shared"
    shared_root.mkdir()
    preparations = 0

    def counted_prepare(root: Path, environment: dict[str, str]) -> Path:
        nonlocal preparations
        preparations += 1
        return _prepare_lightweight_candidate(root, environment)

    candidate = _coordinated_candidate_template(
        shared_root,
        source,
        source_root=source,
        prepare=counted_prepare,
        verify_generated_state=_verify_lightweight_generated_state,
    )
    ready = candidate.parent / ".ready"
    ready.write_bytes(b"{invalid readiness\n")
    assert (
        _coordinated_candidate_template(
            shared_root,
            source,
            source_root=source,
            prepare=counted_prepare,
            verify_generated_state=_verify_lightweight_generated_state,
        )
        == candidate
    )
    mismatched = json.loads(ready.read_bytes())
    mismatched["templateHead"] = "0" * 40
    ready.write_text(
        json.dumps(mismatched, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    assert (
        _coordinated_candidate_template(
            shared_root,
            source,
            source_root=source,
            prepare=counted_prepare,
            verify_generated_state=_verify_lightweight_generated_state,
        )
        == candidate
    )
    assert preparations == 3


def test_candidate_template_rejects_stale_generated_state_before_readiness(
    tmp_path: Path,
) -> None:
    source = _initialize_lightweight_candidate_source(tmp_path / "source")
    shared_root = tmp_path / "shared"
    shared_root.mkdir()

    def reject_generated_state(_root: Path) -> None:
        raise AssertionError("generated state is stale")

    with pytest.raises(AssertionError, match="generated state is stale"):
        _coordinated_candidate_template(
            shared_root,
            source,
            source_root=source,
            prepare=_prepare_lightweight_candidate,
            verify_generated_state=reject_generated_state,
        )

    assert not (shared_root / "candidate-shared").exists()


def test_candidate_worker_checkout_restores_without_mutating_shared_template(
    tmp_path: Path,
) -> None:
    source = _initialize_lightweight_candidate_source(tmp_path / "source")
    shared_root = tmp_path / "shared"
    shared_root.mkdir()
    template = _coordinated_candidate_template(
        shared_root,
        source,
        source_root=source,
        prepare=_prepare_lightweight_candidate,
        verify_generated_state=_verify_lightweight_generated_state,
    )
    first_root = tmp_path / "first"
    second_root = tmp_path / "second"
    first_root.mkdir()
    second_root.mkdir()
    first = _create_reusable_repository(template, first_root)
    second = _create_reusable_repository(template, second_root)
    template_manifest = template / "packs/python/best-practices/skillpack.yaml"
    worker_manifest = first.root / "packs/python/best-practices/skillpack.yaml"
    expected = template_manifest.read_bytes()
    assert worker_manifest.read_bytes() == expected
    expected_mode = _git_index_entry(template, "tool.sh")
    assert first.root != template
    assert second.root != template

    worker_manifest.write_bytes(b"contaminated worker checkout\n")
    (first.root / "tool.sh").write_bytes(b"contaminated\n")
    subprocess.run(
        [*GIT, "-C", str(first.root), "config", "user.name", "Contaminated"],
        check=True,
        env=first.environment,
    )
    subprocess.run(
        [*GIT, "-C", str(first.root), "add", "-A"],
        check=True,
        env=first.environment,
    )
    subprocess.run(
        [*GIT, "-C", str(first.root), "update-index", "--chmod=-x", "--", "tool.sh"],
        check=True,
        env=first.environment,
    )
    subprocess.run(
        [
            *GIT,
            "-C",
            str(first.root),
            "commit",
            "-q",
            "--no-gpg-sign",
            "-m",
            "contamination",
        ],
        check=True,
        env=first.environment,
    )
    subprocess.run(
        [*GIT, "-C", str(first.root), "branch", "leaked-branch"],
        check=True,
        env=first.environment,
    )
    subprocess.run(
        [*GIT, "-C", str(first.root), "tag", "leaked-tag"],
        check=True,
        env=first.environment,
    )
    _restore_reusable_repository(first)

    assert worker_manifest.read_bytes() == expected
    assert template_manifest.read_bytes() == expected
    assert (second.root / "packs/python/best-practices/skillpack.yaml").read_bytes() == expected
    assert _git_index_entry(first.root, "tool.sh") == expected_mode
    assert _git_index_entry(second.root, "tool.sh") == expected_mode
    assert _template_head(first.root) == first.base_sha
    assert _template_head(second.root) == second.base_sha
    assert _repository_head_and_status(first.root, first.environment)[1] == ""
    assert (
        subprocess.run(
            [*GIT, "-C", str(first.root), "for-each-ref", "--format=%(refname)"],
            check=True,
            capture_output=True,
            text=True,
            env=first.environment,
        ).stdout
        == ""
    )


def _git_index_entry(root: Path, path: str) -> str:
    return subprocess.run(
        [*GIT, "-C", str(root), "ls-files", "--stage", "--", path],
        check=True,
        capture_output=True,
        text=True,
        env=_isolated_git_environment(),
    ).stdout.strip()


def test_candidate_template_interrupt_cleans_partial_state(
    tmp_path: Path,
) -> None:
    source = _initialize_lightweight_candidate_source(tmp_path / "source")
    shared_root = tmp_path / "shared"
    shared_root.mkdir()

    def interrupt_setup(
        root: Path,
        _environment: dict[str, str],
    ) -> None:
        (root / "partial-state").write_bytes(b"incomplete\n")
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        _coordinated_candidate_template(
            shared_root,
            source,
            source_root=source,
            prepare=interrupt_setup,
            verify_generated_state=_verify_lightweight_generated_state,
        )

    fixture_root = shared_root / "candidate-shared"
    assert not fixture_root.exists()
    candidate = _coordinated_candidate_template(
        shared_root,
        source,
        source_root=source,
        prepare=_prepare_lightweight_candidate,
        verify_generated_state=_verify_lightweight_generated_state,
    )
    assert candidate.is_dir()
    assert (candidate.parent / ".ready").is_file()


def test_preview_uses_exact_shared_head_and_preserves_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "source"
    root.mkdir()
    subprocess.run([*GIT, "init", "-q", str(root)], check=True)
    subprocess.run([*GIT, "-C", str(root), "config", "user.name", "Fixture"], check=True)
    subprocess.run(
        [*GIT, "-C", str(root), "config", "user.email", "fixture@example.invalid"],
        check=True,
    )
    tracked = root / "tracked.txt"
    tracked.write_bytes(b"old\n")
    subprocess.run([*GIT, "-C", str(root), "add", "tracked.txt"], check=True)
    subprocess.run(
        [*GIT, "-C", str(root), "commit", "-q", "--no-gpg-sign", "-m", "old"],
        check=True,
    )
    old_head = subprocess.check_output(
        [*GIT, "-C", str(root), "rev-parse", "HEAD"], text=True
    ).strip()
    tracked.write_bytes(b"new\n")
    (root / "new-only.txt").write_bytes(b"new commit\n")
    subprocess.run([*GIT, "-C", str(root), "add", "-A"], check=True)
    subprocess.run(
        [*GIT, "-C", str(root), "commit", "-q", "--no-gpg-sign", "-m", "new"],
        check=True,
    )
    new_head = subprocess.check_output(
        [*GIT, "-C", str(root), "rev-parse", "HEAD"], text=True
    ).strip()

    redirected = tmp_path / "redirected"
    redirected.mkdir()
    subprocess.run([*GIT, "init", "-q", str(redirected)], check=True)
    subprocess.run(
        [*GIT, "-C", str(redirected), "config", "user.name", "Fixture"],
        check=True,
    )
    subprocess.run(
        [*GIT, "-C", str(redirected), "config", "user.email", "fixture@example.invalid"],
        check=True,
    )
    sentinel = redirected / "sentinel.txt"
    sentinel.write_bytes(b"must remain unchanged\n")
    subprocess.run([*GIT, "-C", str(redirected), "add", "sentinel.txt"], check=True)
    subprocess.run(
        [
            *GIT,
            "-C",
            str(redirected),
            "commit",
            "-q",
            "--no-gpg-sign",
            "-m",
            "sentinel",
        ],
        check=True,
    )
    redirected_status = _status(redirected)

    invalid_global_config = tmp_path / "invalid.gitconfig"
    invalid_global_config.write_text("[invalid\n", encoding="utf-8")
    contaminated_environment = {
        "GIT_DIR": str(redirected / ".git"),
        "GIT_WORK_TREE": str(redirected),
        "GIT_INDEX_FILE": str(redirected / ".git/index"),
        "GIT_OBJECT_DIRECTORY": str(redirected / ".git/objects"),
        "GIT_CONFIG_GLOBAL": str(invalid_global_config),
        "GIT_CONFIG_COUNT": "1",
        "GIT_CONFIG_KEY_0": "core.hooksPath",
        "GIT_CONFIG_VALUE_0": str(tmp_path / "injected-hooks"),
        "GIT_CONFIG_PARAMETERS": "'core.bare=true'",
    }
    with monkeypatch.context() as context:
        for key, value in contaminated_environment.items():
            context.setenv(key, value)
        isolated = lifecycle_commands._isolated_git_environment()
        assert {key for key in isolated if key.upper().startswith("GIT_")} == {
            "GIT_CONFIG_GLOBAL",
            "GIT_CONFIG_NOSYSTEM",
            "GIT_LFS_SKIP_SMUDGE",
            "GIT_TERMINAL_PROMPT",
        }
        assert lifecycle_commands._require_clean_worktree(root) == new_head

    (root / "untracked.txt").write_bytes(b"do not copy\n")
    source_status = _status(root)

    replacement = "preview\nexact Unicode: ☃\n"
    with monkeypatch.context() as context:
        for key, value in contaminated_environment.items():
            context.setenv(key, value)
        preview = lifecycle_commands._copy_for_preview(
            root,
            {"tracked.txt": replacement},
            head=old_head,
        )
    try:
        assert (preview / "tracked.txt").read_bytes() == replacement.encode("utf-8")
        assert not (preview / "new-only.txt").exists()
        assert not (preview / "untracked.txt").exists()
        assert (preview / ".git/objects/info/alternates").is_file()
        assert (
            subprocess.check_output(
                [*GIT, "-C", str(preview), "rev-parse", "HEAD"], text=True
            ).strip()
            == old_head
        )
    finally:
        lifecycle_commands._remove_temporary_tree(preview.parent)
    assert _status(root) == source_status
    assert _status(redirected) == redirected_status
    assert sentinel.read_bytes() == b"must remain unchanged\n"


def test_preview_clone_failure_is_actionable_and_cleans_temporary_tree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    temporary = tmp_path / "preview"
    temporary.mkdir()
    monkeypatch.setattr(
        lifecycle_commands.tempfile,
        "mkdtemp",
        lambda **_kwargs: str(temporary),
    )

    def fail_clone(*_args: object, **_kwargs: object) -> None:
        raise subprocess.CalledProcessError(128, ["git", "clone"])

    monkeypatch.setattr(lifecycle_commands.subprocess, "run", fail_clone)
    with pytest.raises(SkillpackError, match="exact-HEAD lifecycle preview"):
        lifecycle_commands._copy_for_preview(tmp_path, {}, head="a" * 40)
    assert not temporary.exists()


def test_temporary_tree_cleanup_removes_readonly_files(tmp_path: Path) -> None:
    temporary = tmp_path / "readonly-tree"
    temporary.mkdir()
    locked = temporary / "locked.txt"
    locked.write_bytes(b"fixture\n")
    locked.chmod(0o400)

    lifecycle_commands._remove_temporary_tree(temporary)

    assert not temporary.exists()


@pytest.mark.windows_release_integration
@pytest.mark.xdist_group("candidate-repository")
def test_prepare_release_preview_digest_and_atomic_apply(
    monkeypatch: pytest.MonkeyPatch,
    candidate_repo_copy: Path,
    prepared_release_plan: dict[str, Any],
) -> None:
    root = candidate_repo_copy
    release_date = dt.date.today().isoformat()

    plan = prepared_release_plan
    assert plan["operation"] == "prepare-release"
    assert len(plan["planDigest"]) == 64
    assert plan["schemaVersion"] == 2
    assert "maturity: stable" in plan["patch"]
    assert plan["patch"] == plan["unifiedPatch"]
    assert plan["changedFiles"]
    assert any(
        str(item["path"]).startswith("dist/") and item["beforeSha256"] != item["afterSha256"]
        for item in plan["generatedChanges"]
    )
    assert _status(root) == ""

    with monkeypatch.context() as context:
        context.setattr(lifecycle_commands, "build_lifecycle_plan", lambda *_args, **_kwargs: plan)
        with pytest.raises(SkillpackError, match="digest does not match"):
            apply_lifecycle_plan(
                root,
                "python-best-practices",
                operation="prepare-release",
                release_date=release_date,
                plan_digest="0" * 64,
            )
    assert _status(root) == ""

    # Preview construction is exercised above. Reuse those exact reviewed bytes here so this
    # test isolates the transactional apply; a separate contract verifies apply always rebuilds.
    with monkeypatch.context() as context:
        context.setattr(lifecycle_commands, "build_lifecycle_plan", lambda *_args, **_kwargs: plan)
        applied = apply_lifecycle_plan(
            root,
            "python-best-practices",
            operation="prepare-release",
            release_date=release_date,
            plan_digest=plan["planDigest"],
        )
    assert applied["applied"] is True
    pack = get_pack(root, "python-best-practices")
    assert pack.maturity == "stable"
    assert pack.publication_state == "unpublished"
    changelog = (pack.path / "CHANGELOG.md").read_text(encoding="utf-8")
    assert f"## [1.0.0] - {release_date}" in changelog
    assert "release-candidate" not in changelog
    assert "RELEASE PREPARATION NOTE" not in changelog
    assert changelog.endswith("\n")
    assert not changelog.endswith("\n\n")
    _require_release_readiness(pack)
    for skill in pack.skills:
        frontmatter, _body = parse_skill_markdown_text(
            (pack.path / "skills" / skill / "SKILL.md").read_text(encoding="utf-8"),
            Path(skill) / "SKILL.md",
        )
        assert frontmatter["metadata"]["version"] == "1.0.0"
        assert frontmatter["metadata"]["maturity"] == "stable"


def test_plan_text_preserves_apply_status() -> None:
    rendered = json.loads(
        lifecycle_commands.plan_text({"planDigest": "a" * 64, "mode": "apply", "applied": True})
    )

    assert rendered["mode"] == "apply"
    assert rendered["applied"] is True


def test_apply_rebuilds_lifecycle_plan_before_digest_comparison(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[Path, str, str, str | None, str | None]] = []

    def rebuilt(
        root: Path,
        pack_id: str,
        *,
        operation: str,
        release_date: str | None = None,
        version: str | None = None,
    ) -> dict[str, str]:
        calls.append((root, pack_id, operation, release_date, version))
        return {"planDigest": "a" * 64}

    monkeypatch.setattr(lifecycle_commands, "build_lifecycle_plan", rebuilt)
    with pytest.raises(SkillpackError, match="digest does not match"):
        apply_lifecycle_plan(
            ROOT,
            "python-best-practices",
            operation="prepare-release",
            release_date="2026-07-19",
            plan_digest="b" * 64,
        )
    assert calls == [(ROOT, "python-best-practices", "prepare-release", "2026-07-19", None)]


@pytest.mark.windows_release_integration
@pytest.mark.xdist_group("candidate-repository")
def test_prepare_release_can_raise_version_without_stale_candidate_wording(
    candidate_repo_copy: Path,
) -> None:
    root = candidate_repo_copy
    release_date = dt.date.today().isoformat()
    candidate, changes = _prepare_canonical_changes(
        root,
        "python-best-practices",
        operation="prepare-release",
        release_date=release_date,
        version="1.0.1",
    )
    assert candidate.version == "1.0.1"
    for relative, content in changes.items():
        (root / relative).write_bytes(content.encode("utf-8"))
    apply_generated_files(root)
    pack = get_pack(root, "python-best-practices")
    changelog = (pack.path / "CHANGELOG.md").read_text(encoding="utf-8")
    assert f"## [1.0.1] - {release_date}" in changelog
    assert "Prepared the `1.0.1` release contents" in changelog
    assert "`1.0.0` has not been published" not in changelog
    _require_release_readiness(pack)


@pytest.mark.parametrize(
    ("field", "canonical", "drifted", "validation_message", "release_message"),
    [
        (
            "version",
            "1.0.0",
            "9.9.9",
            "metadata.version must be '1.0.0'",
            "metadata.version must match pack version '1.0.0'",
        ),
        (
            "maturity",
            "stable",
            "draft",
            "metadata.maturity must be 'stable'",
            "metadata.maturity must match pack maturity 'stable'",
        ),
    ],
)
@pytest.mark.windows_release_integration
@pytest.mark.xdist_group("candidate-repository")
def test_skill_local_lifecycle_drift_fails_validation_and_release_readiness(
    field: str,
    canonical: str,
    drifted: str,
    validation_message: str,
    release_message: str,
    candidate_repo_copy: Path,
) -> None:
    root = candidate_repo_copy
    release_date = dt.date.today().isoformat()
    _candidate, changes = _prepare_canonical_changes(
        root,
        "python-best-practices",
        operation="prepare-release",
        release_date=release_date,
    )
    for relative, content in changes.items():
        (root / relative).write_bytes(content.encode("utf-8"))
    apply_generated_files(root)
    pack = get_pack(root, "python-best-practices")
    skill = pack.skills[0]
    skill_file = pack.path / "skills" / skill / "SKILL.md"
    original = skill_file.read_text(encoding="utf-8")
    frontmatter, body = parse_skill_markdown_text(original, skill_file.relative_to(root))
    assert frontmatter["metadata"][field] == canonical
    frontmatter["metadata"][field] = drifted
    skill_file.write_text(lifecycle_commands._frontmatter_text(frontmatter, body), encoding="utf-8")

    validation = validate_repository(root)
    assert validation_message in "\n".join(validation.errors)
    with pytest.raises(SkillpackError, match=re.escape(release_message)):
        _require_release_readiness(pack)


@pytest.mark.parametrize(
    "pack_id",
    [
        "python-best-practices",
        "python-cli-apps",
        "rust-best-practices",
        "rust-cli-apps",
        "postgres-databases",
    ],
)
def test_every_public_pack_changelog_can_be_finalized(pack_id: str) -> None:
    root = ROOT
    pack = get_pack(root, pack_id)
    if pack.maturity == "stable":
        changelog = (pack.path / "CHANGELOG.md").read_text(encoding="utf-8")
        assert f"## [{pack.version}]" in changelog
        assert "release-candidate" not in changelog
        assert "RELEASE PREPARATION NOTE" not in changelog
        return
    _candidate, changes = _prepare_canonical_changes(
        root,
        pack_id,
        operation="prepare-release",
        release_date=dt.date.today().isoformat(),
    )
    changelog = changes[(pack.path / "CHANGELOG.md").relative_to(root).as_posix()]
    assert "has not been published" not in changelog
    assert "release-candidate" not in changelog
    assert "RELEASE PREPARATION NOTE" not in changelog


@pytest.mark.windows_release_integration
@pytest.mark.xdist_group("candidate-repository")
def test_prepare_release_rolls_back_canonical_and_generated_files(
    monkeypatch: pytest.MonkeyPatch,
    candidate_repo_copy: Path,
) -> None:
    root = candidate_repo_copy
    release_date = dt.date.today().isoformat()
    generated_path = "dist/preview/rollback-fixture/nested/generated.txt"
    plan = _transaction_failure_plan(root, generated_paths=(generated_path,))
    original = lifecycle_commands.apply_generated_files
    monkeypatch.setattr(lifecycle_commands, "build_lifecycle_plan", lambda *_args, **_kwargs: plan)

    def fail_after_write(candidate_root: Path, *, check: bool = False) -> list[str]:
        if check:
            return original(candidate_root, check=True)
        generated = candidate_root / generated_path
        generated.parent.mkdir(parents=True)
        generated.write_bytes(b"must be removed during rollback\n")
        raise SkillpackError("forced generation failure")

    monkeypatch.setattr(lifecycle_commands, "apply_generated_files", fail_after_write)
    with pytest.raises(SkillpackError, match="forced generation failure"):
        apply_lifecycle_plan(
            root,
            "python-best-practices",
            operation="prepare-release",
            release_date=release_date,
            plan_digest=plan["planDigest"],
        )
    assert _status(root) == ""
    assert not (root / generated_path).exists()
    assert not (root / "dist/preview/rollback-fixture").exists()


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="legacy plain-list adapter coverage is platform-neutral and exhaustive on POSIX",
)
def test_lifecycle_preview_plain_list_generation_fallback_is_not_forwarded_as_snapshot(
    monkeypatch: pytest.MonkeyPatch,
    candidate_repo_copy: Path,
) -> None:
    root = candidate_repo_copy
    original = lifecycle_commands.apply_generated_files

    def plain_list_result(candidate_root: Path, *, check: bool = False) -> list[str]:
        return list(original(candidate_root, check=check))

    monkeypatch.setattr(lifecycle_commands, "apply_generated_files", plain_list_result)
    plan = build_lifecycle_plan(
        root,
        "python-best-practices",
        operation="prepare-release",
        release_date=dt.date.today().isoformat(),
    )
    assert plan["pack"] == "python-best-practices"
    assert plan["maturity"] == "stable"


@pytest.mark.parametrize("failure", [KeyboardInterrupt(), SystemExit(23)])
@pytest.mark.windows_release_integration
@pytest.mark.xdist_group("candidate-repository")
def test_prepare_release_rolls_back_process_interrupts(
    monkeypatch: pytest.MonkeyPatch,
    failure: BaseException,
    candidate_repo_copy: Path,
) -> None:
    root = candidate_repo_copy
    release_date = dt.date.today().isoformat()
    plan = _transaction_failure_plan(root)
    original = lifecycle_commands.apply_generated_files
    monkeypatch.setattr(lifecycle_commands, "build_lifecycle_plan", lambda *_args, **_kwargs: plan)

    def interrupt_after_canonical_write(candidate_root: Path, *, check: bool = False) -> list[str]:
        if check:
            return original(candidate_root, check=True)
        raise failure

    monkeypatch.setattr(
        lifecycle_commands,
        "apply_generated_files",
        interrupt_after_canonical_write,
    )
    with pytest.raises(type(failure)) as raised:
        apply_lifecycle_plan(
            root,
            "python-best-practices",
            operation="prepare-release",
            release_date=release_date,
            plan_digest=plan["planDigest"],
        )
    if isinstance(failure, SystemExit):
        assert raised.value.code == 23
    assert _status(root) == ""


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="new-tree begin-development rollback is exhaustive on POSIX; Windows retains the shared transaction rollback contract",
)
def test_begin_development_rollback_removes_new_generated_directories(
    monkeypatch: pytest.MonkeyPatch,
    generated_repo_copy: Path,
) -> None:
    root = generated_repo_copy
    pack = get_pack(root, "python-best-practices")
    manifest_path = pack.path / "skillpack.yaml"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    manifest["maturity"] = "stable"
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    for relative, content in lifecycle_commands._skill_updates(
        pack,
        version="1.0.0",
        maturity="stable",
    ).items():
        (root / relative).write_text(content, encoding="utf-8")
    apply_generated_files(root)
    subprocess.run([*GIT, "-C", str(root), "add", "-A"], check=True)
    subprocess.run(
        [*GIT, "-C", str(root), "commit", "-q", "--no-gpg-sign", "-m", "stable"],
        check=True,
    )
    source_sha = subprocess.check_output(
        [*GIT, "-C", str(root), "rev-parse", "HEAD"], text=True
    ).strip()
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    manifest["publication"] = {
        "state": "published",
        "latest-release": {
            "version": "1.0.0",
            "source-sha": source_sha,
            "release-id": 123,
            "released-at": "2026-07-19T18:30:00Z",
        },
    }
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    apply_generated_files(root)
    subprocess.run([*GIT, "-C", str(root), "add", "-A"], check=True)
    subprocess.run(
        [*GIT, "-C", str(root), "commit", "-q", "--no-gpg-sign", "-m", "published"],
        check=True,
    )
    preview_tree = root / "dist/preview/opencode/python/best-practices"
    assert not preview_tree.exists()

    plan = build_lifecycle_plan(
        root,
        "python-best-practices",
        operation="begin-development",
        version="1.0.1",
    )
    monkeypatch.setattr(lifecycle_commands, "build_lifecycle_plan", lambda *_args, **_kwargs: plan)
    from skillpack_tools import validate as validate_module

    original_validate = validate_module.validate_repository

    def fail_real_checkout(candidate_root: Path, **kwargs: object) -> object:
        if candidate_root == root:
            return SimpleNamespace(ok=False, errors=["forced validation failure"])
        return original_validate(candidate_root, **kwargs)

    monkeypatch.setattr(validate_module, "validate_repository", fail_real_checkout)
    with pytest.raises(SkillpackError, match="forced validation failure"):
        apply_lifecycle_plan(
            root,
            "python-best-practices",
            operation="begin-development",
            version="1.0.1",
            plan_digest=plan["planDigest"],
        )
    assert _status(root) == ""
    assert not preview_tree.exists()


def test_begin_development_preserves_latest_public_release(
    generated_repo_copy: Path,
) -> None:
    root = generated_repo_copy
    pack = get_pack(root, "python-best-practices")
    manifest_path = pack.path / "skillpack.yaml"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    latest = {
        "version": "1.0.0",
        "source-sha": "a" * 40,
        "release-id": 123456,
        "released-at": "2026-07-19T18:30:00Z",
    }
    manifest["maturity"] = "stable"
    manifest["publication"] = {"state": "published", "latest-release": latest}
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")

    candidate, changes = _prepare_canonical_changes(
        root,
        "python-best-practices",
        operation="begin-development",
        version="1.0.1",
    )
    assert candidate.version == "1.0.1"
    assert candidate.maturity == "release-candidate"
    assert candidate.latest_release == latest
    updated_manifest = yaml.safe_load(changes[manifest_path.relative_to(root).as_posix()])
    assert updated_manifest["publication"] == manifest["publication"]
    assert all(
        "maturity: release-candidate" in content
        for path, content in changes.items()
        if path.endswith("/SKILL.md")
    )


@pytest.mark.parametrize("maturity", ["stable", "release-candidate"])
def test_begin_development_rejects_source_already_ahead_of_latest_release(
    maturity: str,
    generated_repo_copy: Path,
) -> None:
    root = generated_repo_copy
    manifest_path = get_pack(root, "python-best-practices").path / "skillpack.yaml"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    manifest["version"] = "1.0.1"
    manifest["maturity"] = maturity
    manifest["publication"] = {
        "state": "published",
        "latest-release": {
            "version": "1.0.0",
            "source-sha": "a" * 40,
            "release-id": 123456,
            "released-at": "2026-07-19T18:30:00Z",
        },
    }
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    before = manifest_path.read_bytes()

    with pytest.raises(SkillpackError, match="already ahead of latest-release"):
        _prepare_canonical_changes(
            root,
            "python-best-practices",
            operation="begin-development",
            version="1.0.2",
        )
    assert manifest_path.read_bytes() == before


def test_lifecycle_commands_reject_maintainer_release_and_non_increasing_version(
    generated_repo_copy: Path,
) -> None:
    root = generated_repo_copy
    with pytest.raises(SkillpackError, match="Maintainer-only"):
        _prepare_canonical_changes(
            root,
            "genaptic-skillsets-development",
            operation="prepare-release",
            release_date=dt.date.today().isoformat(),
        )

    pack = get_pack(root, "python-best-practices")
    manifest_path = pack.path / "skillpack.yaml"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    manifest["maturity"] = "stable"
    manifest["publication"] = {
        "state": "published",
        "latest-release": {
            "version": "1.0.0",
            "source-sha": "a" * 40,
            "release-id": 123456,
            "released-at": "2026-07-19T18:30:00Z",
        },
    }
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    with pytest.raises(SkillpackError, match="must exceed the immutable"):
        _prepare_canonical_changes(
            root,
            "python-best-practices",
            operation="prepare-release",
            release_date=dt.date.today().isoformat(),
        )
    with pytest.raises(SkillpackError, match="must exceed"):
        _prepare_canonical_changes(
            root,
            "python-best-practices",
            operation="begin-development",
            version="1.0.0",
        )
