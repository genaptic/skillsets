from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
import socket
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
SINGLE = (
    ROOT
    / "packs/shared/genaptic-skillsets-development/skills/genaptic-skillsets-create-skill/scripts/scaffold_skill.py"
)
SKILLPACK = (
    ROOT
    / "packs/shared/genaptic-skillsets-development/skills/genaptic-skillsets-create-skillpack/scripts/scaffold_skillpack.py"
)
SINGLE_EXAMPLE = SINGLE.parents[1] / "assets/skill-request.example.json"
SKILLPACK_EXAMPLE = SKILLPACK.parents[1] / "assets/skillpack-request.example.json"


def run_helper(
    script: Path,
    repo: Path,
    request: Path,
    *arguments: str,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-I",
            "-S",
            str(script),
            "--repo",
            str(repo),
            "--request",
            str(request),
            *arguments,
        ],
        cwd=repo,
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )


def make_repo(target: Path) -> Path:
    target.mkdir()
    shutil.copy2(ROOT / "repository.yaml", target / "repository.yaml")
    shutil.copytree(ROOT / "templates", target / "templates")
    pack_target = target / "packs/python/best-practices"
    pack_target.parent.mkdir(parents=True)
    shutil.copytree(ROOT / "packs/python/best-practices", pack_target)
    return target


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    return make_repo(tmp_path / "repo")


def load_helper(script: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    previous = sys.dont_write_bytecode
    try:
        sys.dont_write_bytecode = True
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
    return module


def write_request(repo: Path, source: Path, name: str = "request.json") -> Path:
    path = repo / name
    path.write_bytes(source.read_bytes())
    return path


def preview(
    script: Path, repo: Path, request: Path
) -> tuple[subprocess.CompletedProcess[str], dict]:
    completed = run_helper(script, repo, request, "--json")
    assert completed.returncode == 0, completed.stderr
    return completed, json.loads(completed.stdout)


def test_preview_is_deterministic_relative_redacted_and_lists_templates(repo: Path) -> None:
    request = write_request(repo, SINGLE_EXAMPLE)
    before = {
        path.relative_to(repo).as_posix(): path.stat().st_mtime_ns for path in repo.rglob("*")
    }
    first, plan = preview(SINGLE, repo, request)
    second, repeated = preview(SINGLE, repo, request)
    after = {path.relative_to(repo).as_posix(): path.stat().st_mtime_ns for path in repo.rglob("*")}
    assert first.stdout == second.stdout
    assert plan == repeated
    assert re.fullmatch(r"[0-9a-f]{64}", plan["planDigest"])
    assert plan["repository"] == "."
    assert plan["request"] == "request"
    assert str(repo) not in first.stdout
    assert before == after

    skillpack_request = write_request(repo, SKILLPACK_EXAMPLE, "skillpack.json")
    _, skillpack_plan = preview(SKILLPACK, repo, skillpack_request)
    assert skillpack_plan["operation"] == "genaptic-skillsets-create-skillpack"
    assert skillpack_plan["skillpackName"] == "Go Service Observability"
    assert any(path.endswith("tests/compatibility/smoke.py") for path in skillpack_plan["newFiles"])
    assert str(repo) not in json.dumps(skillpack_plan)
    assert "details" not in skillpack_plan
    assert "scope" not in skillpack_plan
    assert all("details" not in skill for skill in skillpack_plan["skills"])


def test_single_skill_apply_requires_reviewed_digest_and_preserves_interfaces(repo: Path) -> None:
    request = write_request(repo, SINGLE_EXAMPLE)
    _, plan = preview(SINGLE, repo, request)
    missing = run_helper(SINGLE, repo, request, "--apply", "--json")
    assert missing.returncode == 2
    wrong = run_helper(SINGLE, repo, request, "--apply", "--plan-digest", "0" * 64, "--json")
    assert wrong.returncode == 2
    destination = repo / plan["destination"]
    assert not destination.exists()

    applied = run_helper(
        SINGLE,
        repo,
        request,
        "--apply",
        "--plan-digest",
        plan["planDigest"],
        "--json",
    )
    assert applied.returncode == 0, applied.stderr
    assert destination.is_dir()
    request_data = json.loads(request.read_text(encoding="utf-8"))
    interface = (destination / "agents/openai.yaml").read_text(encoding="utf-8")
    assert request_data["openai"]["displayName"] in interface
    assert request_data["openai"]["defaultPrompt"] in interface
    assert request_data["skillName"] in (
        repo / "packs/python/best-practices/skillpack.yaml"
    ).read_text(encoding="utf-8")
    skill_markdown = (destination / "SKILL.md").read_text(encoding="utf-8")
    assert 'version: "1.0.0"' in skill_markdown
    assert 'maturity: "release-candidate"' in skill_markdown
    assert not (repo / ".tmp").exists()


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        (b"{", "invalid JSON"),
        (b'{"schemaVersion":1,"schemaVersion":1}', "duplicate JSON key"),
        (b'{"schemaVersion":NaN}', "non-finite"),
        (b"\xff", "valid UTF-8"),
    ],
)
def test_strict_request_parser_rejects_malformed_input(
    repo: Path, payload: bytes, message: str
) -> None:
    request = repo / "bad.json"
    request.write_bytes(payload)
    completed = run_helper(SINGLE, repo, request, "--json")
    assert completed.returncode == 2
    assert message in completed.stderr
    assert "Traceback" not in completed.stderr


