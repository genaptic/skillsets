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
from html import escape as html_escape
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator

from skillpack_tools import release as release_module
from skillpack_tools.configure import configure_repository
from skillpack_tools.evals import (
    eval_report,
    run_structural_evals,
    validate_routing_boundaries,
)
from skillpack_tools.evidence import build_evidence_envelope
from skillpack_tools.generate import apply_generated_files, build_generated_files
from skillpack_tools.models import discover_packs, get_pack, load_repository
from skillpack_tools.release import build_release
from skillpack_tools.signing import VerifiedTag
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
    plain = re.sub(r"\s+\|\s+", " ", plain)
    return " ".join(plain.split())


def test_process_output_normalization_removes_ansi_and_diagnostic_wrapping() -> None:
    completed = subprocess.CompletedProcess(
        args=["pwsh"],
        returncode=1,
        stdout="",
        stderr=("\x1b[31;1mInstalled CLI does not support 'gh skill'\x1b[0m\n    | command.\n"),
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
if /I "%GH_FAKE_MODE%"=="group-unsupported" if /I "%~1:%~2"=="skill:--help" exit /b 1
if /I "%~1:%~2"=="skill:--help" exit /b 0
if /I "%GH_FAKE_MODE%"=="install-unsupported" if /I "%~1:%~2:%~3"=="skill:install:--help" exit /b 1
if /I "%~1:%~2:%~3"=="skill:install:--help" exit /b 0
if /I "%~1:%~2"=="skill:install" exit /b 0
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
    boundary_errors, boundaries = validate_routing_boundaries(root)
    assert boundary_errors == []
    pack_skills = set(pack.skills)
    skill_owners = {
        skill: candidate.id for candidate in discover_packs(root) for skill in candidate.skills
    }
    boundary_cases = [
        {
            "boundaryId": boundary.id,
            "caseId": case["id"],
            "scope": (
                "internal-pack"
                if len({skill_owners[skill] for skill in boundary.skills}) == 1
                else "cross-pack"
            ),
            "boundarySkills": list(boundary.skills),
            "installedPacks": sorted({skill_owners[skill] for skill in boundary.skills}),
            "expectedSkills": case["expectedSkills"],
            "observedSkills": case["expectedSkills"],
            "passed": True,
            "notes": "",
        }
        for boundary in boundaries
        if set(boundary.skills) & pack_skills
        for case in boundary.cases
    ]
    return {
        "schemaVersion": 2,
        "testedAt": "2026-07-18T00:00:00Z",
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
        "cases": {
            "routing": routing,
            "behavior": behavior,
            "boundaries": boundary_cases,
        },
        "effects": {"network": [], "filesystem": ["temporary client home"]},
        "reviewer": {"github": "jecsand838", "githubId": 170039284, "verdict": "passed"},
        "verdict": {"status": "passed", "notes": "All declared cases passed."},
    }


def _write_evidence_bundle(
    root: Path,
    report_path: Path,
    report: dict,
    *,
    run_id: int,
) -> None:
    report_path.write_text(json.dumps(report), encoding="utf-8")
    client = report["client"]["name"]
    envelope = build_evidence_envelope(
        repository_id=1,
        repository_slug=load_repository(root).slug,
        run_id=run_id,
        run_attempt=1,
        workflow_ref=(
            f"{load_repository(root).slug}/.github/workflows/native-compatibility.yml@refs/heads/main"
        ),
        workflow_sha="f" * 40,
        event="workflow_dispatch",
        actor="jecsand838",
        actor_id=170039284,
        triggering_actor="jecsand838",
        source_sha=report["pack"]["sourceSha"],
        evidence_sha="e" * 40,
        report_repository_path=f"compatibility/reports/{client}.json",
        report_sha256=hashlib.sha256(report_path.read_bytes()).hexdigest(),
        client=client,
        pack_id=report["pack"]["id"],
        tested_at=report["testedAt"],
    )
    report_path.with_name(f"{client}.envelope.json").write_text(
        json.dumps(envelope), encoding="utf-8"
    )
    report_path.with_name(f"{client}.attestation.jsonl").write_text(
        '{"dsseEnvelope": {}}\n', encoding="utf-8"
    )
    report_path.with_name(f"{client}.artifact.json").write_text(
        json.dumps(
            {
                "ingestionRunId": run_id,
                "ingestionArtifactId": run_id + 100,
                "ingestionArtifactDigest": "sha256:" + "a" * 64,
            }
        ),
        encoding="utf-8",
    )


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
    output = "dist/dev/opencode/python/best-practices/python-project-layout/assets/fixture.bin"
    assert generated[output] == binary.read_bytes()
    assert all(".env.secret" not in path and not path.endswith(".pyc") for path in generated)
    assert any(path.endswith("/.env.example") for path in generated)
    assert all(not path.endswith((".pem", "/id_ed25519")) for path in generated)
    assert all("/.cache/" not in path for path in generated)
    helper = (
        "dist/dev/opencode/python/best-practices/python-project-layout/scripts/inspect_layout.py"
    )
    assert generated.modes[helper] == 0o755
    assert (
        generated.modes[
            "dist/dev/opencode/python/best-practices/python-project-layout/assets/fixture-tool"
        ]
        == 0o755
    )
    assert (
        generated.modes[
            "dist/dev/opencode/python/best-practices/python-project-layout/scripts/data.json"
        ]
        == 0o644
    )

    apply_generated_files(repo_copy)
    assert (repo_copy / output).read_bytes() == binary.read_bytes()
    if os.name != "nt":
        assert (repo_copy / helper).stat().st_mode & 0o777 == 0o755

    stale_claude = pack.path / ".claude-plugin" / "plugin.json"
    stale_installer = repo_copy / "dist" / "dev" / "install" / f"{pack.id}.sh"

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


def test_legacy_source_sha_has_no_publication_authority(repo_copy: Path) -> None:
    local = build_generated_files(repo_copy)
    claude = json.loads(local[".claude-plugin/marketplace.json"])
    assert claude["plugins"] == []
    catalog = json.loads(local["catalog.json"])
    assert catalog["packs"] == []
    development = json.loads(local["dist/dev/catalog.json"])
    pack = next(item for item in development["packs"] if item["id"] == "python-best-practices")
    assert pack["publication"] == {
        "state": "unpublished",
        "visibility": "public",
        "maturity": "release-candidate",
        "sourceType": "repo-local",
    }

    source_sha = "a" * 40
    _write_manifest(
        repo_copy,
        "python-best-practices",
        lambda data: data.__setitem__("source-sha", source_sha),
    )
    still_unpublished = build_generated_files(repo_copy)
    assert json.loads(still_unpublished[".claude-plugin/marketplace.json"])["plugins"] == []
    assert json.loads(still_unpublished["catalog.json"])["packs"] == []
    schema = json.loads((repo_copy / "schemas/skillpack.schema.json").read_text())
    raw = load_yaml(get_pack(repo_copy, "python-best-practices").path / "skillpack.yaml")
    assert list(Draft202012Validator(schema).iter_errors(raw))


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
    catalog = json.loads(generated["dist/dev/catalog.json"])
    assert list(Draft202012Validator(catalog_schema).iter_errors(catalog)) == []
    catalog["packs"][0]["version"] = "1.0.0junk"
    assert list(Draft202012Validator(catalog_schema).iter_errors(catalog))

    eval_schema = json.loads((repo_copy / "schemas/eval-report.schema.json").read_text())
    report = eval_report(run_structural_evals(repo_copy, skill_filter="python-project-layout"))
    assert list(Draft202012Validator(eval_schema).iter_errors(report)) == []
    del report["skills"][0]["routing"][0]["prompt"]
    assert list(Draft202012Validator(eval_schema).iter_errors(report))


def test_pages_index_is_deterministic_relative_and_manifested(repo_copy: Path) -> None:
    generated = build_generated_files(repo_copy)
    repeated = build_generated_files(repo_copy)
    page = generated["dist/public/index.html"]

    assert isinstance(page, str)
    assert page == repeated["dist/public/index.html"]
    assert re.search(r"<(?:script|link)\b", page, re.IGNORECASE) is None
    assert (
        re.search(
            r"\b(?:src|href)\s*=\s*[\"'](?:https?:)?//",
            page,
            re.IGNORECASE,
        )
        is None
    )

    config = load_repository(repo_copy)
    assert html_escape(config.project_name) in page
    assert html_escape(config.project_description) in page
    assert html_escape(config.slug) in page
    assert html_escape(config.marketplace_name) in page

    assert page.count('<article class="pack">') == 0
    assert "No stable releases are currently published" in page
    for pack in discover_packs(repo_copy):
        assert html_escape(pack.id) not in page

    manifest = json.loads(generated["dist/generated-files.json"])
    entry = next(item for item in manifest["files"] if item["path"] == "dist/public/index.html")
    page_bytes = page.encode("utf-8")
    assert entry == {
        "path": "dist/public/index.html",
        "sha256": hashlib.sha256(page_bytes).hexdigest(),
        "size": len(page_bytes),
        "mode": "0644",
    }


def test_pages_index_escapes_repository_and_pack_metadata(repo_copy: Path) -> None:
    repository_path = repo_copy / "repository.yaml"
    repository = load_yaml(repository_path)
    repository["project"]["name"] = 'Skillsets <script>alert("project")</script> & more'
    repository["project"]["description"] = '<img src="x" onerror="project"> & safe'
    repository["repository"]["owner"] = "genaptic&friends"
    repository["marketplace"]["name"] = 'market<place>&"safe"'
    repository_path.write_text(dump_yaml(repository), encoding="utf-8")

    display_name = '<img src="x" onerror="pack">'
    description = 'Use <strong>care</strong> & "quotes".'
    target = 'target<script>alert("target")</script>'

    def inject_markup(data: dict) -> None:
        data["display-name"] = display_name
        data["description"] = description
        data["targets"].append(target)

    _write_manifest(repo_copy, "python-best-practices", inject_markup)
    page = build_generated_files(repo_copy)["dist/public/index.html"]

    for value in (
        repository["project"]["name"],
        repository["project"]["description"],
        "genaptic&friends/skillsets",
        repository["marketplace"]["name"],
    ):
        assert html_escape(value) in page
    for unpublished in (display_name, description, target):
        assert html_escape(unpublished) not in page
    assert "<script>" not in page
    assert "<img " not in page
    assert "No stable releases are currently published" in page


def test_eval_export_contains_complete_prompts_and_expectations() -> None:
    report = eval_report(run_structural_evals(ROOT, skill_filter="python-project-layout"))
    skill = report["skills"][0]
    assert skill["routingCases"] == len(skill["routing"]) == 6
    assert skill["behaviorCases"] == len(skill["behavior"]) == 2
    assert all({"prompt", "shouldTrigger", "reason"} <= set(case) for case in skill["routing"])
    assert all({"prompt", "assertions", "forbidden"} <= set(case) for case in skill["behavior"])
    assert report["totals"]["routingBoundaries"] == 1
    assert report["totals"]["boundaryCases"] == 4
    assert [case["outcome"] for case in report["routingBoundaries"][0]["cases"]] == [
        "a-only",
        "b-only",
        "both",
        "neither",
    ]


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
    boundary_cases = data["cases"]["boundaries"]
    assert len(boundary_cases) == 12
    assert {case["boundaryId"] for case in boundary_cases} == {
        "python-cli-error-output-vs-python-error-handling",
        "python-cli-testing-vs-python-testing-strategy",
        "python-project-layout-vs-python-testing-strategy",
    }
    cross_pack = [case for case in boundary_cases if case["scope"] == "cross-pack"]
    assert len(cross_pack) == 8
    assert all(len(case["boundarySkills"]) == 2 for case in cross_pack)
    assert all(
        case["installedPacks"] == ["python-best-practices", "python-cli-apps"]
        for case in cross_pack
    )

    omitted_cross_pack = deepcopy(data)
    omitted_cross_pack["cases"]["boundaries"] = [
        case
        for case in omitted_cross_pack["cases"]["boundaries"]
        if case["scope"] == "internal-pack"
    ]
    path.write_text(json.dumps(omitted_cross_pack), encoding="utf-8")
    errors, _ = validate_compatibility_report(
        repo_copy,
        path,
        pack=get_pack(repo_copy, "python-best-practices"),
        source_sha=source_sha,
    )
    assert "every canonical boundary incident" in "\n".join(errors)
    errors, _ = validate_compatibility_report(repo_copy, path, source_sha=source_sha)
    assert "every canonical boundary incident" in "\n".join(errors)

    misdeclared_cross_pack = deepcopy(data)
    misdeclared_cross_pack["cases"]["boundaries"][0]["scope"] = "internal-pack"
    path.write_text(json.dumps(misdeclared_cross_pack), encoding="utf-8")
    errors, _ = validate_compatibility_report(
        repo_copy,
        path,
        pack=get_pack(repo_copy, "python-best-practices"),
        source_sha=source_sha,
    )
    combined = "\n".join(errors)
    assert "scope must be 'cross-pack'" in combined
    assert "every canonical boundary incident" in combined

    missing_protocol_field = deepcopy(data)
    missing_protocol_field["cases"]["boundaries"][0].pop("installedPacks")
    path.write_text(json.dumps(missing_protocol_field), encoding="utf-8")
    errors, _ = validate_compatibility_report(
        repo_copy,
        path,
        pack=get_pack(repo_copy, "python-best-practices"),
        source_sha=source_sha,
    )
    assert "'installedPacks' is a required property" in "\n".join(errors)

    mismatched_boundary = deepcopy(data)
    mismatched_boundary["cases"]["boundaries"][0]["observedSkills"] = []
    path.write_text(json.dumps(mismatched_boundary), encoding="utf-8")
    errors, _ = validate_compatibility_report(
        repo_copy,
        path,
        pack=get_pack(repo_copy, "python-best-practices"),
        source_sha=source_sha,
    )
    assert "passed must equal the observed/expected selection" in "\n".join(errors)

    path.write_text('{"schemaVersion":1}', encoding="utf-8")
    errors, _ = validate_compatibility_report(repo_copy, path)
    assert "schemaVersion 1 is unsupported" in "\n".join(errors)

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
    future["testedAt"] = "2999-01-01T00:00:00Z"
    path.write_text(json.dumps(future), encoding="utf-8")
    errors, _ = validate_compatibility_report(
        repo_copy,
        path,
        pack=get_pack(repo_copy, "python-best-practices"),
        source_sha=source_sha,
    )
    assert "minutes in the future" in "\n".join(errors)


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
        "maintainer_github_id": 123456,
        "trusted_ssh_fingerprint": "SHA256:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
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
    assert '          DEFAULT_BRANCH: "trunk"\n' in native
    release = (repo_copy / ".github/workflows/release.yml").read_text(encoding="utf-8")
    assert '          DEFAULT_BRANCH: "trunk"\n' in release


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
        assert f'          DEFAULT_BRANCH: "{branch}"\n' in native
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
        "SECURITY.md",
        "schemas/repository.schema.json",
    ):
        text = (repo_copy / relative).read_text(encoding="utf-8")
        assert expected_slug in text
        assert duplicated_slug not in text

    assert configure_repository(repo_copy, repository="skillsets-next") == []


