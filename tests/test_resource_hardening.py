from __future__ import annotations

import shutil
from pathlib import Path

from skillpack_tools.validate import validate_repository

ROOT = Path(__file__).resolve().parents[1]


def _copy_repository(tmp_path: Path) -> Path:
    target = tmp_path / "repository"
    shutil.copytree(
        ROOT,
        target,
        ignore=shutil.ignore_patterns(".git", ".venv", ".pytest_cache", "__pycache__"),
    )
    return target


def _errors(root: Path) -> str:
    return "\n".join(validate_repository(root).errors)


def test_resource_directories_and_recursive_reachability_fail_closed(tmp_path: Path) -> None:
    root = _copy_repository(tmp_path)
    skill = root / "packs/rust/best-practices/skills/rust-abstraction-design"
    scripts = skill / "scripts"

    scripts.mkdir()
    assert "resource directory must not be empty" in _errors(root)

    (scripts / "README.md").write_text("# Scripts\n", encoding="utf-8")
    assert "README-only resource directories are prohibited" in _errors(root)

    (scripts / "orphan.py").write_text("print('fixture')\n", encoding="utf-8")
    combined = _errors(root)
    assert "runtime resource is not reachable from SKILL.md" in combined

    skill_file = skill / "SKILL.md"
    original_skill = skill_file.read_text(encoding="utf-8")
    skill_file.write_text(
        original_skill + "\nThe `scripts/` directory contains helpers.\n", encoding="utf-8"
    )
    assert f"{scripts / 'orphan.py'}: runtime resource is not reachable" in _errors(root)
    skill_file.write_text(
        original_skill + "\nA stale note names `scripts/orphan.py.bak`.\n",
        encoding="utf-8",
    )
    assert f"{scripts / 'orphan.py'}: runtime resource is not reachable" in _errors(root)
    skill_file.write_text(
        original_skill + "\nUse [the exact helper](scripts/orphan.py).\n",
        encoding="utf-8",
    )
    assert f"{scripts / 'orphan.py'}: runtime resource is not reachable" not in _errors(root)
    skill_file.write_text(
        original_skill + "\nUse [the helper directory](scripts/) when needed.\n",
        encoding="utf-8",
    )
    assert f"{scripts / 'orphan.py'}: runtime resource is not reachable" not in _errors(root)

    guide = skill / "references/guide.md"
    guide.write_text(
        guide.read_text(encoding="utf-8") + "\n[Missing nested reference](missing.md)\n",
        encoding="utf-8",
    )
    assert "broken relative link: missing.md" in _errors(root)