def test_strict_request_parser_rejects_oversize_input(repo: Path) -> None:
    request = repo / "large.json"
    request.write_bytes(b" " * (1024 * 1024 + 1))
    completed = run_helper(SINGLE, repo, request, "--json")
    assert completed.returncode == 2
    assert "exceeds 1048576 bytes" in completed.stderr


def test_symlinked_template_and_request_are_rejected(repo: Path) -> None:
    request = write_request(repo, SINGLE_EXAMPLE)
    link = repo / "templates/skill/references/symlink.md"
    try:
        os.symlink(repo / "repository.yaml", link)
    except OSError:
        pytest.skip("symlinks unavailable")
    completed = run_helper(SINGLE, repo, request, "--json")
    assert completed.returncode == 2
    assert "symlink" in completed.stderr
    link.unlink()
    request_link = repo / "request-link.json"
    os.symlink(request, request_link)
    completed = run_helper(SINGLE, repo, request_link, "--json")
    assert completed.returncode == 2
    assert "symlink" in completed.stderr


def test_stale_digest_refuses_apply_without_destination(repo: Path) -> None:
    request = write_request(repo, SINGLE_EXAMPLE)
    _, plan = preview(SINGLE, repo, request)
    checklist = repo / "templates/skill/references/checklist.md"
    checklist.write_text(checklist.read_text(encoding="utf-8") + "\nChanged.\n", encoding="utf-8")
    completed = run_helper(
        SINGLE,
        repo,
        request,
        "--apply",
        "--plan-digest",
        plan["planDigest"],
        "--json",
    )
    assert completed.returncode == 2
    assert "stale" in completed.stderr
    assert not (repo / plan["destination"]).exists()


def one_skill_request(repo: Path) -> Path:
    data = json.loads(SKILLPACK_EXAMPLE.read_text(encoding="utf-8"))
    data["skills"] = [data["skills"][0]]
    data["skills"][0]["nearestNeighbor"] = "python-project-layout"
    data["operations"] = data["skills"][0]["operations"]
    skill = data["skills"][0]["name"]
    data["interface"]["starterPrompts"] = [
        data["interface"]["starterPrompts"][0],
        {
            "skill": skill,
            "prompt": (
                f"Use ${skill} to review an existing logging design against its declared "
                "safety contract."
            ),
        },
    ]
    path = repo / "one-skill.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_one_skill_pack_apply_uses_runtime_map_and_unreleased_changelog(repo: Path) -> None:
    request = one_skill_request(repo)
    _, plan = preview(SKILLPACK, repo, request)
    applied = run_helper(
        SKILLPACK,
        repo,
        request,
        "--apply",
        "--plan-digest",
        plan["planDigest"],
        "--json",
    )
    assert applied.returncode == 0, applied.stderr
    destination = repo / plan["destination"]
    manifest = (destination / "skillpack.yaml").read_text(encoding="utf-8")
    changelog = (destination / "CHANGELOG.md").read_text(encoding="utf-8")
    readme = (destination / "README.md").read_text(encoding="utf-8")
    assert "schema-version: 2" in manifest
    assert "maturity: release-candidate" in manifest
    assert "distribution:\n  visibility: public" in manifest
    assert "publication:\n  state: unpublished" in manifest
    assert "release-gates:\n- native-evidence\n- deterministic-archive" in manifest
    assert "interface:\n  short-description:" in manifest
    assert "compatibility:\n  runtimes:" in manifest
    assert "## [Unreleased]" in changelog
    assert "<!-- BEGIN RELEASE PREPARATION NOTE -->" in changelog
    assert "<!-- END RELEASE PREPARATION NOTE -->" in changelog
    assert not re.search(r"## \[\d+\.\d+\.\d+\]", changelog)
    assert "Maturity: `release-candidate`" in readme
    assert "Publication state:\n`unpublished`" in readme
    assert f"{plan['packId']}-v{plan['version']}" in readme
    skill_markdown = next((destination / "skills").glob("*/SKILL.md")).read_text(encoding="utf-8")
    assert 'version: "1.0.0"' in skill_markdown
    assert 'maturity: "release-candidate"' in skill_markdown
    assert (destination / "tests/compatibility/smoke.py").stat().st_mode & 0o111
    assert not (repo / ".tmp").exists()