def test_release_workflow_protects_and_binds_the_neutral_verified_source(repo_copy: Path) -> None:
    workflow = (repo_copy / ".github/workflows/release.yml").read_text(encoding="utf-8")
    source_job = workflow.split("  source:\n", 1)[1].split("\n  rust-assets:\n", 1)[0]
    rust_job = workflow.split("  rust-assets:\n", 1)[1].split("\n  release-gates:\n", 1)[0]
    gate_job = workflow.split("  release-gates:\n", 1)[1].split("\n  release-build:\n", 1)[0]
    release_build_job = workflow.split("  release-build:\n", 1)[1].split("\n  release:\n", 1)[0]
    release_job = workflow.split("\n  release:\n", 1)[1]

    assert "    environment: release\n" not in source_job
    assert "    environment: release\n" not in rust_job
    assert "    environment: release\n" in release_job
    assert "      source_sha: ${{ steps.gate-policy.outputs.source_sha }}\n" in source_job
    signal = "      - name: Verify GitHub's signed-tag signal before running tagged repository code"
    signer = "      - name: Enforce the protected-main signer allowlist"
    policy = "      - name: Validate the selected lifecycle and release-gate policy"
    assert source_job.index(signal) < source_job.index(signer) < source_job.index(policy)
    assert "GH_TOKEN: ${{ github.token }}" in source_job
    assert "git/tags/$tag_object" in source_job
    assert "'.verification.verified'" in source_job
    assert "validate_pack_lifecycle(pack)" in source_job
    assert 'pack.visibility != "public"' in source_job
    assert 'pack.maturity != "stable"' in source_job

    verified_sha = "${{ needs.source.outputs.source_sha }}"
    assert f"          ref: {verified_sha}\n" in rust_job
    assert '--pack "$PACK_ID"' in rust_job
    assert "    if: needs.source.outputs.requires_rust == 'true'\n" in rust_job
    assert "    if: ${{ always() }}\n" in gate_job
    assert 'requires_rust == "true" and rust != "success"' in gate_job
    assert 'requires_rust == "false" and rust != "skipped"' in gate_job

    assert f"          ref: {verified_sha}\n" in release_build_job
    assert f"          VERIFIED_SOURCE_SHA: {verified_sha}\n" in release_build_job
    assert "if head != verified_source:" in release_build_job
    assert "if tagged != head:" in release_build_job
    assert "Verify GitHub's signed-tag attestation" in release_build_job

    # The write-capable publisher consumes the sealed read-only build. It may inspect the
    # tag as inert data, but all Python policy code comes from protected main.
    assert "      - release-build\n" in release_job
    assert "Check out protected publication policy without credentials" in release_job
    assert "Check out the exact tag as inert release data" in release_job
    assert "Download and digest-verify the exact release-build artifact" in release_job
    assert "EXPECTED_ARTIFACT_DIGEST: ${{ needs.release-build.outputs.artifact_digest }}" in (
        release_job
    )
    assert 'export PYTHONPATH="$POLICY_ROOT/src"' in release_job
    assert "working-directory: release-source" not in release_job


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
        metadata_name = "python-best-practices-v1.0.0-draft/RELEASE-METADATA.json"
        assert archive.namelist().count(metadata_name) == 1
        metadata = json.loads(archive.read(metadata_name))
        assert metadata["mode"] == "draft-rehearsal"
        assert metadata["pack"]["sourceSha"] is None
        assert metadata["tagSignature"] is None
        assert metadata["compatibilityEvidence"] == {"required": False, "reports": []}
        info = archive.getinfo(metadata_name)
        assert info.date_time == (1980, 1, 1, 0, 0, 0)
        assert (info.external_attr >> 16) & 0o777 == 0o644
    assert "Source SHA: `not available (draft rehearsal)`" in notes.read_text(encoding="utf-8")


