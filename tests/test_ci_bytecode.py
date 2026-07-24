from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _canonical_bytecode(repository: Path) -> list[Path]:
    residue: list[Path] = []
    for relative in ("src", "tools", "tests", "packs"):
        root = repository / relative
        residue.extend(root.rglob("__pycache__"))
        residue.extend(root.rglob("*.pyc"))
        residue.extend(root.rglob("*.pyo"))
    return residue


def test_validation_job_redirects_bytecode_before_any_python_invocation() -> None:
    workflow = (ROOT / ".github/workflows/validate.yml").read_text(encoding="utf-8")
    repository_job = workflow.split("  repository:\n", maxsplit=1)[1].split(
        "\n  rust-assets:\n", maxsplit=1
    )[0]
    redirect = repository_job.index("      - name: Redirect Python bytecode outside the worktree")
    first_repository_python = repository_job.index(
        "      - name: Install the hash-locked toolchain"
    )
    assert redirect < first_repository_python
    assert "$RUNNER_TEMP/genaptic-python-cache/${{ matrix.python-version }}" in repository_job
    assert "PYTHONPYCACHEPREFIX=%s\\n" in repository_job
    assert '"$GITHUB_ENV"' in repository_job
    assert "${{ runner.temp }}" not in repository_job


def test_compileall_external_cache_keeps_repository_validation_clean(
    tmp_path: Path,
    generated_repo_copy: Path,
) -> None:
    repository = generated_repo_copy
    cache = tmp_path / "python-cache"
    environment = os.environ.copy()
    environment["PYTHONPYCACHEPREFIX"] = str(cache)

    subprocess.run(
        [sys.executable, "-m", "compileall", "-q", "src", "tools", "tests", "packs"],
        cwd=repository,
        env=environment,
        check=True,
        timeout=120,
    )
    assert any(cache.rglob("*.pyc"))
    assert _canonical_bytecode(repository) == []

    subprocess.run(
        [sys.executable, "tools/generate-all", "--check"],
        cwd=repository,
        env=environment,
        check=True,
        timeout=120,
    )

    assert _canonical_bytecode(repository) == []