def test_skillpack_requires_exact_aggregate_operations(repo: Path) -> None:
    request = one_skill_request(repo)
    data = json.loads(request.read_text(encoding="utf-8"))
    data["operations"]["network"] = "required"
    request.write_text(json.dumps(data), encoding="utf-8")
    completed = run_helper(SKILLPACK, repo, request, "--json")
    assert completed.returncode == 2
    assert "component-wise maximum" in completed.stderr


def test_helpers_are_standalone_offline_and_executable() -> None:
    for script in (SINGLE, SKILLPACK):
        source = script.read_text(encoding="utf-8")
        assert "import subprocess" not in source
        assert "urllib.request" not in source
        assert "requests" not in source
        assert script.stat().st_mode & 0o111
        help_result = subprocess.run(
            [sys.executable, "-I", "-S", str(script), "--help"],
            text=True,
            capture_output=True,
            check=False,
        )
        assert help_result.returncode == 0
        help_text = " ".join(help_result.stdout.split())
        assert "Python 3.11" in help_text
        assert "network" in help_text
        assert "stdout" in help_text


@pytest.mark.parametrize("boundary", ["destination", "manifest", "inventory"])
def test_single_skill_failure_boundaries_roll_back_safely(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, boundary: str
) -> None:
    repo = make_repo(tmp_path / boundary)
    request = write_request(repo, SINGLE_EXAMPLE)
    module = load_helper(SINGLE, f"scaffold_skill_{boundary}")
    plan, _, destination, _, _ = module.build_plan(repo, request)
    digest = module.canonical_digest(plan)
    manifest = repo / "packs/python/best-practices/skillpack.yaml"
    inventory = repo / "packs/python/best-practices/tests/compatibility/expected-skills.json"
    before = (manifest.read_bytes(), inventory.read_bytes())

    if boundary == "destination":
        original_replace = module.os.replace

        def replace_then_fail(source, target):
            original_replace(source, target)
            if Path(target) == destination:
                raise OSError("injected failure after destination move")

        monkeypatch.setattr(module.os, "replace", replace_then_fail)
    else:
        original_atomic = module.atomic_replace
        calls = 0
        fail_at = 1 if boundary == "manifest" else 2

        def write_then_fail(path, content):
            nonlocal calls
            calls += 1
            original_atomic(path, content)
            if calls == fail_at:
                raise OSError(f"injected failure after {boundary} write")

        monkeypatch.setattr(module, "atomic_replace", write_then_fail)

    with pytest.raises(module.ScaffoldError, match="rolled back where safe"):
        module.apply_plan(repo, request, digest)
    assert not destination.exists()
    assert (manifest.read_bytes(), inventory.read_bytes()) == before
    assert not (repo / ".tmp").exists()


