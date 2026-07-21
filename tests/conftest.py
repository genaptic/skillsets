from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


@dataclass(frozen=True)
class _ReusableRepository:
    root: Path
    base_sha: str
    hooks: Path
    environment: dict[str, str]


def _copy_ignore(_directory: str, names: list[str]) -> set[str]:
    ignored = {
        ".coverage",
        ".DS_Store",
        ".git",
        ".idea",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".venv",
        "__pycache__",
        "releases",
        "tmp",
    } & set(names)
    ignored.update(name for name in names if name.endswith((".pyc", ".pyo")))
    return ignored


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


def _configure_fixture_repository(root: Path, hooks: Path, environment: dict[str, str]) -> None:
    for key, value in (
        ("user.name", "Fixture"),
        ("user.email", "fixture@example.invalid"),
        ("commit.gpgsign", "false"),
        ("core.autocrlf", "false"),
        ("core.hooksPath", str(hooks)),
        ("core.longpaths", "true"),
    ):
        subprocess.run(
            ["git", "-C", str(root), "config", key, value],
            check=True,
            env=environment,
        )


def _restore_reusable_repository(repository: _ReusableRepository) -> None:
    """Restore a module checkout without paying for another full clone."""

    command = ["git", "-c", "core.longpaths=true", "-C", str(repository.root)]
    subprocess.run(
        [*command, "checkout", "-q", "-f", "--detach", repository.base_sha],
        check=True,
        env=repository.environment,
    )
    subprocess.run(
        [*command, "clean", "-q", "-ffdx"],
        check=True,
        env=repository.environment,
    )
    _configure_fixture_repository(
        repository.root,
        repository.hooks,
        repository.environment,
    )
    status_command = [*command, "status", "--porcelain=v1", "--untracked-files=all"]
    status = subprocess.run(
        status_command,
        check=True,
        capture_output=True,
        text=True,
        env=repository.environment,
    ).stdout
    if status:
        raise AssertionError(f"reusable repository fixture was not restored:\n{status}")


@pytest.fixture(scope="session")
def generated_repository_template(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Materialize the expensive generated repository fixture once per test session."""

    from skillpack_tools.generate import apply_generated_files

    fixture_root = tmp_path_factory.mktemp("g")
    root = fixture_root / "w"
    shutil.copytree(ROOT, root, ignore=_copy_ignore)
    environment = _isolated_git_environment()
    subprocess.run(
        ["git", "-c", "core.longpaths=true", "init", "-q", str(root)],
        check=True,
        env=environment,
    )
    empty_hooks = fixture_root / "h"
    empty_hooks.mkdir()
    _configure_fixture_repository(root, empty_hooks, environment)
    subprocess.run(
        ["git", "-c", "core.longpaths=true", "-C", str(root), "add", "-A"],
        check=True,
        env=environment,
    )
    source_index = subprocess.run(
        [
            "git",
            "-c",
            "core.longpaths=true",
            "-C",
            str(ROOT),
            "ls-files",
            "--stage",
            "-z",
        ],
        check=True,
        capture_output=True,
        text=True,
        env=environment,
    ).stdout
    executable_paths = [
        entry.split("\t", 1)[1]
        for entry in source_index.split("\0")
        if entry.startswith("100755 ") and "\t" in entry
    ]
    if executable_paths:
        subprocess.run(
            [
                "git",
                "-c",
                "core.longpaths=true",
                "-C",
                str(root),
                "update-index",
                "--chmod=+x",
                "--",
                *executable_paths,
            ],
            check=True,
            env=environment,
        )
    apply_generated_files(root)
    subprocess.run(
        ["git", "-c", "core.longpaths=true", "-C", str(root), "add", "-A"],
        check=True,
        env=environment,
    )
    subprocess.run(
        [
            "git",
            "-c",
            "core.longpaths=true",
            "-C",
            str(root),
            "commit",
            "-q",
            "--no-gpg-sign",
            "-m",
            "generated repository fixture",
        ],
        check=True,
        env=environment,
    )
    return root


@pytest.fixture(scope="module")
def reusable_generated_repository(
    tmp_path_factory: pytest.TempPathFactory, generated_repository_template: Path
) -> _ReusableRepository:
    """Create one isolated checkout per test module."""

    fixture_root = tmp_path_factory.mktemp("r")
    root = fixture_root / "w"
    empty_hooks = fixture_root / "h"
    empty_hooks.mkdir()
    environment = _isolated_git_environment()
    subprocess.run(
        [
            "git",
            "-c",
            "core.longpaths=true",
            "clone",
            "-q",
            "--shared",
            "--",
            str(generated_repository_template),
            str(root),
        ],
        check=True,
        env=environment,
    )
    _configure_fixture_repository(root, empty_hooks, environment)
    base_sha = subprocess.run(
        ["git", "-c", "core.longpaths=true", "-C", str(root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
        env=environment,
    ).stdout.strip()
    return _ReusableRepository(root, base_sha, empty_hooks, environment)


@pytest.fixture()
def generated_repo_copy(
    reusable_generated_repository: _ReusableRepository,
) -> Path:
    """Return a clean checkout while amortizing setup across one test module."""

    _restore_reusable_repository(reusable_generated_repository)
    return reusable_generated_repository.root