def test_clean_git_draft_release_still_has_no_source_commit(repo_copy: Path) -> None:
    subprocess.run(["git", "init", "-q", str(repo_copy)], check=True)
    subprocess.run(["git", "-C", str(repo_copy), "config", "user.name", "Fixture"], check=True)
    subprocess.run(
        ["git", "-C", str(repo_copy), "config", "user.email", "fixture@example.invalid"],
        check=True,
    )
    subprocess.run(["git", "-C", str(repo_copy), "add", "-A"], check=True)
    subprocess.run(
        ["git", "-C", str(repo_copy), "commit", "-q", "-m", "clean fixture"],
        check=True,
    )
    archive, _checksum, notes = build_release(
        repo_copy,
        "python-best-practices",
        draft=True,
    )
    assert (
        len(
            subprocess.check_output(
                ["git", "-C", str(repo_copy), "rev-parse", "HEAD"], text=True
            ).strip()
        )
        == 40
    )
    with zipfile.ZipFile(archive) as bundle:
        metadata = json.loads(
            bundle.read("python-best-practices-v1.0.0-draft/RELEASE-METADATA.json")
        )
    assert metadata["pack"]["sourceSha"] is None
    assert "not available (draft rehearsal)" in notes.read_text(encoding="utf-8")


def test_formal_release_rejects_release_candidate_placeholders(repo_copy: Path) -> None:
    _write_manifest(
        repo_copy,
        "python-best-practices",
        lambda data: data.__setitem__("maturity", "stable"),
    )
    pack = get_pack(repo_copy, "python-best-practices")
    for skill in pack.skills:
        skill_file = pack.path / "skills" / skill / "SKILL.md"
        skill_file.write_text(
            skill_file.read_text(encoding="utf-8").replace(
                'maturity: "release-candidate"', 'maturity: "stable"'
            ),
            encoding="utf-8",
        )
    apply_generated_files(repo_copy)
    with pytest.raises(SkillpackError, match="finalize the changelog"):
        build_release(
            repo_copy,
            "python-best-practices",
            reports=[],
            policy_root=repo_copy,
        )


