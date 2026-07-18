from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tomllib
import zipfile
from copy import deepcopy
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator

from skillpack_tools import release as release_module
from skillpack_tools.configure import configure_repository
from skillpack_tools.evals import eval_report, run_structural_evals
from skillpack_tools.generate import apply_generated_files, build_generated_files
from skillpack_tools.models import get_pack, load_repository
from skillpack_tools.release import build_release
from skillpack_tools.util import SkillpackError, dump_yaml, load_yaml
from skillpack_tools.validate import (
    _placeholder_hits,
    validate_compatibility_report,
)

ROOT = Path(__file__).resolve().parents[1]
ANSI_ESCAPE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


def _copy_ignore(_directory: str, names: list[str]) -> set[str]:
    ignored = {".git", ".idea", ".pytest_cache", ".venv", "__pycache__"} & set(names)
    ignored.update(name for name in names if name.endswith((".pyc", ".pyo")))
    return ignored


@pytest.fixture()
def repo_copy(tmp_path: Path) -> Path:
    target = tmp_path / "skillsets"
    shutil.copytree(ROOT, target, ignore=_copy_ignore)
    configure_repository(target)
    return target


def _write_manifest(root: Path, pack_id: str, mutate) -> None:
    pack = get_pack(root, pack_id)
    data = load_yaml(pack.path / "skillpack.yaml")
    mutate(data)
    (pack.path / "skillpack.yaml").write_text(dump_yaml(data), encoding="utf-8")


def _normalized_process_output(completed: subprocess.CompletedProcess[str]) -> str:
    plain = ANSI_ESCAPE.sub("", completed.stdout + completed.stderr)
    return " ".join(plain.split())


def test_process_output_normalization_removes_ansi_and_diagnostic_wrapping() -> None:
    completed = subprocess.CompletedProcess(
        args=["pwsh"],
        returncode=1,
        stdout="",
        stderr="\x1b[31;1mInstalled CLI does not support 'gh skill'\x1b[0m\ncommand.\n",
    )

    assert _normalized_process_output(completed) == (
        "Installed CLI does not support 'gh skill' command."
    )


