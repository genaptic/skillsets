from __future__ import annotations

import subprocess
from copy import deepcopy
from pathlib import Path

import pytest

from skillpack_tools import release
from skillpack_tools.models import Pack
from skillpack_tools.util import SkillpackError


def _pack(tmp_path: Path, **overrides: object) -> Pack:
    pack_path = tmp_path / "packs" / "python" / "example"
    pack_path.mkdir(parents=True)
    raw: dict[str, object] = {
        "schema-version": 2,
        "id": "example-pack",
        "display-name": "Example Pack",
        "description": "Example release fixture.",
        "language": "python",
        "subject": "example",
        "version": "1.0.0",
        "maturity": "stable",
        "distribution": {"visibility": "public"},
        "publication": {"state": "unpublished"},
        "release-gates": ["native-evidence", "deterministic-archive"],
        "interface": {
            "short-description": "Exercise deterministic release checks.",
            "starter-prompts": [
                {"skill": "example-skill", "prompt": "Use $example-skill to review this."},
                {"skill": "other-skill", "prompt": "Use $other-skill to check that."},
            ],
        },
        "license": "Apache-2.0",
        "maintainers": [{"github": "maintainer"}],
        "skills": ["example-skill", "other-skill"],
        "targets": ["claude-code", "codex", "opencode"],
        "category": "testing",
        "keywords": ["testing"],
        "compatibility": {},
        "operations": {},
    }
    raw.update(overrides)
    (pack_path / "CHANGELOG.md").write_text(
        "# Changelog\n\n## [Unreleased]\n\n## [1.0.0] - 2026-07-19\n\n- Initial release.\n",
        encoding="utf-8",
    )
    (pack_path / "README.md").write_text("# Example Pack\n\nReady for release.\n", encoding="utf-8")
    for skill in raw["skills"]:  # type: ignore[union-attr]
        skill_path = pack_path / "skills" / str(skill) / "SKILL.md"
        skill_path.parent.mkdir(parents=True)
        skill_path.write_text(
            "---\n"
            f"name: {skill}\n"
            "description: Exercise release-readiness validation.\n"
            "license: Apache-2.0\n"
            "metadata:\n"
            '  version: "1.0.0"\n'
            '  maturity: "stable"\n'
            "---\n\n# Fixture\n",
            encoding="utf-8",
        )
    return Pack(root=tmp_path, path=pack_path, raw=raw)


def _with_raw(pack: Pack, **updates: object) -> Pack:
    raw = deepcopy(pack.raw)
    raw.update(updates)
    return Pack(root=pack.root, path=pack.path, raw=raw)


def test_git_wrapper_reports_missing_git_and_command_failures(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        release.subprocess,
        "check_output",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("missing")),
    )
    with pytest.raises(SkillpackError, match="Git is required"):
        release._git(tmp_path, "status")

    failure = subprocess.CalledProcessError(1, ["git"], stderr="not a repository\n")
    monkeypatch.setattr(
        release.subprocess,
        "check_output",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(failure),
    )
    with pytest.raises(SkillpackError, match="not a repository"):
        release._git(tmp_path, "status")


@pytest.mark.parametrize(
    ("updates", "message"),
    [
        ({"maturity": "release-candidate"}, "maturity must be 'stable'"),
        ({"distribution": {"visibility": "maintainers"}}, "maintainer-only"),
        (
            {
                "publication": {
                    "state": "withdrawn",
                    "latest-release": {
                        "version": "1.0.0",
                        "source-sha": "a" * 40,
                        "release-id": 1,
                        "released-at": "2026-07-19T18:30:00Z",
                    },
                }
            },
            "withdrawn packs",
        ),
        (
            {
                "publication": {
                    "state": "published",
                    "latest-release": {
                        "version": "1.0.0",
                        "source-sha": "a" * 40,
                        "release-id": 1,
                        "released-at": "2026-07-19T18:30:00Z",
                    },
                }
            },
            "must be newer than the last public release",
        ),
    ],
)
def test_release_readiness_rejects_nonpublishable_lifecycle(
    tmp_path: Path, updates: dict[str, object], message: str
) -> None:
    pack = _with_raw(_pack(tmp_path), **updates)
    with pytest.raises(SkillpackError, match=message):
        release._require_release_readiness(pack)


def test_release_readiness_rejects_changelog_and_readme_placeholders(tmp_path: Path) -> None:
    pack = _pack(tmp_path)
    changelog = pack.path / "CHANGELOG.md"
    readme = pack.path / "README.md"

    changelog.write_text("# Changelog\n", encoding="utf-8")
    with pytest.raises(SkillpackError, match="exactly one"):
        release._require_release_readiness(pack)

    changelog.write_text("# Changelog\n\n## [Unreleased]\n\n- Pending.\n", encoding="utf-8")
    with pytest.raises(SkillpackError, match="must be empty"):
        release._require_release_readiness(pack)

    changelog.write_text(
        "# Changelog\n\n## [Unreleased]\n\n## [1.0.0]\n\n- Release-candidate build.\n",
        encoding="utf-8",
    )
    with pytest.raises(SkillpackError, match="release-candidate wording"):
        release._require_release_readiness(pack)

    changelog.write_text(
        "# Changelog\n\n## [Unreleased]\n\n## [1.0.0]\n\n- Stable build.\n",
        encoding="utf-8",
    )
    readme.write_text("This is an unpublished release candidate.\n", encoding="utf-8")
    with pytest.raises(SkillpackError, match=r"README\.md"):
        release._require_release_readiness(pack)


def test_release_readiness_checks_each_skill_mirror(tmp_path: Path) -> None:
    pack = _pack(tmp_path)
    release._require_release_readiness(pack)
    skill_file = pack.path / "skills" / "example-skill" / "SKILL.md"

    original = skill_file.read_text(encoding="utf-8")
    skill_file.write_text(
        original.replace('maturity: "stable"', 'maturity: "draft"'), encoding="utf-8"
    )
    with pytest.raises(SkillpackError, match=r"metadata\.maturity"):
        release._require_release_readiness(pack)

    skill_file.write_text(
        original.replace('version: "1.0.0"', 'version: "1.0.1"'), encoding="utf-8"
    )
    with pytest.raises(SkillpackError, match=r"metadata\.version"):
        release._require_release_readiness(pack)
