from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

import pytest

from skillpack_tools.configure import configure_repository
from skillpack_tools.models import discover_packs, load_repository
from skillpack_tools.release import build_release
from skillpack_tools.validate import validate_repository


@pytest.fixture()
def configured_repo(generated_repo_copy: Path) -> Path:
    target = generated_repo_copy
    configure_repository(
        target,
        project_name="Example Skillsets",
        project_description="Portable example skills for native agent clients.",
        owner="example-org",
        repository="skillsets",
        default_branch="main",
        publisher_name="Example Publisher",
        copyright_owner="Example Publisher",
        maintainer_name="Example Maintainer",
        maintainer_github="example-maintainer",
        maintainer_github_id=123456,
        trusted_ssh_fingerprint="SHA256:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
        security_channel="github-private-vulnerability-reporting",
        marketplace_name="example-skillsets",
        marketplace_display_name="Example Skillsets",
        marketplace_description="Portable example skills for native agent clients.",
        license_id="Apache-2.0",
        initial_year=2026,
    )
    return target


def test_configure_replaces_every_identity_surface(configured_repo: Path) -> None:
    config = load_repository(configured_repo)
    assert config.project_name == "Example Skillsets"
    assert config.slug == "example-org/skillsets"
    assert config.publisher_name == "Example Publisher"
    assert config.maintainer_name == "Example Maintainer"
    assert config.security_email is None
    assert config.security_url == (
        "https://github.com/example-org/skillsets/security/advisories/new"
    )
    assert "@example-maintainer" in (configured_repo / ".github/CODEOWNERS").read_text(
        encoding="utf-8"
    )
    env = (configured_repo / ".env.example").read_text(encoding="utf-8")
    assert "GENAPTIC_SKILLSETS_REPOSITORY=example-org/skillsets" in env
    assert "PGHOST=" in env
    assert "PGPORT=5432" in env
    assert "AGENT_SKILLPACKS_" not in env
    assert "example-org/skillsets/security/advisories/new" in (
        configured_repo / "SECURITY.md"
    ).read_text(encoding="utf-8")
    assert "Copyright 2026 Example Publisher" in (configured_repo / "NOTICE").read_text(
        encoding="utf-8"
    )
    for pack in discover_packs(configured_repo):
        assert pack.maintainers == [{"github": "example-maintainer"}]
    marketplace = json.loads(
        (configured_repo / ".claude-plugin/marketplace.json").read_text(encoding="utf-8")
    )
    assert marketplace["owner"]["name"] == "Example Publisher"
    release_intent_schema = json.loads(
        (configured_repo / "schemas/release-intent.schema.json").read_text(encoding="utf-8")
    )
    assert release_intent_schema["$id"] == (
        "https://raw.githubusercontent.com/example-org/skillsets/main/"
        "schemas/release-intent.schema.json"
    )
    result = validate_repository(
        configured_repo,
        check_generated=True,
        strict_placeholders=True,
    )
    assert result.ok, result.errors
    assert result.warnings == []


def test_pack_release_is_deterministic_and_bounded(configured_repo: Path) -> None:
    first, checksum, notes = build_release(configured_repo, "python-best-practices", draft=True)
    first_bytes = first.read_bytes()
    first_digest = hashlib.sha256(first_bytes).hexdigest()
    assert checksum.read_text(encoding="utf-8").startswith(first_digest)
    notes_text = notes.read_text(encoding="utf-8")
    assert "python-best-practices-v1.0.0" in notes_text
    assert notes_text.count("# Changelog") == 1
    assert notes_text.count("Prepared the `1.0.0` release-candidate contents") == 1

    second, _, _ = build_release(configured_repo, "python-best-practices", draft=True)
    assert second.read_bytes() == first_bytes

    with zipfile.ZipFile(second) as archive:
        names = archive.namelist()
        assert names
        assert all(name.startswith("python-best-practices-v1.0.0-draft/") for name in names)
        assert all(".." not in Path(name).parts for name in names)
        assert all(info.date_time == (1980, 1, 1, 0, 0, 0) for info in archive.infolist())
        assert any(name.endswith("python-project-layout/SKILL.md") for name in names)
        helper = next(
            info
            for info in archive.infolist()
            if info.filename.endswith("scripts/inspect_layout.py")
        )
        assert helper.create_system == 3
        assert (helper.external_attr >> 16) & 0o777 == 0o755