def test_single_skill_interruption_rolls_back_and_reports(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = make_repo(tmp_path / "interrupted")
    request = write_request(repo, SINGLE_EXAMPLE)
    module = load_helper(SINGLE, "scaffold_skill_interrupted")
    plan, _, destination, _, _ = module.build_plan(repo, request)
    digest = module.canonical_digest(plan)
    manifest = repo / "packs/python/best-practices/skillpack.yaml"
    inventory = repo / "packs/python/best-practices/tests/compatibility/expected-skills.json"
    before = (manifest.read_bytes(), inventory.read_bytes())
    original_atomic = module.atomic_replace
    calls = 0

    def interrupt_after_manifest(path, content):
        nonlocal calls
        calls += 1
        original_atomic(path, content)
        if calls == 1:
            raise KeyboardInterrupt

    monkeypatch.setattr(module, "atomic_replace", interrupt_after_manifest)
    with pytest.raises(module.ScaffoldError, match="apply interrupted"):
        module.apply_plan(repo, request, digest)
    assert not destination.exists()
    assert (manifest.read_bytes(), inventory.read_bytes()) == before


def test_concurrently_modified_created_destination_is_preserved(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = make_repo(tmp_path / "concurrent")
    request = write_request(repo, SINGLE_EXAMPLE)
    module = load_helper(SINGLE, "scaffold_skill_concurrent")
    plan, _, destination, _, _ = module.build_plan(repo, request)
    digest = module.canonical_digest(plan)
    original_replace = module.os.replace

    def move_modify_then_fail(source, target):
        original_replace(source, target)
        if Path(target) == destination:
            skill = destination / "SKILL.md"
            skill.write_text(
                skill.read_text(encoding="utf-8") + "\nConcurrent edit.\n", encoding="utf-8"
            )
            raise OSError("injected failure after concurrent edit")

    monkeypatch.setattr(module.os, "replace", move_modify_then_fail)
    with pytest.raises(module.ScaffoldError, match="changed concurrently and was preserved"):
        module.apply_plan(repo, request, digest)
    assert destination.is_dir()
    assert "Concurrent edit." in (destination / "SKILL.md").read_text(encoding="utf-8")


@pytest.mark.parametrize("condition", ["source-sha", "no-unreleased", "undeclared-skill"])
def test_single_skill_refuses_unsafe_pack_release_state(tmp_path: Path, condition: str) -> None:
    repo = make_repo(tmp_path / condition)
    request = write_request(repo, SINGLE_EXAMPLE)
    manifest = repo / "packs/python/best-practices/skillpack.yaml"
    if condition == "source-sha":
        text = manifest.read_text(encoding="utf-8").replace(
            "version: 1.0.0\n", f"version: 1.0.0\nsource-sha: {'a' * 40}\n"
        )
        manifest.write_text(text, encoding="utf-8")
        expected = "source-sha"
    elif condition == "no-unreleased":
        changelog = manifest.with_name("CHANGELOG.md")
        changelog.write_text(
            changelog.read_text(encoding="utf-8").replace("## [Unreleased]", "## Draft"),
            encoding="utf-8",
        )
        expected = "no explicit [Unreleased]"
    else:
        (manifest.parent / "skills/undeclared-skill").mkdir()
        expected = "undeclared or missing"
    completed = run_helper(SINGLE, repo, request, "--json")
    assert completed.returncode == 2
    assert expected in completed.stderr


def test_single_skill_allows_only_a_newer_published_development_cycle(repo: Path) -> None:
    request = write_request(repo, SINGLE_EXAMPLE)
    request_data = json.loads(request.read_text(encoding="utf-8"))
    request_data["expectedPackVersion"] = "1.0.1"
    request.write_text(json.dumps(request_data), encoding="utf-8")
    manifest = repo / "packs/python/best-practices/skillpack.yaml"
    data = yaml.safe_load(manifest.read_text(encoding="utf-8"))
    data["version"] = "1.0.1"
    data["maturity"] = "release-candidate"
    data["publication"] = {
        "state": "published",
        "latest-release": {
            "version": "1.0.0",
            "source-sha": "a" * 40,
            "release-id": 123,
            "released-at": "2026-07-19T18:30:00Z",
        },
    }
    manifest.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    inventory = manifest.parent / "tests/compatibility/expected-skills.json"
    inventory_data = json.loads(inventory.read_text(encoding="utf-8"))
    inventory_data["version"] = "1.0.1"
    inventory.write_text(json.dumps(inventory_data), encoding="utf-8")
    completed = run_helper(SINGLE, repo, request, "--json")
    assert completed.returncode == 0, completed.stderr

    data["version"] = "1.0.0"
    data["maturity"] = "stable"
    manifest.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    inventory_data["version"] = "1.0.0"
    inventory.write_text(json.dumps(inventory_data), encoding="utf-8")
    request_data["expectedPackVersion"] = "1.0.0"
    request.write_text(json.dumps(request_data), encoding="utf-8")
    frozen = run_helper(SINGLE, repo, request, "--json")
    assert frozen.returncode == 2
    assert "run begin-development" in frozen.stderr


def test_skillpack_template_declares_complete_manifest_v2_lifecycle() -> None:
    manifest = yaml.safe_load((ROOT / "templates/skillpack/skillpack.yaml").read_text())
    assert manifest["schema-version"] == 2
    assert manifest["maturity"] == "release-candidate"
    assert manifest["distribution"] == {"visibility": "public"}
    assert manifest["publication"] == {"state": "unpublished"}
    assert manifest["release-gates"] == ["native-evidence", "deterministic-archive"]
    assert 25 <= len(manifest["interface"]["short-description"]) <= 120
    assert len(manifest["interface"]["starter-prompts"]) == 2


def test_skillpack_scaffold_assigns_rust_asset_gate(repo: Path) -> None:
    data = json.loads(SKILLPACK_EXAMPLE.read_text(encoding="utf-8"))
    data["language"] = "rust"
    data["packId"] = "rust-service-observability"
    request = repo / "rust-skillpack.json"
    request.write_text(json.dumps(data), encoding="utf-8")
    _, plan = preview(SKILLPACK, repo, request)
    module = load_helper(SKILLPACK, "scaffold_skillpack_rust_gate")
    manifest = yaml.safe_load(module.render_manifest(plan, "fixture-maintainer"))
    assert manifest["release-gates"] == [
        "native-evidence",
        "deterministic-archive",
        "rust-assets",
    ]


@pytest.mark.parametrize("name", ["CON", "__pycache__", "private-key.pem"])
def test_rejected_template_paths_fail_closed(tmp_path: Path, name: str) -> None:
    repo = make_repo(tmp_path / re.sub(r"[^a-z]", "-", name.lower()))
    request = write_request(repo, SINGLE_EXAMPLE)
    path = repo / "templates/skill/references" / name
    if name == "__pycache__":
        path.mkdir()
        (path / "fixture.pyc").write_bytes(b"cache")
    else:
        path.write_text("must be rejected\n", encoding="utf-8")
    completed = run_helper(SINGLE, repo, request, "--json")
    assert completed.returncode == 2
    assert "rejected path" in completed.stderr


def test_direct_planning_never_uses_network_or_subprocess(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    request = write_request(repo, SINGLE_EXAMPLE)
    module = load_helper(SINGLE, "scaffold_skill_no_effects")

    def forbidden(*_args, **_kwargs):
        raise AssertionError("network or subprocess access is forbidden")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)
    plan, _, _, _, _ = module.build_plan(repo, request)
    assert plan["operation"] == "genaptic-skillsets-create-skill"


def test_twenty_skill_pack_preview_and_apply(repo: Path) -> None:
    data = json.loads(SKILLPACK_EXAMPLE.read_text(encoding="utf-8"))
    prototype = data["skills"][0]
    skills = []
    for index in range(20):
        skill = json.loads(json.dumps(prototype))
        skill_id = f"go-observability-{index + 1:02d}"
        neighbor = f"go-observability-{(index + 1) % 20 + 1:02d}"
        skill["name"] = skill_id
        skill["nearestNeighbor"] = neighbor
        skill["openai"] = {
            "displayName": f"Go Observability {index + 1:02d}",
            "shortDescription": f"Design Go observability workflow number {index + 1:02d}",
            "defaultPrompt": f"Use ${skill_id} to design this focused Go observability workflow.",
        }
        skills.append(skill)
    data["skills"] = skills
    data["operations"] = skills[0]["operations"]
    data["interface"]["starterPrompts"] = [
        {
            "skill": skill["name"],
            "prompt": skill["openai"]["defaultPrompt"],
        }
        for skill in skills[:2]
    ]
    request = repo / "twenty-skills.json"
    request.write_text(json.dumps(data), encoding="utf-8")
    _, plan = preview(SKILLPACK, repo, request)
    assert len(plan["skills"]) == 20
    assert len({skill["name"] for skill in plan["skills"]}) == 20
    completed = run_helper(
        SKILLPACK,
        repo,
        request,
        "--apply",
        "--plan-digest",
        plan["planDigest"],
        "--json",
    )
    assert completed.returncode == 0, completed.stderr
    destination = repo / plan["destination"]
    assert len(list((destination / "skills").iterdir())) == 20
    expected = json.loads(
        (destination / "tests/compatibility/expected-skills.json").read_text(encoding="utf-8")
    )
    assert expected["skills"] == [skill["name"] for skill in skills]


def schema_errors(schema_path: Path, data: dict) -> list:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    return list(Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(data))


@pytest.mark.parametrize(
    ("field", "accepted", "rejected"),
    [
        ("skillpackName", "abc", "ab"),
        ("details", "d" * 16000, "d" * 16001),
    ],
)
def test_skillpack_top_level_bounds_agree_with_schema(
    repo: Path, field: str, accepted: str, rejected: str
) -> None:
    schema = SKILLPACK.parents[1] / "assets/skillpack-request.schema.json"
    base = json.loads(SKILLPACK_EXAMPLE.read_text(encoding="utf-8"))
    accepted_data = deepcopy(base)
    accepted_data[field] = accepted
    assert schema_errors(schema, accepted_data) == []
    accepted_path = repo / f"accepted-{field}.json"
    accepted_path.write_text(json.dumps(accepted_data), encoding="utf-8")
    assert run_helper(SKILLPACK, repo, accepted_path, "--json").returncode == 0

    rejected_data = deepcopy(base)
    rejected_data[field] = rejected
    assert schema_errors(schema, rejected_data)
    rejected_path = repo / f"rejected-{field}.json"
    rejected_path.write_text(json.dumps(rejected_data), encoding="utf-8")
    assert run_helper(SKILLPACK, repo, rejected_path, "--json").returncode == 2


def test_semver_and_http_source_unbounded_schema_intent_matches_helpers(repo: Path) -> None:
    long_version = "1.0.0-" + "a" * 256
    long_source = "https://example.com/" + "a" * 4096

    single_schema = SINGLE.parents[1] / "assets/skill-request.schema.json"
    single_data = json.loads(SINGLE_EXAMPLE.read_text(encoding="utf-8"))
    single_data["expectedPackVersion"] = long_version
    single_data["userSources"] = [long_source]
    assert schema_errors(single_schema, single_data) == []
    single_module = load_helper(SINGLE, "scaffold_skill_schema_bounds")
    assert single_module.validate_request(deepcopy(single_data)) == single_data

    skillpack_schema = SKILLPACK.parents[1] / "assets/skillpack-request.schema.json"
    skillpack_data = json.loads(SKILLPACK_EXAMPLE.read_text(encoding="utf-8"))
    skillpack_data["version"] = long_version
    skillpack_data["userSources"] = [long_source]
    assert schema_errors(skillpack_schema, skillpack_data) == []
    path = repo / "long-version-source.json"
    path.write_text(json.dumps(skillpack_data), encoding="utf-8")
    completed = run_helper(SKILLPACK, repo, path, "--json")
    assert completed.returncode == 0, completed.stderr


@pytest.mark.parametrize("length", [12000, 12001])
def test_per_skill_details_bound_matches_schema(repo: Path, length: int) -> None:
    schema = SKILLPACK.parents[1] / "assets/skillpack-request.schema.json"
    data = json.loads(SKILLPACK_EXAMPLE.read_text(encoding="utf-8"))
    data["skills"][0]["details"] = "s" * length
    errors = schema_errors(schema, data)
    path = repo / f"skill-details-{length}.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    completed = run_helper(SKILLPACK, repo, path, "--json")
    assert (errors == []) is (completed.returncode == 0)


def test_scaffolded_readme_preserves_full_skill_details_without_ellipsis(repo: Path) -> None:
    data = json.loads(SKILLPACK_EXAMPLE.read_text(encoding="utf-8"))
    detail = (
        "Design the complete first observability boundary with every declared constraint. "
        + "Preserve this deliberately long middle section exactly in the scaffold output. " * 8
        + "END-OF-DETAIL-SENTINEL"
    )
    data["skills"] = [data["skills"][0]]
    data["skills"][0]["details"] = detail
    data["skills"][0]["nearestNeighbor"] = "python-project-layout"
    data["operations"] = data["skills"][0]["operations"]
    skill = data["skills"][0]["name"]
    data["interface"]["starterPrompts"] = [
        data["interface"]["starterPrompts"][0],
        {
            "skill": skill,
            "prompt": f"Use ${skill} to review an existing logging design for safety gaps.",
        },
    ]
    request = repo / "full-details.json"
    request.write_text(json.dumps(data), encoding="utf-8")
    _, plan = preview(SKILLPACK, repo, request)
    completed = run_helper(
        SKILLPACK,
        repo,
        request,
        "--apply",
        "--plan-digest",
        plan["planDigest"],
        "--json",
    )
    assert completed.returncode == 0, completed.stderr
    readme = (repo / plan["destination"] / "README.md").read_text(encoding="utf-8")
    assert " ".join(detail.split()) in readme
    assert "END-OF-DETAIL-SENTINEL" in readme
    assert "END-OF-DETAIL-SENTINEL..." not in readme
