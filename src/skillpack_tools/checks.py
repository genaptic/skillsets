from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

from .evals import run_structural_evals
from .generate import apply_generated_files
from .models import get_pack
from .util import SkillpackError
from .validate import raise_for_result, validate_repository


def _run(root: Path, command: Sequence[str], *, environment: dict[str, str] | None = None) -> None:
    printable = " ".join(command)
    print(f"+ {printable}")
    completed = subprocess.run(
        list(command),
        cwd=root,
        env=environment,
        check=False,
    )
    if completed.returncode:
        raise SkillpackError(f"Check failed with exit code {completed.returncode}: {printable}")


def lock(root: Path, *, check: bool) -> None:
    python = sys.executable
    if check:
        _run(root, [python, "tools/check-dependency-lock"])
        return
    environment = os.environ.copy()
    environment["CUSTOM_COMPILE_COMMAND"] = "skillpacks lock"
    _run(
        root,
        [
            python,
            "-m",
            "piptools",
            "compile",
            "--allow-unsafe",
            "--generate-hashes",
            "--quiet",
            "--strip-extras",
            "--resolver=backtracking",
            "--output-file=requirements-dev.txt",
            "requirements-dev.in",
        ],
        environment=environment,
    )


def lint(root: Path) -> None:
    python = sys.executable
    _run(root, [python, "-m", "ruff", "check", "."])
    _run(root, [python, "-m", "ruff", "format", "--check", "."])
    _run(root, [python, "tools/lint-portable"])


def test(root: Path) -> None:
    _run(root, [sys.executable, "-m", "pytest"])


def check(root: Path) -> None:
    """Run the complete non-mutating repository gate in its documented order."""

    python = sys.executable
    lock(root, check=True)
    _run(
        root,
        [
            python,
            "tools/check-rust-assets",
            "--cargo-home",
            str(root / ".venv" / "rust-cargo-home"),
        ],
    )
    apply_generated_files(root, check=True)
    raise_for_result(validate_repository(root, check_generated=True, strict_placeholders=True))
    run_structural_evals(root)
    lint(root)
    test(root)


def check_pack(root: Path, pack_id: str) -> None:
    """Run a focused pack check while retaining repository-wide graph invariants."""

    try:
        pack = get_pack(root, pack_id)
    except KeyError as exc:
        raise SkillpackError(str(exc)) from exc
    apply_generated_files(root, check=True)
    raise_for_result(
        validate_repository(
            root,
            check_generated=True,
            strict_placeholders=True,
            pack_filter=pack.id,
        )
    )
    for skill in pack.skills:
        run_structural_evals(root, skill_filter=skill)
    _run(root, [sys.executable, "-m", "ruff", "check", pack.relative_path])
    _run(root, [sys.executable, "-m", "ruff", "format", "--check", pack.relative_path])
    if pack.language == "rust":
        _run(
            root,
            [
                sys.executable,
                "tools/check-rust-assets",
                "--pack",
                pack.id,
                "--cargo-home",
                str(root / ".venv" / "rust-cargo-home"),
            ],
        )
    print(
        f"Focused checks passed for {pack.id}. Full `skillpacks check` remains mandatory "
        "before merge or release."
    )