def test_publishable_release_requires_current_policy_root(repo_copy: Path) -> None:
    with pytest.raises(SkillpackError, match="explicit protected policy root"):
        build_release(repo_copy, "python-best-practices", reports=[])
    with pytest.raises(SkillpackError, match="not valid for a draft"):
        build_release(
            repo_copy,
            "python-best-practices",
            draft=True,
            policy_root=repo_copy,
        )


def test_release_evidence_uses_current_policy_over_tag_policy(
    repo_copy: Path,
    tmp_path: Path,
) -> None:
    pack = get_pack(repo_copy, "python-best-practices")
    source_sha = "d" * 40
    reports: list[Path] = []
    for client in ("claude-code", "codex", "opencode"):
        path = tmp_path / f"{client}.json"
        _write_evidence_bundle(
            repo_copy,
            path,
            _compatibility_report(repo_copy, pack.id, source_sha, client),
            run_id=100 + len(reports),
        )
        reports.append(path)

    policy_root = tmp_path / "protected-policy"
    shutil.copytree(repo_copy, policy_root, ignore=_copy_ignore)
    policy_path = policy_root / "repository.yaml"
    policy = load_yaml(policy_path)
    policy["compatibility-evidence"]["authorized-reviewers"] = [
        {"github": "replacement-reviewer", "github-id": 999999}
    ]
    policy_path.write_text(dump_yaml(policy), encoding="utf-8")

    with pytest.raises(SkillpackError, match="not authorized"):
        release_module._require_compatibility_evidence(
            repo_copy,
            policy_root,
            pack,
            source_sha,
            reports,
        )


