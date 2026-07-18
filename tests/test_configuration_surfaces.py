from __future__ import annotations

import shutil
from pathlib import Path

import pytest
import yaml

from skillpack_tools.configure import configure_repository

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture()
def repo_copy(tmp_path: Path) -> Path:
    target = tmp_path / "repo"

    def ignore(_directory: str, names: list[str]) -> set[str]:
        ignored = {".git", ".pytest_cache", ".venv", "__pycache__"} & set(names)
        ignored.update(name for name in names if name.endswith((".pyc", ".pyo")))
        return ignored

    shutil.copytree(ROOT, target, ignore=ignore)
    return target


def test_configure_rewrites_issue_routing_identity(repo_copy: Path) -> None:
    configure_repository(
        repo_copy,
        owner="example-org",
        repository="portable-skills",
    )

    issue_config = yaml.safe_load(
        (repo_copy / ".github/ISSUE_TEMPLATE/config.yml").read_text(encoding="utf-8")
    )
    urls = {link["url"] for link in issue_config["contact_links"]}
    assert urls == {
        "https://github.com/example-org/portable-skills/security/advisories/new",
        "https://github.com/example-org/portable-skills/discussions/categories/q-a",
    }
    pages_doc = (repo_copy / "docs/github-pages.md").read_text(encoding="utf-8")
    assert "https://example-org.github.io/portable-skills/" in pages_doc
    assert "https://genaptic.github.io/skillsets/" not in pages_doc


def test_configure_rewrites_every_default_branch_workflow_surface(repo_copy: Path) -> None:
    configure_repository(repo_copy, default_branch="release/v2")

    for workflow in ("codeql.yml", "compatibility.yml", "eval.yml", "pages.yml", "validate.yml"):
        text = (repo_copy / ".github/workflows" / workflow).read_text(encoding="utf-8")
        assert '      - "release/v2"\n' in text

    native = (repo_copy / ".github/workflows/native-compatibility.yml").read_text(encoding="utf-8")
    assert '        default: "release/v2"\n' in native
    assert '          DEFAULT_BRANCH: "release/v2"\n' in native

    release = (repo_copy / ".github/workflows/release.yml").read_text(encoding="utf-8")
    assert '          DEFAULT_BRANCH: "release/v2"\n' in release

    pages = (repo_copy / ".github/workflows/pages.yml").read_text(encoding="utf-8")
    assert '          DEFAULT_BRANCH: "release/v2"\n' in pages


def test_dependabot_groups_security_updates_for_every_ecosystem(repo_copy: Path) -> None:
    config = yaml.safe_load((repo_copy / ".github/dependabot.yml").read_text(encoding="utf-8"))

    assert {update["package-ecosystem"] for update in config["updates"]} == {
        "github-actions",
        "pip",
    }
    for update in config["updates"]:
        assert update["groups"]["security-updates"] == {
            "applies-to": "security-updates",
            "patterns": ["*"],
        }


def test_codeowners_names_every_current_pack_explicitly(repo_copy: Path) -> None:
    codeowners = (repo_copy / ".github/CODEOWNERS").read_text(encoding="utf-8")

    for path in (
        "/packs/python/best-practices/",
        "/packs/python/cli-apps/",
        "/packs/rust/best-practices/",
        "/packs/rust/cli-apps/",
        "/packs/shared/postgres-databases/",
        "/packs/shared/repository-development/",
    ):
        assert f"{path} @jecsand838\n" in codeowners
