from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from conftest import (
    _clone_clean_generated_source,
    _configure_fixture_repository,
    _isolated_git_environment,
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
    hooks = fixture_root / "h"
    hooks.mkdir()
    environment = _isolated_git_environment()
    subprocess.run([*GIT, "init", "-q", str(root)], check=True, env=environment)
    _configure_fixture_repository(root, hooks, environment)
    tracked = root / "tracked.txt"
    tracked.write_bytes(b"tracked\n")
    subprocess.run(
        [*GIT, "-C", str(root), "add", "tracked.txt"],
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
            "template",
        ],
        check=True,
        env=environment,
    )
    head = subprocess.run(
        [*GIT, "-C", str(root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
        env=environment,
    ).stdout.strip()
    (fixture_root / ".ready").write_bytes((head + "\n").encode("ascii"))
    return fixture_root, root


def _initialize_source_repository(tmp_path: Path) -> tuple[Path, dict[str, str], Path]:
    source = tmp_path / "source"
    source.mkdir()
    hooks = tmp_path / "source-hooks"
    hooks.mkdir()
    environment = _isolated_git_environment()
    subprocess.run([*GIT, "init", "-q", str(source)], check=True, env=environment)
    _configure_fixture_repository(source, hooks, environment)
    tracked = source / "tracked.txt"
    tracked.write_bytes(b"tracked\n")
    executable = source / "script.sh"
    executable.write_bytes(b"#!/bin/sh\nexit 0\n")
    executable.chmod(0o755)
    subprocess.run([*GIT, "-C", str(source), "add", "-A"], check=True, env=environment)
    subprocess.run(
        [*GIT, "-C", str(source), "commit", "-q", "--no-gpg-sign", "-m", "source"],
        check=True,
        env=environment,
    )
    return source, environment, hooks


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


def test_ready_template_creation_ignores_ambient_git_configuration(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    global_config = tmp_path / "ambient.gitconfig"
    global_config.write_bytes(b"[core]\n\tautocrlf = true\n")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(global_config))

    fixture_root, root = _initialize_ready_template(tmp_path)

    assert _require_ready_generated_template(fixture_root) == root
    assert (root / "tracked.txt").read_bytes() == b"tracked\n"
    assert (
        subprocess.run(
            [*GIT, "-C", str(root), "config", "--get", "core.autocrlf"],
            check=True,
            capture_output=True,
            text=True,
            env=_isolated_git_environment(),
        ).stdout.strip()
        == "false"
    )


def test_clean_source_clone_preserves_exact_commit_and_modes(tmp_path: Path) -> None:
    source, environment, _source_hooks = _initialize_source_repository(tmp_path)
    destination = tmp_path / "clone"
    clone_hooks = tmp_path / "clone-hooks"
    clone_hooks.mkdir()
    expected_head = subprocess.run(
        [*GIT, "-C", str(source), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
        env=environment,
    ).stdout.strip()

    actual_head = _clone_clean_generated_source(
        source,
        destination,
        clone_hooks,
        environment,
    )

    assert actual_head == expected_head
    assert (destination / "tracked.txt").read_bytes() == b"tracked\n"
    assert subprocess.run(
        [*GIT, "-C", str(destination), "ls-files", "--stage", "script.sh"],
        check=True,
        capture_output=True,
        text=True,
        env=environment,
    ).stdout.startswith("100755 ")
    assert (
        subprocess.run(
            [*GIT, "-C", str(destination), "status", "--porcelain=v1"],
            check=True,
            capture_output=True,
            text=True,
            env=environment,
        ).stdout
        == ""
    )


def test_dirty_source_uses_copy_fallback_without_creating_clone(tmp_path: Path) -> None:
    source, environment, _source_hooks = _initialize_source_repository(tmp_path)
    destination = tmp_path / "clone"
    clone_hooks = tmp_path / "clone-hooks"
    clone_hooks.mkdir()
    (source / "tracked.txt").write_bytes(b"dirty\n")

    assert _clone_clean_generated_source(source, destination, clone_hooks, environment) is None
    assert not destination.exists()


def test_clean_source_clone_ignores_only_copy_excluded_content(tmp_path: Path) -> None:
    source, environment, _source_hooks = _initialize_source_repository(tmp_path)
    gitignore = source / ".gitignore"
    gitignore.write_bytes(b".pytest_cache/\n.build/\n")
    subprocess.run([*GIT, "-C", str(source), "add", ".gitignore"], check=True, env=environment)
    subprocess.run(
        [*GIT, "-C", str(source), "commit", "-q", "--no-gpg-sign", "-m", "ignore"],
        check=True,
        env=environment,
    )
    safe_ignored = source / ".pytest_cache/cache.bin"
    safe_ignored.parent.mkdir()
    safe_ignored.write_bytes(b"ignored cache\n")
    clone = tmp_path / "safe-clone"
    clone_hooks = tmp_path / "safe-clone-hooks"
    clone_hooks.mkdir()

    assert _clone_clean_generated_source(source, clone, clone_hooks, environment)
    assert not (clone / ".pytest_cache").exists()

    unsafe_ignored = source / ".build/input.bin"
    unsafe_ignored.parent.mkdir()
    unsafe_ignored.write_bytes(b"copy-visible ignored input\n")
    second_clone = tmp_path / "unsafe-clone"
    second_hooks = tmp_path / "unsafe-clone-hooks"
    second_hooks.mkdir()

    assert _clone_clean_generated_source(source, second_clone, second_hooks, environment) is None
    assert not second_clone.exists()


def test_clean_source_clone_rejects_source_race(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source, environment, _source_hooks = _initialize_source_repository(tmp_path)
    destination = tmp_path / "clone"
    clone_hooks = tmp_path / "clone-hooks"
    clone_hooks.mkdir()
    original_run = subprocess.run

    def race_after_clone(*args: object, **kwargs: object) -> subprocess.CompletedProcess:
        completed = original_run(*args, **kwargs)
        command = args[0]
        if isinstance(command, list) and "clone" in command:
            (source / "tracked.txt").write_bytes(b"raced\n")
        return completed

    monkeypatch.setattr(subprocess, "run", race_after_clone)

    with pytest.raises(AssertionError, match="source changed"):
        _clone_clean_generated_source(source, destination, clone_hooks, environment)


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
