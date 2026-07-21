from __future__ import annotations

import subprocess

from conftest import _restore_reusable_repository, _ReusableRepository

GIT = ("git", "-c", "core.longpaths=true")


def _git(repository: _ReusableRepository, *arguments: str) -> str:
    return subprocess.run(
        [*GIT, "-C", str(repository.root), *arguments],
        check=True,
        capture_output=True,
        text=True,
        env=repository.environment,
    ).stdout.strip()


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
