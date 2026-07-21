from __future__ import annotations

from pathlib import Path

from skillpack_tools.models import get_pack
from skillpack_tools.validate import _validate_skill, validate_repository


def _skill_errors(root: Path) -> str:
    pack = get_pack(root, "rust-best-practices")
    skill = "rust-abstraction-design"
    errors: list[str] = []
    warnings: list[str] = []
    _validate_skill(
        root,
        pack.id,
        pack.version,
        pack.maturity,
        skill,
        pack.path / "skills" / skill,
        errors,
        warnings,
    )
    assert warnings == []
    return "\n".join(errors)


def test_resource_directories_and_recursive_reachability_fail_closed(
    generated_repo_copy: Path,
) -> None:
    root = generated_repo_copy
    skill = root / "packs/rust/best-practices/skills/rust-abstraction-design"
    scripts = skill / "scripts"

    scripts.mkdir()
    assert "resource directory must not be empty" in "\n".join(validate_repository(root).errors)

    (scripts / "README.md").write_text("# Scripts\n", encoding="utf-8")
    assert "README-only resource directories are prohibited" in _skill_errors(root)

    (scripts / "orphan.py").write_text("print('fixture')\n", encoding="utf-8")
    combined = _skill_errors(root)
    assert "runtime resource is not reachable from SKILL.md" in combined

    skill_file = skill / "SKILL.md"
    original_skill = skill_file.read_text(encoding="utf-8")
    skill_file.write_text(
        original_skill + "\nThe `scripts/` directory contains helpers.\n", encoding="utf-8"
    )
    assert f"{scripts / 'orphan.py'}: runtime resource is not reachable" in _skill_errors(root)
    skill_file.write_text(
        original_skill + "\nA stale note names `scripts/orphan.py.bak`.\n",
        encoding="utf-8",
    )
    assert f"{scripts / 'orphan.py'}: runtime resource is not reachable" in _skill_errors(root)
    skill_file.write_text(
        original_skill + "\nUse [the exact helper](scripts/orphan.py).\n",
        encoding="utf-8",
    )
    assert f"{scripts / 'orphan.py'}: runtime resource is not reachable" not in _skill_errors(root)
    skill_file.write_text(
        original_skill + "\nUse [the helper directory](scripts/) when needed.\n",
        encoding="utf-8",
    )
    assert f"{scripts / 'orphan.py'}: runtime resource is not reachable" not in _skill_errors(root)

    guide = skill / "references/guide.md"
    guide.write_text(
        guide.read_text(encoding="utf-8") + "\n[Missing nested reference](missing.md)\n",
        encoding="utf-8",
    )
    assert "broken relative link: missing.md" in _skill_errors(root)