def test_release_evidence_uses_current_freshness_over_tag_policy(
    repo_copy: Path,
    tmp_path: Path,
) -> None:
    pack = get_pack(repo_copy, "python-best-practices")
    source_sha = "d" * 40
    reports: list[Path] = []
    for index, client in enumerate(("claude-code", "codex", "opencode"), start=1):
        path = tmp_path / f"{client}.json"
        report = _compatibility_report(repo_copy, pack.id, source_sha, client)
        report["testedAt"] = "2026-01-01T00:00:00Z"
        _write_evidence_bundle(repo_copy, path, report, run_id=200 + index)
        reports.append(path)

    policy_root = tmp_path / "protected-policy"
    shutil.copytree(repo_copy, policy_root, ignore=_copy_ignore)
    tag_policy_path = repo_copy / "repository.yaml"
    tag_policy = load_yaml(tag_policy_path)
    tag_policy["compatibility-evidence"]["max-age-days"] = 999
    tag_policy_path.write_text(dump_yaml(tag_policy), encoding="utf-8")

    with pytest.raises(SkillpackError, match="older than 45 days"):
        release_module._require_compatibility_evidence(
            repo_copy,
            policy_root,
            pack,
            source_sha,
            reports,
        )


@pytest.mark.parametrize(
    "schema_name",
    ["compatibility-report.schema.json", "compatibility-evidence-envelope.schema.json"],
)
def test_release_evidence_uses_current_schema_over_tag_schema(
    repo_copy: Path,
    tmp_path: Path,
    schema_name: str,
) -> None:
    pack = get_pack(repo_copy, "python-best-practices")
    source_sha = "d" * 40
    reports: list[Path] = []
    for index, client in enumerate(("claude-code", "codex", "opencode"), start=1):
        path = tmp_path / f"{client}.json"
        _write_evidence_bundle(
            repo_copy,
            path,
            _compatibility_report(repo_copy, pack.id, source_sha, client),
            run_id=300 + index,
        )
        reports.append(path)

    policy_root = tmp_path / "protected-policy"
    shutil.copytree(repo_copy, policy_root, ignore=_copy_ignore)
    schema_path = policy_root / "schemas" / schema_name
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    schema["required"].append("protectedPolicyMarker")
    schema_path.write_text(json.dumps(schema), encoding="utf-8")

    with pytest.raises(SkillpackError, match="protectedPolicyMarker"):
        release_module._require_compatibility_evidence(
            repo_copy,
            policy_root,
            pack,
            source_sha,
            reports,
        )