def _write_fake_gh(directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        executable = directory / "gh.cmd"
        executable.write_text(
            """@echo off
>>"%GH_FAKE_LOG%" echo %GH_TELEMETRY%^|%GH_PROMPT_DISABLED%^|%GH_NO_UPDATE_NOTIFIER%^|%*
if "%1:%2"=="skill:--help" (
  if "%GH_FAKE_MODE%"=="group-unsupported" exit /b 1
  exit /b 0
)
if "%1:%2:%3"=="skill:install:--help" (
  if "%GH_FAKE_MODE%"=="install-unsupported" exit /b 1
  exit /b 0
)
if "%1:%2"=="skill:install" exit /b 0
exit /b 64
""",
            encoding="utf-8",
        )
    else:
        executable = directory / "gh"
        executable.write_text(
            """#!/bin/sh
printf '%s|%s|%s|%s\\n' \
  "$GH_TELEMETRY" "$GH_PROMPT_DISABLED" "$GH_NO_UPDATE_NOTIFIER" "$*" \
  >> "$GH_FAKE_LOG"
case "${1-}:${2-}:${3-}" in
  skill:--help:)
    [ "${GH_FAKE_MODE-}" != "group-unsupported" ]
    ;;
  skill:install:--help)
    [ "${GH_FAKE_MODE-}" != "install-unsupported" ]
    ;;
  skill:install:*)
    exit 0
    ;;
  *)
    exit 64
    ;;
esac
""",
            encoding="utf-8",
        )
        executable.chmod(0o755)
    return executable


def _compatibility_report(root: Path, pack_id: str, source_sha: str, client: str) -> dict:
    pack = get_pack(root, pack_id)
    routing: list[dict[str, object]] = []
    behavior: list[dict[str, object]] = []
    for skill in pack.skills:
        data = json.loads(
            (pack.path / "skills" / skill / "evals" / "evals.json").read_text(encoding="utf-8")
        )
        routing.extend(
            {"skill": skill, "id": case["id"], "passed": True, "notes": ""}
            for case in data["routing"]
        )
        behavior.extend(
            {"skill": skill, "id": case["id"], "passed": True, "notes": ""}
            for case in data["behavior"]
        )
    return {
        "schemaVersion": 1,
        "date": "2026-07-17",
        "client": {"name": client, "version": "1.2.3", "model": "test-model"},
        "pack": {
            "id": pack.id,
            "version": pack.version,
            "tag": pack.tag,
            "sourceSha": source_sha,
            "expectedSkills": pack.skills,
        },
        "environment": {"operatingSystem": "test-os", "shell": "test-shell"},
        "installation": {
            "method": "isolated native-client fixture",
            "discoveredSkills": pack.skills,
            "permissions": ["read repository"],
        },
        "cases": {"routing": routing, "behavior": behavior},
        "effects": {"network": [], "filesystem": ["temporary client home"]},
        "reviewer": {"name": "Reviewer", "github": "reviewer", "verdict": "passed"},
        "verdict": {"status": "passed", "notes": "All declared cases passed."},
    }


def test_generation_is_byte_safe_filtered_mode_aware_and_target_aware(
    repo_copy: Path,
) -> None:
    pack = get_pack(repo_copy, "python-best-practices")
    skill = pack.path / "skills" / "python-project-layout"
    binary = skill / "assets" / "fixture.bin"
    binary.write_bytes(b"\x00\xff\x80binary\r\n")
    (skill / "assets" / ".env.secret").write_text("TOKEN=nope\n", encoding="utf-8")
    (skill / "assets" / ".env.example").write_text("TOKEN=\n", encoding="utf-8")
    (skill / "assets" / "private.pem").write_text("secret\n", encoding="utf-8")
    (skill / "assets" / "id_ed25519").write_text("secret\n", encoding="utf-8")
    (skill / "assets" / "ignored.pyc").write_bytes(b"bytecode")
    executable_asset = skill / "assets" / "fixture-tool"
    executable_asset.write_text("fixture\n", encoding="utf-8")
    executable_asset.chmod(0o755)
    script_data = skill / "scripts" / "data.json"
    script_data.write_text('{"fixture": true}\n', encoding="utf-8")
    script_data.chmod(0o644)
    cache = skill / "assets" / ".cache"
    cache.mkdir()
    (cache / "ignored.bin").write_bytes(b"cache")

    generated = build_generated_files(repo_copy)
    output = "dist/opencode/python/best-practices/python-project-layout/assets/fixture.bin"
    assert generated[output] == binary.read_bytes()
    assert all(".env.secret" not in path and not path.endswith(".pyc") for path in generated)
    assert any(path.endswith("/.env.example") for path in generated)
    assert all(not path.endswith((".pem", "/id_ed25519")) for path in generated)
    assert all("/.cache/" not in path for path in generated)
    helper = "dist/opencode/python/best-practices/python-project-layout/scripts/inspect_layout.py"
    assert generated.modes[helper] == 0o755
    assert (
        generated.modes[
            "dist/opencode/python/best-practices/python-project-layout/assets/fixture-tool"
        ]
        == 0o755
    )
    assert (
        generated.modes[
            "dist/opencode/python/best-practices/python-project-layout/scripts/data.json"
        ]
        == 0o644
    )

    apply_generated_files(repo_copy)
    assert (repo_copy / output).read_bytes() == binary.read_bytes()
    if os.name != "nt":
        assert (repo_copy / helper).stat().st_mode & 0o777 == 0o755

    stale_claude = pack.path / ".claude-plugin" / "plugin.json"
    stale_installer = repo_copy / "dist" / "install" / f"{pack.id}.sh"

    def remove_targets(data: dict) -> None:
        data["targets"] = ["codex"]

    _write_manifest(repo_copy, pack.id, remove_targets)
    changed = apply_generated_files(repo_copy)
    assert stale_claude.relative_to(repo_copy).as_posix() in changed
    assert stale_installer.relative_to(repo_copy).as_posix() in changed
    assert not stale_claude.exists()
    assert not stale_installer.exists()
    readme = (pack.path / "README.md").read_text(encoding="utf-8")
    assert "### Codex" in readme
    assert "### Claude Code" not in readme
    assert "### OpenCode or direct install" not in readme


def test_source_sha_controls_marketplace_and_catalog_publication(repo_copy: Path) -> None:
    local = build_generated_files(repo_copy)
    claude = json.loads(local[".claude-plugin/marketplace.json"])
    item = next(item for item in claude["plugins"] if item["name"] == "python-best-practices")
    assert item["source"] == "./packs/python/best-practices"
    catalog = json.loads(local["catalog.json"])
    pack = next(item for item in catalog["packs"] if item["id"] == "python-best-practices")
    assert pack["publication"] == {"state": "unpublished", "sourceType": "repo-local"}

    source_sha = "a" * 40
    _write_manifest(
        repo_copy,
        "python-best-practices",
        lambda data: data.__setitem__("source-sha", source_sha),
    )
    published = build_generated_files(repo_copy)
    claude = json.loads(published[".claude-plugin/marketplace.json"])
    item = next(item for item in claude["plugins"] if item["name"] == "python-best-practices")
    assert item["source"]["source"] == "git-subdir"
    assert item["source"]["sha"] == source_sha
    catalog = json.loads(published["catalog.json"])
    pack = next(item for item in catalog["packs"] if item["id"] == "python-best-practices")
    assert pack["publication"] == {
        "state": "published",
        "sourceType": "git-subdir",
        "sourceSha": source_sha,
    }


def test_generated_manifest_and_generalized_pack_schemas(repo_copy: Path) -> None:
    generated = build_generated_files(repo_copy)
    manifest = json.loads(generated["dist/generated-files.json"])
    schema = json.loads((repo_copy / "schemas/generated-files.schema.json").read_text())
    assert list(Draft202012Validator(schema).iter_errors(manifest)) == []
    binary_entries = [entry for entry in manifest["files"] if entry["path"].endswith(".png")]
    assert all({"path", "sha256", "size", "mode"} <= set(entry) for entry in manifest["files"])
    assert binary_entries or manifest["files"]

    pack_schema = json.loads((repo_copy / "schemas/skillpack.schema.json").read_text())
    one_skill = deepcopy(get_pack(repo_copy, "python-best-practices").raw)
    one_skill["skills"] = one_skill["skills"][:1]
    one_skill["compatibility"] = {
        "runtimes": {"nodejs": ">=22 for optional helpers"},
        "notes": "Core instructions remain portable across supported clients.",
    }
    assert list(Draft202012Validator(pack_schema).iter_errors(one_skill)) == []

    catalog_schema = json.loads((repo_copy / "schemas/catalog.schema.json").read_text())
    catalog = json.loads(generated["catalog.json"])
    assert list(Draft202012Validator(catalog_schema).iter_errors(catalog)) == []
    catalog["packs"][0]["version"] = "1.0.0junk"
    assert list(Draft202012Validator(catalog_schema).iter_errors(catalog))

    eval_schema = json.loads((repo_copy / "schemas/eval-report.schema.json").read_text())
    report = eval_report(run_structural_evals(repo_copy, skill_filter="python-project-layout"))
    assert list(Draft202012Validator(eval_schema).iter_errors(report)) == []
    del report["skills"][0]["routing"][0]["prompt"]
    assert list(Draft202012Validator(eval_schema).iter_errors(report))


def test_eval_export_contains_complete_prompts_and_expectations() -> None:
    report = eval_report(run_structural_evals(ROOT, skill_filter="python-project-layout"))
    skill = report["skills"][0]
    assert skill["routingCases"] == len(skill["routing"]) == 7
    assert skill["behaviorCases"] == len(skill["behavior"]) == 2
    assert all({"prompt", "shouldTrigger", "reason"} <= set(case) for case in skill["routing"])
    assert any(case.get("preferredSkill") for case in skill["routing"])
    assert all({"prompt", "assertions", "forbidden"} <= set(case) for case in skill["behavior"])


def test_compatibility_report_binds_all_cases_pack_sha_and_verdict(
    repo_copy: Path, tmp_path: Path
) -> None:
    source_sha = "b" * 40
    path = tmp_path / "codex.json"
    data = _compatibility_report(repo_copy, "python-best-practices", source_sha, "codex")
    path.write_text(json.dumps(data), encoding="utf-8")
    errors, loaded = validate_compatibility_report(
        repo_copy,
        path,
        pack=get_pack(repo_copy, "python-best-practices"),
        source_sha=source_sha,
    )
    assert errors == []
    assert loaded == data

    data["cases"]["routing"].pop()
    data["reviewer"]["verdict"] = "failed"
    path.write_text(json.dumps(data), encoding="utf-8")
    errors, _ = validate_compatibility_report(
        repo_copy,
        path,
        pack=get_pack(repo_copy, "python-best-practices"),
        source_sha=source_sha,
    )
    assert "routing cases must cover" in "\n".join(errors)
    assert "reviewer.verdict" in "\n".join(errors)

    future = _compatibility_report(repo_copy, "python-best-practices", source_sha, "codex")
    future["date"] = "2999-01-01"
    path.write_text(json.dumps(future), encoding="utf-8")
    errors, _ = validate_compatibility_report(
        repo_copy,
        path,
        pack=get_pack(repo_copy, "python-best-practices"),
        source_sha=source_sha,
    )
    assert "cannot be in the future" in "\n".join(errors)


def test_configure_is_explicit_idempotent_and_preserves_environment(repo_copy: Path) -> None:
    env = repo_copy / ".env.example"
    env.write_text(env.read_text(encoding="utf-8") + "PGHOST=localhost\n", encoding="utf-8")
    arguments = {
        "project_name": "Example Skillsets",
        "project_description": "Portable example skills for three native agent clients.",
        "owner": "example-org",
        "repository": "skills",
        "default_branch": "trunk",
        "publisher_name": "Example Publisher",
        "copyright_owner": "Example Publisher",
        "maintainer_name": "Example Maintainer",
        "maintainer_github": "example-maintainer",
        "security_channel": "github-private-vulnerability-reporting",
        "marketplace_name": "example-skillsets",
        "marketplace_display_name": "Example Skillsets",
        "marketplace_description": "Portable example skills for three native agent clients.",
        "license_id": "Apache-2.0",
        "initial_year": 2026,
    }
    assert configure_repository(repo_copy, **arguments)
    assert configure_repository(repo_copy, **arguments) == []
    config = load_repository(repo_copy)
    assert config.project_name == "Example Skillsets"
    assert config.publisher_name == "Example Publisher"
    assert config.security_email is None
    assert config.security_url.endswith("/security/advisories/new")
    text = env.read_text(encoding="utf-8")
    assert "GENAPTIC_SKILLSETS_REPOSITORY=example-org/skills" in text
    assert "PGHOST=localhost" in text
    assert "AGENT_SKILLPACKS" not in text
    assert "example-org/skills/security/advisories/new" in (repo_copy / "SECURITY.md").read_text(
        encoding="utf-8"
    )
    assert "Example Skillsets" in (repo_copy / "GOVERNANCE.md").read_text(encoding="utf-8")
    assert "Example Skillsets" in (repo_copy / "CHANGELOG.md").read_text(encoding="utf-8")
    for workflow in ("codeql.yml", "compatibility.yml", "eval.yml", "validate.yml"):
        text = (repo_copy / ".github/workflows" / workflow).read_text(encoding="utf-8")
        assert '      - "trunk"\n' in text
    native = (repo_copy / ".github/workflows/native-compatibility.yml").read_text(encoding="utf-8")
    assert '        default: "trunk"\n' in native
    release = (repo_copy / ".github/workflows/release.yml").read_text(encoding="utf-8")
    assert "success\\tworkflow_dispatch\\ttrunk\\t" in release


def test_configure_serializes_quoted_identity_and_yaml_scalar_branch_names(
    repo_copy: Path,
) -> None:
    project_name = 'Genaptic "Quoted" Skillsets'
    publisher_name = 'Example "Publisher" \\ Documentation'
    maintainer_name = 'Example "Maintainer"'
    arguments = {
        "project_name": project_name,
        "project_description": (
            'Portable "quoted" skills for deterministic structured-output validation.'
        ),
        "publisher_name": publisher_name,
        "copyright_owner": publisher_name,
        "maintainer_name": maintainer_name,
        "marketplace_display_name": 'Example "Quoted" Skillsets',
        "marketplace_description": (
            'Portable "quoted" skills for deterministic marketplace validation.'
        ),
        "default_branch": "true",
    }
    assert configure_repository(repo_copy, **arguments)

    for schema_path in sorted((repo_copy / "schemas").glob("*.json")):
        json.loads(schema_path.read_text(encoding="utf-8"))
    pyproject = tomllib.loads((repo_copy / "pyproject.toml").read_text(encoding="utf-8"))
    assert pyproject["project"]["authors"][0]["name"] == publisher_name
    citation = yaml.safe_load((repo_copy / "CITATION.cff").read_text(encoding="utf-8"))
    assert citation["title"] == project_name
    assert citation["authors"][0] == {
        "family-names": '"Maintainer"',
        "given-names": "Example",
    }

    for branch in ("true", "null", "123", "1.2"):
        configure_repository(repo_copy, default_branch=branch)
        branch_line = f'      - "{branch}"\n'
        for workflow in ("codeql.yml", "compatibility.yml", "eval.yml", "validate.yml"):
            text = (repo_copy / ".github/workflows" / workflow).read_text(encoding="utf-8")
            assert branch_line in text
            yaml.safe_load(text)
        native = (repo_copy / ".github/workflows/native-compatibility.yml").read_text(
            encoding="utf-8"
        )
        assert f'        default: "{branch}"\n' in native
        yaml.safe_load(native)

    assert configure_repository(repo_copy, default_branch="1.2") == []


def test_configure_identity_replacement_is_single_pass_for_overlapping_slugs(
    repo_copy: Path,
) -> None:
    configure_repository(
        repo_copy,
        repository="skillsets-next",
        project_name="Genaptic Skillsets Next",
    )

    expected_slug = "genaptic/skillsets-next"
    duplicated_slug = "genaptic/skillsets-next-next"
    for relative in (
        "README.md",
        "SECURITY.md",
        "schemas/repository.schema.json",
    ):
        text = (repo_copy / relative).read_text(encoding="utf-8")
        assert expected_slug in text
        assert duplicated_slug not in text

    assert configure_repository(repo_copy, repository="skillsets-next") == []


def test_release_workflow_protects_and_binds_the_exact_rust_tested_tag(repo_copy: Path) -> None:
    workflow = (repo_copy / ".github/workflows/release.yml").read_text(encoding="utf-8")
    rust_job = workflow.split("  rust-assets:\n", 1)[1].split("\n  release:\n", 1)[0]
    release_job = workflow.split("\n  release:\n", 1)[1]

    assert "    environment: release\n" in rust_job
    assert "      source_sha: ${{ steps.tested-source.outputs.sha }}\n" in rust_job
    attestation = (
        "      - name: Verify GitHub's signed-tag attestation before running repository code"
    )
    assert rust_job.index(attestation) < rust_job.index("      - name: Set up Python")
    assert "GH_TOKEN: ${{ github.token }}" in rust_job
    assert "git/tags/$tag_object" in rust_job
    assert "'.verification.verified'" in rust_job

    tested_sha = "${{ needs.rust-assets.outputs.source_sha }}"
    assert f"          ref: {tested_sha}\n" in release_job
    assert f"          RUST_TESTED_SHA: {tested_sha}\n" in release_job
    assert "if head != rust_tested:" in release_job
    assert "if tagged != head:" in release_job
    assert "Verify GitHub's signed-tag attestation" in release_job


def test_strict_placeholder_scan_covers_distribution_surfaces(repo_copy: Path) -> None:
    assert _placeholder_hits(repo_copy) == []
    path = repo_copy / "docs" / "placeholder.md"
    path.write_text("Install from OWNER/REPO and replace YOUR_HANDLE.\n", encoding="utf-8")
    hits = _placeholder_hits(repo_copy)
    assert any("OWNER/REPO" in hit for hit in hits)
    assert any("YOUR_" in hit for hit in hits)


def test_draft_release_is_marked_deterministic_and_allowlisted(repo_copy: Path) -> None:
    rogue = get_pack(repo_copy, "python-best-practices").path / "rogue-secret.txt"
    rogue.write_text("must not be packaged\n", encoding="utf-8")
    first, checksum, notes = build_release(repo_copy, "python-best-practices", draft=True)
    first_bytes = first.read_bytes()
    assert first.name == "python-best-practices-v1.0.0-draft.zip"
    assert "DRAFT REHEARSAL" in notes.read_text(encoding="utf-8")
    assert checksum.read_text(encoding="utf-8").startswith(hashlib.sha256(first_bytes).hexdigest())
    second, _, _ = build_release(repo_copy, "python-best-practices", draft=True)
    assert second.read_bytes() == first_bytes
    with zipfile.ZipFile(second) as archive:
        assert all("rogue-secret.txt" not in name for name in archive.namelist())


def test_formal_release_rejects_release_candidate_placeholders(repo_copy: Path) -> None:
    with pytest.raises(SkillpackError, match="finalize the changelog"):
        build_release(repo_copy, "python-best-practices", reports=[])


def test_formal_release_accepts_external_complete_evidence_without_path_leak(
    repo_copy: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pack = get_pack(repo_copy, "python-best-practices")
    (pack.path / "CHANGELOG.md").write_text(
        "# Changelog\n\n## [1.0.0]\n\n- Initial stable release.\n",
        encoding="utf-8",
    )
    for skill in pack.skills:
        skill_file = pack.path / "skills" / skill / "SKILL.md"
        skill_file.write_text(
            skill_file.read_text(encoding="utf-8").replace(
                'maturity: "release-candidate"', 'maturity: "stable"'
            ),
            encoding="utf-8",
        )
    readme = pack.path / "README.md"
    readme.write_text(
        readme.read_text(encoding="utf-8")
        .replace(
            "This pack is an unpublished release candidate.",
            "This pack is prepared for an independently versioned release.",
        )
        .replace("Release-candidate manifest version:", "Manifest version:")
        .replace("Expected release tag (not yet created):", "Release tag:")
        .replace(
            "No public installation or native-client/model compatibility is claimed yet.",
            "Validated compatibility reports are attached to the release.",
        ),
        encoding="utf-8",
    )
    apply_generated_files(repo_copy)
    source_sha = "d" * 40
    reports: list[Path] = []
    for client in ("claude-code", "codex", "opencode"):
        path = tmp_path / f"{client}.json"
        path.write_text(
            json.dumps(
                _compatibility_report(repo_copy, "python-best-practices", source_sha, client)
            ),
            encoding="utf-8",
        )
        reports.append(path)
    monkeypatch.setattr(
        release_module,
        "_require_publishable_git_state",
        lambda _root, _pack, _files: source_sha,
    )
    archive, _, notes = build_release(repo_copy, "python-best-practices", reports=reports)
    assert archive.name == "python-best-practices-v1.0.0.zip"
    note_text = notes.read_text(encoding="utf-8")
    assert "PUBLISHABLE RELEASE" in note_text
    assert str(tmp_path) not in note_text
    assert "`codex`: `codex.json`" in note_text


def test_publishable_git_gate_verifies_signed_annotated_tag(
    repo_copy: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pack = get_pack(repo_copy, "python-best-practices")
    source_sha = "e" * 40
    calls: list[tuple[str, ...]] = []

    def fake_git(_root: Path, *args: str) -> str:
        calls.append(args)
        if args == ("rev-parse", "HEAD") or args[:2] == ("rev-list", "-n"):
            return source_sha
        if args[:2] == ("status", "--porcelain"):
            return ""
        if args[:2] == ("cat-file", "-t"):
            return "tag"
        if args[0] == "verify-tag":
            return ""
        raise AssertionError(args)

    monkeypatch.setattr(release_module, "_git", fake_git)
    monkeypatch.setattr(
        release_module.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args, 0),
    )
    result = release_module._require_publishable_git_state(
        repo_copy,
        pack,
        [
            (
                pack.path / "skillpack.yaml",
                f"{pack.relative_path}/skillpack.yaml",
                (pack.path / "skillpack.yaml").lstat(),
            )
        ],
    )
    assert result == source_sha
    assert ("verify-tag", pack.tag) in calls


def test_unpublished_installer_allows_safe_dry_run_and_codex_update_is_single(
    repo_copy: Path,
) -> None:
    apply_generated_files(repo_copy)
    installer = repo_copy / "dist/install/python-best-practices.sh"
    bash = shutil.which("bash")
    assert bash is not None
    empty_path = repo_copy.parent / "empty-path"
    empty_path.mkdir()
    dry_run_environment = os.environ.copy()
    dry_run_environment["PATH"] = str(empty_path)
    result = subprocess.run(
        [bash, str(installer), "--dry-run"],
        check=True,
        env=dry_run_environment,
        text=True,
        capture_output=True,
    )
    assert "gh skill install" in result.stdout
    invalid = subprocess.run(
        ["bash", str(installer), "--pin", "not-a-sha"],
        check=False,
        text=True,
        capture_output=True,
    )
    assert invalid.returncode == 2
    assert "40-character" in invalid.stderr
    readme = (repo_copy / "packs/python/best-practices/README.md").read_text(encoding="utf-8")
    assert readme.count("codex plugin marketplace upgrade") == 0
    assert "bash dist/install/python-best-practices.sh --dry-run" in readme
    assert "FULL_COMMIT_SHA" not in readme

    _write_manifest(
        repo_copy,
        "python-best-practices",
        lambda data: data.__setitem__("source-sha", "c" * 40),
    )
    apply_generated_files(repo_copy)
    readme = (repo_copy / "packs/python/best-practices/README.md").read_text(encoding="utf-8")
    assert readme.count("codex plugin marketplace upgrade") == 1


def test_bash_installer_probes_preview_commands_and_scopes_gh_environment(
    repo_copy: Path,
) -> None:
    if os.name == "nt":
        pytest.skip("generated Bash installer is exercised on Unix-like runners")
    bash = shutil.which("bash")
    assert bash is not None
    apply_generated_files(repo_copy)
    installer = repo_copy / "dist/install/python-best-practices.sh"
    pin = "a" * 40
    arguments = [bash, str(installer), "--pin", pin]

    empty_path = repo_copy.parent / "missing-gh"
    empty_path.mkdir()
    missing_environment = os.environ.copy()
    missing_environment["PATH"] = str(empty_path)
    missing = subprocess.run(
        arguments,
        check=False,
        env=missing_environment,
        text=True,
        capture_output=True,
    )
    assert missing.returncode == 127
    assert "not installed" in missing.stderr

    fake_bin = repo_copy.parent / "fake-gh-bin"
    _write_fake_gh(fake_bin)
    log = repo_copy.parent / "fake-gh.log"
    environment = os.environ.copy()
    environment.update(
        {
            "PATH": str(fake_bin),
            "GH_FAKE_LOG": str(log),
            "GH_TELEMETRY": "inherited-telemetry",
            "GH_PROMPT_DISABLED": "inherited-prompt",
            "GH_NO_UPDATE_NOTIFIER": "inherited-notifier",
        }
    )

    environment["GH_FAKE_MODE"] = "group-unsupported"
    unsupported_group = subprocess.run(
        arguments,
        check=False,
        env=environment,
        text=True,
        capture_output=True,
    )
    assert unsupported_group.returncode == 1
    assert "does not support the public-preview 'gh skill' command" in unsupported_group.stderr
    assert log.read_text(encoding="utf-8").splitlines() == ["false|1|1|skill --help"]

    log.write_text("", encoding="utf-8")
    environment["GH_FAKE_MODE"] = "install-unsupported"
    unsupported_install = subprocess.run(
        arguments,
        check=False,
        env=environment,
        text=True,
        capture_output=True,
    )
    assert unsupported_install.returncode == 1
    assert "does not support the public-preview 'gh skill install'" in unsupported_install.stderr
    assert log.read_text(encoding="utf-8").splitlines() == [
        "false|1|1|skill --help",
        "false|1|1|skill install --help",
    ]

    log.write_text("", encoding="utf-8")
    environment["GH_FAKE_MODE"] = "supported"
    supported = subprocess.run(
        arguments,
        check=False,
        env=environment,
        text=True,
        capture_output=True,
    )
    assert supported.returncode == 0, supported.stderr
    pack = get_pack(repo_copy, "python-best-practices")
    expected = [
        "false|1|1|skill --help",
        "false|1|1|skill install --help",
        *[
            (
                "false|1|1|skill install genaptic/skillsets "
                f"packs/python/best-practices/skills/{skill} --agent opencode "
                f"--scope user --pin {pin}"
            )
            for skill in pack.skills
        ],
    ]
    assert log.read_text(encoding="utf-8").splitlines() == expected


def test_powershell_installer_has_distinct_preflight_and_restores_environment_when_available(
    repo_copy: Path,
) -> None:
    apply_generated_files(repo_copy)
    installer = repo_copy / "dist/install/python-best-practices.ps1"
    script = installer.read_text(encoding="utf-8")
    assert "Get-Command gh -CommandType Application" in script
    assert '"GH_TELEMETRY" = "false"' in script
    assert '"GH_PROMPT_DISABLED" = "1"' in script
    assert '"GH_NO_UPDATE_NOTIFIER" = "1"' in script
    assert "$PSNativeCommandUseErrorActionPreference = $false" in script
    assert '& $GhCommand.Source "skill" "--help"' in script
    assert '& $GhCommand.Source "skill" "install" "--help"' in script
    assert "exit 127" in script
    assert "} finally {" in script

    powershell = shutil.which("pwsh")
    if powershell is None:
        return

    pin = "b" * 40
    empty_path = repo_copy.parent / "powershell-missing-gh"
    empty_path.mkdir()
    missing_environment = os.environ.copy()
    missing_environment["PATH"] = str(empty_path)
    missing = subprocess.run(
        [powershell, "-NoProfile", "-NonInteractive", "-File", str(installer), "-Pin", pin],
        check=False,
        env=missing_environment,
        text=True,
        capture_output=True,
    )
    assert missing.returncode == 127
    assert "not installed" in _normalized_process_output(missing)

    fake_bin = repo_copy.parent / "powershell-fake-gh-bin"
    _write_fake_gh(fake_bin)
    log = repo_copy.parent / "powershell-fake-gh.log"
    environment = os.environ.copy()
    environment.update(
        {
            "PATH": str(fake_bin),
            "GH_FAKE_LOG": str(log),
            "GH_FAKE_MODE": "group-unsupported",
        }
    )
    unsupported = subprocess.run(
        [powershell, "-NoProfile", "-NonInteractive", "-File", str(installer), "-Pin", pin],
        check=False,
        env=environment,
        text=True,
        capture_output=True,
    )
    assert unsupported.returncode == 1
    assert "does not support the public-preview 'gh skill' command" in (
        _normalized_process_output(unsupported)
    )

    log.write_text("", encoding="utf-8")
    environment["GH_FAKE_MODE"] = "install-unsupported"
    unsupported_install = subprocess.run(
        [powershell, "-NoProfile", "-NonInteractive", "-File", str(installer), "-Pin", pin],
        check=False,
        env=environment,
        text=True,
        capture_output=True,
    )
    assert unsupported_install.returncode == 1
    assert "does not support the public-preview 'gh skill install' command" in (
        _normalized_process_output(unsupported_install)
    )
    assert log.read_text(encoding="utf-8").splitlines() == [
        "false|1|1|skill --help",
        "false|1|1|skill install --help",
    ]

    log.write_text("", encoding="utf-8")
    environment["GH_FAKE_MODE"] = "supported"
    harness = repo_copy.parent / "invoke-installer.ps1"
    escaped_installer = str(installer).replace("'", "''")
    harness.write_text(
        f"""$env:GH_TELEMETRY = 'inherited-telemetry'
$env:GH_PROMPT_DISABLED = 'inherited-prompt'
Remove-Item -LiteralPath 'Env:GH_NO_UPDATE_NOTIFIER' -ErrorAction SilentlyContinue
& '{escaped_installer}' -Pin '{pin}'
if ($env:GH_TELEMETRY -ne 'inherited-telemetry') {{ exit 90 }}
if ($env:GH_PROMPT_DISABLED -ne 'inherited-prompt') {{ exit 91 }}
if (Test-Path -LiteralPath 'Env:GH_NO_UPDATE_NOTIFIER') {{ exit 92 }}
""",
        encoding="utf-8",
    )
    supported = subprocess.run(
        [powershell, "-NoProfile", "-NonInteractive", "-File", str(harness)],
        check=False,
        env=environment,
        text=True,
        capture_output=True,
    )
    assert supported.returncode == 0, supported.stdout + supported.stderr
    pack = get_pack(repo_copy, "python-best-practices")
    expected = [
        "false|1|1|skill --help",
        "false|1|1|skill install --help",
        *[
            (
                "false|1|1|skill install genaptic/skillsets "
                f"packs/python/best-practices/skills/{skill} --agent opencode "
                f"--scope user --pin {pin}"
            )
            for skill in pack.skills
        ],
    ]
    assert log.read_text(encoding="utf-8").splitlines() == expected
