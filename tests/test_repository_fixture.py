from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from conftest import (
    _require_ready_generated_template,
    _restore_reusable_repository,
    _ReusableRepository,
)

GIT = ("git", "-c", "core.longpaths=true")


def _git(repository: _ReusableRepository, *arguments: str) -> str:
    return subprocess.run(
        [*GIT, "-C", str(repository.root), *arguments],
        check=True,
        capture_output=True,
        text=True,
        env=repository.environment,
    ).stdout.strip()


def _initialize_ready_template(tmp_path: Path) -> tuple[Path, Path]:
    fixture_root = tmp_path / "template"
    root = fixture_root / "w"
    root.mkdir(parents=True)
    subprocess.run([*GIT, "init", "-q", str(root)], check=True)
    subprocess.run([*GIT, "-C", str(root), "config", "user.name", "Fixture"], check=True)
    subprocess.run(
        [
            *GIT,
            "-C",
            str(root),
            "config",
            "user.email",
            "fixture@example.invalid",
        ],
        check=True,
    )
    tracked = root / "tracked.txt"
    tracked.write_text("tracked\n", encoding="utf-8")
    subprocess.run([*GIT, "-C", str(root), "add", "tracked.txt"], check=True)
    subprocess.run(
        [
            *GIT,
            "-C",
            str(root),
            "commit",
            "-q",
            "--no-gpg-sign",
            "-m",
            "template",
        ],
        check=True,
    )
    head = subprocess.run(
        [*GIT, "-C", str(root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    (fixture_root / ".ready").write_text(head + "\n", encoding="utf-8")
    return fixture_root, root


def test_generated_template_ready_marker_matches_clean_head(
    generated_repository_template: Path,
) -> None:
    fixture_root = generated_repository_template.parent

    assert _require_ready_generated_template(fixture_root) == (generated_repository_template)


def test_generated_template_ready_marker_fails_closed_on_mutation(tmp_path: Path) -> None:
    fixture_root, root = _initialize_ready_template(tmp_path)
    assert _require_ready_generated_template(fixture_root) == root

    (root / "tracked.txt").write_text("mutated\n", encoding="utf-8")

    with pytest.raises(AssertionError, match="template is dirty"):
        _require_ready_generated_template(fixture_root)


def test_generated_template_ready_marker_fails_closed_on_wrong_head(
    tmp_path: Path,
) -> None:
    fixture_root, _root = _initialize_ready_template(tmp_path)
    (fixture_root / ".ready").write_text("0" * 40 + "\n", encoding="utf-8")

    with pytest.raises(AssertionError, match="does not match its ready marker"):
        _require_ready_generated_template(fixture_root)


def test_reusable_repository_is_worker_local(
    generated_repository_template: Path,
    reusable_generated_repository: _ReusableRepository,
    tmp_path_factory: pytest.TempPathFactory,
    worker_id: str,
) -> None:
    repository = reusable_generated_repository

    assert repository.root != generated_repository_template
    assert tmp_path_factory.getbasetemp() in repository.root.parents
    if worker_id != "master":
        assert generated_repository_template.parent.parent == (
            tmp_path_factory.getbasetemp().parent
        )


def test_reusable_repository_restores_commits_index_config_and_untracked_files(
    reusable_generated_repository: _ReusableRepository,
) -> None:
    repository = reusable_generated_repository
    _restore_reusable_repository(repository)
    root = repository.root
    readme = root / "README.md"
    executable = root / "tools/bootstrap"
    original_readme = readme.read_bytes()
    original_index_entry = _git(repository, "ls-files", "--stage", "tools/bootstrap")
    original_config = (root / ".git/config").read_bytes()

    readme.write_bytes(b"contaminated\n")
    executable.write_bytes(b"contaminated executable\n")
    untracked = root / "fixture-untracked.txt"
    ignored = root / ".pytest_cache/fixture-ignored.txt"
    untracked.write_bytes(b"untracked\n")
    ignored.parent.mkdir(parents=True, exist_ok=True)
    ignored.write_bytes(b"ignored\n")
    _git(repository, "config", "user.name", "Contaminated Fixture")
    _git(repository, "add", "-A")
    _git(repository, "update-index", "--chmod=-x", "--", "tools/bootstrap")
    _git(repository, "commit", "-q", "--no-gpg-sign", "-m", "fixture contamination")
    _git(repository, "branch", "fixture-leaked-branch")
    _git(repository, "tag", "fixture-leaked-tag")
    assert _git(repository, "for-each-ref", "--format=%(refname)")
    (root / ".git/config").write_bytes(b"[invalid fixture config\n")

    _restore_reusable_repository(repository)

    assert _git(repository, "rev-parse", "HEAD") == repository.base_sha
    assert _git(repository, "rev-parse", "--abbrev-ref", "HEAD") == "HEAD"
    assert readme.read_bytes() == original_readme
    assert _git(repository, "ls-files", "--stage", "tools/bootstrap") == original_index_entry
    assert not untracked.exists()
    assert not ignored.exists()
    assert (root / ".git/config").read_bytes() == original_config
    assert _git(repository, "for-each-ref", "--format=%(refname)") == ""
    assert _git(repository, "config", "user.name") == "Fixture"
    assert _git(repository, "config", "core.hooksPath") == str(repository.hooks)
    assert _git(repository, "status", "--porcelain=v1", "--untracked-files=all") == ""
