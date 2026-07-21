from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


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
    for key, value in (
        ("user.name", "Fixture"),
        ("user.email", "fixture@example.invalid"),
        ("commit.gpgsign", "false"),
        ("core.autocrlf", "false"),
        ("core.hooksPath", str(empty_hooks)),
        ("core.longpaths", "true"),
    ):
        subprocess.run(
            ["git", "-C", str(root), "config", key, value],
            check=True,
            env=environment,
        )
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


@pytest.fixture()
def generated_repo_copy(
    tmp_path_factory: pytest.TempPathFactory, generated_repository_template: Path
) -> Path:
    """Create an isolated local clone without rebuilding every generated surface."""

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
    for key, value in (
        ("user.name", "Fixture"),
        ("user.email", "fixture@example.invalid"),
        ("commit.gpgsign", "false"),
        ("core.autocrlf", "false"),
        ("core.hooksPath", str(empty_hooks)),
        ("core.longpaths", "true"),
    ):
        subprocess.run(
            ["git", "-C", str(root), "config", key, value],
            check=True,
            env=environment,
        )
    return root
