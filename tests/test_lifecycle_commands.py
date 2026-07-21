from __future__ import annotations

import datetime as dt
import re
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import yaml

import skillpack_tools.lifecycle_commands as lifecycle_commands
from skillpack_tools.generate import apply_generated_files
from skillpack_tools.lifecycle_commands import (
    _prepare_canonical_changes,
    apply_lifecycle_plan,
    build_lifecycle_plan,
)
from skillpack_tools.models import get_pack
from skillpack_tools.release import _require_release_readiness
from skillpack_tools.util import SkillpackError, parse_skill_markdown_text
from skillpack_tools.validate import validate_repository

ROOT = Path(__file__).resolve().parents[1]
GIT = ("git", "-c", "core.longpaths=true")


@pytest.fixture(scope="module")
def lifecycle_repository_template(generated_repository_template: Path) -> Path:
    return generated_repository_template


@pytest.fixture(scope="module")
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


def test_prepare_release_preview_digest_and_atomic_apply(
    monkeypatch: pytest.MonkeyPatch,
    generated_repo_copy: Path,
    prepared_release_plan: dict[str, Any],
) -> None:
    root = generated_repo_copy
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
    _require_release_readiness(pack)
    for skill in pack.skills:
        frontmatter, _body = parse_skill_markdown_text(
            (pack.path / "skills" / skill / "SKILL.md").read_text(encoding="utf-8"),
            Path(skill) / "SKILL.md",
        )
        assert frontmatter["metadata"]["version"] == "1.0.0"
        assert frontmatter["metadata"]["maturity"] == "stable"


def test_prepare_release_can_raise_version_without_stale_candidate_wording(
    generated_repo_copy: Path,
) -> None:
    root = generated_repo_copy
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
def test_skill_local_lifecycle_drift_fails_validation_and_release_readiness(
    field: str,
    canonical: str,
    drifted: str,
    validation_message: str,
    release_message: str,
    generated_repo_copy: Path,
) -> None:
    root = generated_repo_copy
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
    _candidate, changes = _prepare_canonical_changes(
        root,
        pack_id,
        operation="prepare-release",
        release_date=dt.date.today().isoformat(),
    )
    pack = get_pack(root, pack_id)
    changelog = changes[(pack.path / "CHANGELOG.md").relative_to(root).as_posix()]
    assert "has not been published" not in changelog
    assert "release-candidate" not in changelog
    assert "RELEASE PREPARATION NOTE" not in changelog


def test_prepare_release_rolls_back_canonical_and_generated_files(
    monkeypatch: pytest.MonkeyPatch,
    generated_repo_copy: Path,
    prepared_release_plan: dict[str, Any],
) -> None:
    root = generated_repo_copy
    release_date = dt.date.today().isoformat()
    plan = prepared_release_plan
    original = lifecycle_commands.apply_generated_files
    monkeypatch.setattr(lifecycle_commands, "build_lifecycle_plan", lambda *_args, **_kwargs: plan)

    def fail_after_write(candidate_root: Path, *, check: bool = False) -> list[str]:
        if check:
            return original(candidate_root, check=True)
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


@pytest.mark.parametrize("failure", [KeyboardInterrupt(), SystemExit(23)])
def test_prepare_release_rolls_back_process_interrupts(
    monkeypatch: pytest.MonkeyPatch,
    failure: BaseException,
    generated_repo_copy: Path,
    prepared_release_plan: dict[str, Any],
) -> None:
    root = generated_repo_copy
    release_date = dt.date.today().isoformat()
    plan = prepared_release_plan
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