def test_formal_release_accepts_external_complete_evidence_without_path_leak(
    repo_copy: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pack = get_pack(repo_copy, "python-best-practices")
    _write_manifest(
        repo_copy,
        "python-best-practices",
        lambda data: data.__setitem__("maturity", "stable"),
    )
    (pack.path / "CHANGELOG.md").write_text(
        "# Changelog\n\n## [Unreleased]\n\n## [1.0.0] - 2026-07-19\n\n- Initial stable release.\n",
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
        _write_evidence_bundle(
            repo_copy,
            path,
            _compatibility_report(repo_copy, "python-best-practices", source_sha, client),
            run_id=100 + len(reports),
        )
        reports.append(path)
    monkeypatch.setattr(
        release_module,
        "_require_publishable_git_state",
        lambda _root, _policy_root, _pack, _files: VerifiedTag(
            source_sha=source_sha,
            kind="ssh",
            fingerprint="SHA256:RXn4sQSc9mwJb13oQVvUUkQvPw+B5N+WrRWH4elMJHg",
        ),
    )
    archive, _, notes = build_release(
        repo_copy,
        "python-best-practices",
        reports=reports,
        policy_root=repo_copy,
    )
    archive_bytes = archive.read_bytes()
    rebuilt, _, _ = build_release(
        repo_copy,
        "python-best-practices",
        reports=reports,
        policy_root=repo_copy,
    )
    assert rebuilt.read_bytes() == archive_bytes
    assert archive.name == "python-best-practices-v1.0.0.zip"
    note_text = notes.read_text(encoding="utf-8")
    assert "PUBLISHABLE RELEASE" in note_text
    assert str(tmp_path) not in note_text
    assert "`codex`: report `codex.json`" in note_text
    assert "SHA256:RXn4sQSc9mwJb13oQVvUUkQvPw+B5N+WrRWH4elMJHg" in note_text
    with zipfile.ZipFile(archive) as release_zip:
        metadata = json.loads(
            release_zip.read("python-best-practices-v1.0.0/RELEASE-METADATA.json")
        )
        assert metadata["mode"] == "publishable"
        assert metadata["pack"]["sourceSha"] == source_sha
        assert metadata["tagSignature"]["type"] == "ssh"
        assert [item["client"] for item in metadata["compatibilityEvidence"]["reports"]] == [
            "claude-code",
            "codex",
            "opencode",
        ]
        assert all(
            item["ingestionArtifactDigest"].startswith("sha256:")
            for item in metadata["compatibilityEvidence"]["reports"]
        )
        assert "python-best-practices-v1.0.0/schemas/release-metadata.schema.json" in (
            release_zip.namelist()
        )
        assert all("routing-boundaries" not in name for name in release_zip.namelist())


def test_publishable_git_gate_verifies_signed_annotated_tag(
    repo_copy: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pack = get_pack(repo_copy, "python-best-practices")
    source_sha = "e" * 40
    calls: list[tuple[str, ...]] = []
    verified: list[str] = []

    def fake_git(_root: Path, *args: str) -> str:
        calls.append(args)
        if args == ("rev-parse", "HEAD") or args[:2] == ("rev-list", "-n"):
            return source_sha
        if args[:2] == ("status", "--porcelain"):
            return ""
        if args[:2] == ("cat-file", "-t"):
            return "tag"
        raise AssertionError(args)

    monkeypatch.setattr(release_module, "_git", fake_git)
    monkeypatch.setattr(
        release_module,
        "verify_tag",
        lambda _root, tag, _signers: (
            verified.append(tag)
            or VerifiedTag(
                source_sha=source_sha,
                kind="ssh",
                fingerprint="SHA256:RXn4sQSc9mwJb13oQVvUUkQvPw+B5N+WrRWH4elMJHg",
            )
        ),
    )
    monkeypatch.setattr(
        release_module.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args, 0),
    )
    result = release_module._require_publishable_git_state(
        repo_copy,
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
    assert result.source_sha == source_sha
    assert verified == [pack.tag]


def test_unpublished_installer_allows_safe_dry_run_and_codex_update_is_single(
    repo_copy: Path,
) -> None:
    apply_generated_files(repo_copy)
    installer = repo_copy / "dist/dev/install/python-best-practices.sh"
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
    assert "claude plugin marketplace add dist/dev/claude" in readme
    assert "codex plugin marketplace add dist/dev/codex" in readme
    assert "plugin marketplace add .\n" not in readme
    assert "bash dist/dev/install/python-best-practices.sh --dry-run" in readme
    assert "FULL_COMMIT_SHA" not in readme

    assert "dist/public/install/python-best-practices.sh" not in readme


def test_bash_installer_probes_preview_commands_and_scopes_gh_environment(
    repo_copy: Path,
) -> None:
    if os.name == "nt":
        pytest.skip("generated Bash installer is exercised on Unix-like runners")
    bash = shutil.which("bash")
    assert bash is not None
    apply_generated_files(repo_copy)
    installer = repo_copy / "dist/dev/install/python-best-practices.sh"
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
    installer = repo_copy / "dist/dev/install/python-best-practices.ps1"
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
