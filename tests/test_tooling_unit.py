from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest
import yaml

from skillpack_tools import cli
from skillpack_tools.evals import validate_eval_file
from skillpack_tools.generate import (
    _portable_source_mode,
    apply_generated_files,
    build_generated_files,
)
from skillpack_tools.models import get_pack, load_repository
from skillpack_tools.util import (
    SkillpackError,
    atomic_write,
    dump_yaml,
    find_repository_root,
    json_text,
    load_yaml,
    markdown_local_links,
    parse_skill_markdown,
    path_is_within,
    relative_posix,
    replace_marked_section,
    rollback_after_failure,
    sha256_bytes,
    sha256_file,
)
from skillpack_tools.validate import (
    _load_json,
    _missing_operational_sections,
    _schema_errors,
    _validate_script,
    _validate_workflows,
    raise_for_result,
    validate_repository,
)

ROOT = Path(__file__).resolve().parents[1]


def test_rollback_failure_reports_both_failures_and_chains_from_rollback() -> None:
    original = KeyboardInterrupt("interrupted write")
    rollback = OSError("restoration failed")

    def fail_rollback() -> None:
        raise rollback

    with pytest.raises(SkillpackError) as raised:
        rollback_after_failure(original, fail_rollback, label="Lifecycle update")
    message = str(raised.value)
    assert "KeyboardInterrupt: interrupted write" in message
    assert "OSError: restoration failed" in message
    assert raised.value.__cause__ is rollback


def test_operational_section_validation_accepts_both_supported_heading_styles() -> None:
    common = "\n".join(
        (
            "## Compatibility",
            "## Inputs",
            "## Procedure",
            "## Verification",
            "## Output contract",
            "## Resources",
        )
    )
    assert _missing_operational_sections(f"# Outcome\n## Safety posture\n{common}\n") == set()
    assert _missing_operational_sections(f"## Outcome\n## Safety\n{common}\n") == set()
    assert _missing_operational_sections(f"## Outcome\n{common}\n") == {"Safety"}


def copy_ignore(directory: str, names: list[str]) -> set[str]:
    ignored = {".git", ".pytest_cache", "__pycache__", ".venv", "releases"} & set(names)
    if Path(directory) == ROOT / "dist":
        ignored.update({"install", "opencode"} & set(names))
    ignored.update(name for name in names if name.endswith((".pyc", ".pyo")))
    return ignored


@pytest.fixture()
def repo_copy(tmp_path: Path) -> Path:
    target = tmp_path / "skillsets"
    shutil.copytree(ROOT, target, ignore=copy_ignore)
    return target


def test_utilities_cover_success_and_error_paths(tmp_path: Path) -> None:
    nested = ROOT / "packs" / "python" / "best-practices" / "README.md"
    assert find_repository_root(nested) == ROOT
    with pytest.raises(SkillpackError, match="Could not find"):
        find_repository_root(tmp_path)

    mapping = tmp_path / "mapping.yaml"
    mapping.write_text("alpha: 1\n", encoding="utf-8")
    assert load_yaml(mapping) == {"alpha": 1}
    assert yaml.safe_load(dump_yaml({"beta": [1, 2]})) == {"beta": [1, 2]}
    assert json_text({"é": 1}).endswith("\n")
    assert "é" in json_text({"é": 1})

    with pytest.raises(SkillpackError, match="does not exist"):
        load_yaml(tmp_path / "missing.yaml")
    invalid = tmp_path / "invalid.yaml"
    invalid.write_text("[unterminated", encoding="utf-8")
    with pytest.raises(SkillpackError, match="Invalid YAML"):
        load_yaml(invalid)
    sequence = tmp_path / "sequence.yaml"
    sequence.write_text("- one\n", encoding="utf-8")
    with pytest.raises(SkillpackError, match="Expected a YAML mapping"):
        load_yaml(sequence)

    skill = tmp_path / "SKILL.md"
    skill.write_text("---\nname: sample\n---\n# Body\n", encoding="utf-8")
    metadata, body = parse_skill_markdown(skill)
    assert metadata["name"] == "sample"
    assert body == "# Body\n"
    skill.write_text("# no frontmatter\n", encoding="utf-8")
    with pytest.raises(SkillpackError, match="must begin"):
        parse_skill_markdown(skill)
    skill.write_text("---\n[bad\n---\nbody\n", encoding="utf-8")
    with pytest.raises(SkillpackError, match="Invalid frontmatter"):
        parse_skill_markdown(skill)
    skill.write_text("---\n- item\n---\nbody\n", encoding="utf-8")
    with pytest.raises(SkillpackError, match="must be a mapping"):
        parse_skill_markdown(skill)

    links = tmp_path / "links.md"
    links.write_text(
        "[local](guide.md) [angle](<two words.md>) [anchor](#x) "
        "[web](https://example.com) [mail](mailto:test@example.com) "
        "![image](ignored.png) [section](guide.md#part)\n",
        encoding="utf-8",
    )
    assert markdown_local_links(links) == ["guide.md", "two", "guide.md"]

    target = tmp_path / "nested" / "file.txt"
    atomic_write(target, "first\n", executable=True)
    assert target.read_text(encoding="utf-8") == "first\n"
    if os.name != "nt":
        assert os.access(target, os.X_OK)
    else:
        assert os.access(target, os.R_OK | os.W_OK)
    target.chmod(0o640)
    expected_mode = target.stat().st_mode & 0o777
    atomic_write(target, "second\n")
    assert target.stat().st_mode & 0o777 == expected_mode

    replaced = replace_marked_section(
        "before\n  <!-- B -->\nold\n  <!-- E -->\nafter\n",
        "<!-- B -->",
        "<!-- E -->",
        "new",
    )
    assert "  <!-- B -->\nnew\n  <!-- E -->" in replaced
    with pytest.raises(SkillpackError, match="Could not find generated section"):
        replace_marked_section("none", "BEGIN", "END", "body")

    child = tmp_path / "nested" / "child"
    assert path_is_within(child, tmp_path)
    assert not path_is_within(tmp_path.parent, tmp_path)
    assert relative_posix(target, tmp_path) == "nested/file.txt"
    assert sha256_bytes(b"value") == sha256_file(_write_bytes(tmp_path / "value.bin", b"value"))


def _write_bytes(path: Path, content: bytes) -> Path:
    path.write_bytes(content)
    return path


def test_portable_source_mode_infers_executable_shebang_without_git(tmp_path: Path) -> None:
    script = tmp_path / "scripts" / "helper.py"
    script.parent.mkdir()
    script.write_text("#!/usr/bin/env python3\nprint('ok')\n", encoding="utf-8")
    data = script.with_name("data.json")
    data.write_text('{"fixture": true}\n', encoding="utf-8")

    assert _portable_source_mode(tmp_path, script, tracked_modes={}) == 0o755
    assert _portable_source_mode(tmp_path, data, tracked_modes={}) == 0o644


def test_model_accessors_and_unknown_pack() -> None:
    config = load_repository(ROOT)
    assert config.owner == "genaptic"
    assert config.name == "skillsets"
    assert config.git_url.endswith(".git")
    assert config.web_url.endswith(config.slug)
    assert config.project_name == "Genaptic Skillsets"
    assert config.publisher_name == "Genaptic"
    assert config.maintainer_github == "jecsand838"
    assert config.security_email is None
    assert config.security_channel == "github-private-vulnerability-reporting"
    assert config.marketplace_display_name == "Genaptic Skillsets"
    assert config.marketplace_description
    assert config.initial_year == 2026

    pack = get_pack(ROOT, "postgres-databases")
    assert pack.display_name == "PostgreSQL Databases"
    assert pack.language == "shared"
    assert pack.subject == "postgres-databases"
    assert pack.tag == "postgres-databases-v1.0.0"
    assert pack.source_sha is None
    assert pack.maintainers
    assert pack.targets == ["claude-code", "codex", "opencode"]
    assert pack.category == "Data & Databases"
    assert pack.keywords
    assert pack.compatibility
    assert pack.operations
    with pytest.raises(KeyError, match="Unknown pack"):
        get_pack(ROOT, "missing-pack")


def test_cli_success_paths(repo_copy: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["--root", str(repo_copy), "generate", "--check"]) == 0
    assert "current" in capsys.readouterr().out

    catalog = repo_copy / "catalog.json"
    catalog.write_text(catalog.read_text(encoding="utf-8") + " ", encoding="utf-8")
    assert cli.main(["--root", str(repo_copy), "generate"]) == 0
    assert "catalog.json" in capsys.readouterr().out
    assert cli.main(["--root", str(repo_copy), "generate"]) == 0
    assert "already current" in capsys.readouterr().out

    assert (
        cli.main(
            ["--root", str(repo_copy), "validate", "--check-generated", "--json", "validation.json"]
        )
        == 0
    )
    validation = json.loads((repo_copy / "validation.json").read_text(encoding="utf-8"))
    assert validation["ok"] is True
    assert validation["warnings"] == []
    capsys.readouterr()

    assert (
        cli.main(
            [
                "--root",
                str(repo_copy),
                "eval",
                "--skill",
                "python-project-layout",
                "--json",
                "eval.json",
            ]
        )
        == 0
    )
    assert (
        json.loads((repo_copy / "eval.json").read_text(encoding="utf-8"))["totals"]["skills"] == 1
    )
    capsys.readouterr()

    assert (
        cli.main(
            [
                "--root",
                str(repo_copy),
                "configure",
                "--owner",
                "example-org",
                "--repository",
                "skills-repo",
                "--maintainer-name",
                "Example Maintainer",
                "--maintainer-github",
                "example-maintainer",
                "--maintainer-github-id",
                "123456",
                "--trusted-ssh-fingerprint",
                "SHA256:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
                "--security-email",
                "security@example.org",
            ]
        )
        == 0
    )
    assert "Repository identity updated" in capsys.readouterr().out

    assert cli.main(["--root", str(repo_copy), "release", "python-best-practices", "--draft"]) == 0
    released = capsys.readouterr().out
    assert "Archive:" in released and "Checksum:" in released and "Release notes:" in released


def test_cli_error_paths(repo_copy: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["--root", str(repo_copy), "eval", "--skill", "missing-skill"]) == 1
    assert "Unknown skill" in capsys.readouterr().err

    assert (
        cli.main(
            [
                "--root",
                str(repo_copy),
                "configure",
                "--owner",
                "invalid!",
                "--maintainer-name",
                "Example",
                "--security-email",
                "security@example.org",
            ]
        )
        == 1
    )
    assert "repository.yaml:repository.owner" in capsys.readouterr().err

    (repo_copy / "docs" / "legacy-placeholder.md").write_text(
        "Replace YOUR_HANDLE before publication.\n", encoding="utf-8"
    )
    assert cli.main(["--root", str(repo_copy), "validate", "--strict-placeholders"]) == 1
    assert "validation failed" in capsys.readouterr().err.lower()

    with pytest.raises(SkillpackError, match="Could not find"):
        cli.main(["--root", str(repo_copy.parent / "missing"), "generate", "--check"])


def test_eval_validation_reports_semantic_failures(tmp_path: Path) -> None:
    skill_dir = tmp_path / "skills" / "sample-skill" / "evals"
    skill_dir.mkdir(parents=True)
    path = skill_dir / "evals.json"

    path.write_text("{bad", encoding="utf-8")
    errors, summary = validate_eval_file(ROOT, path)
    assert summary is None and "invalid JSON" in errors[0]

    path.write_text(json.dumps({"skill": "sample-skill"}), encoding="utf-8")
    errors, summary = validate_eval_file(ROOT, path)
    assert summary is None and errors

    routing = []
    for index in range(6):
        routing.append(
            {
                "id": "duplicate" if index < 2 else f"case-{index}",
                "kind": "negative" if index >= 5 else "explicit-positive",
                "prompt": f"A sufficiently long routing prompt number {index} for validation.",
                "shouldTrigger": False,
                "reason": f"A sufficiently long routing reason number {index} for validation.",
            }
        )
    behavior_case = {
        "id": "same",
        "kind": "safety",
        "prompt": "A sufficiently long behavior prompt for structural validation.",
        "assertions": [
            "First meaningful assertion",
            "Second meaningful assertion",
            "Third meaningful assertion",
        ],
        "forbidden": [
            "First forbidden behavior",
            "Second forbidden behavior",
        ],
    }
    data = {
        "schemaVersion": 1,
        "skill": "wrong-skill",
        "routing": routing,
        "behavior": [behavior_case, dict(behavior_case)],
    }
    path.write_text(json.dumps(data), encoding="utf-8")
    errors, summary = validate_eval_file(ROOT, path)
    assert summary is not None
    combined = "\n".join(errors)
    for expected in (
        "expected directory name",
        "routing case IDs must be unique",
        "implicit-positive",
        "contextual-positive",
        "negative routing",
        "shouldTrigger",
        "behavior case IDs",
        "end-to-end",
    ):
        assert expected in combined


def test_low_level_validation_helpers(tmp_path: Path) -> None:
    errors: list[str] = []
    assert _load_json(tmp_path / "missing.json", errors) is None
    assert "Missing required" in errors[-1]
    invalid = tmp_path / "invalid.json"
    invalid.write_text("{bad", encoding="utf-8")
    assert _load_json(invalid, errors) is None
    assert "Invalid JSON" in errors[-1]
    sequence = tmp_path / "sequence.json"
    sequence.write_text("[]", encoding="utf-8")
    assert _load_json(sequence, errors) is None
    assert "Expected JSON object" in errors[-1]

    schema_errors = _schema_errors({}, {"type": "object", "required": ["name"]}, "sample")
    assert schema_errors and "name" in schema_errors[0]

    bad_script = tmp_path / "bad.py"
    bad_script.write_text(
        'requests.get("https://example.com")\nthis is invalid python\n', encoding="utf-8"
    )
    script_errors: list[str] = []
    _validate_script(bad_script, script_errors)
    assert any("must not access the network" in item for item in script_errors)
    assert any("syntax error" in item.lower() for item in script_errors)

    workflow_root = tmp_path / ".github" / "workflows"
    workflow_errors: list[str] = []
    _validate_workflows(tmp_path, workflow_errors)
    assert "Missing .github/workflows" in workflow_errors[0]
    workflow_root.mkdir(parents=True)
    workflow_errors = []
    _validate_workflows(tmp_path, workflow_errors)
    assert "No GitHub Actions" in workflow_errors[0]
    bad_workflow = workflow_root / "unsafe.yml"
    bad_workflow.write_text(
        "on:\n  pull_request_target:\npermissions:\n  contents: write\n  issues: write\njobs:\n"
        "  bad:\n    steps:\n      - name: Checkout\n        uses: actions/checkout@v4\n"
        "        with:\n          persist-credentials: true\n",
        encoding="utf-8",
    )
    workflow_errors = []
    _validate_workflows(tmp_path, workflow_errors)
    joined = "\n".join(workflow_errors)
    assert "pull_request_target" in joined
    assert "credentials must not persist" in joined
    assert "full lowercase commit SHA" in joined
    assert "only release.yml" in joined
    assert "post-publication tracking job" in joined


def test_repository_validator_detects_compound_corruption(repo_copy: Path) -> None:
    # Workflow supply-chain failures.
    unsafe = repo_copy / ".github" / "workflows" / "unsafe.yml"
    unsafe.write_text(
        "on:\n  pull_request_target:\njobs:\n  bad:\n    steps:\n"
        "      - name: Checkout\n        uses: actions/checkout@v4\n        with:\n          persist-credentials: true\n",
        encoding="utf-8",
    )

    # Pack manifest and inventory failures.
    manifest_path = repo_copy / "packs" / "python" / "best-practices" / "skillpack.yaml"
    manifest = load_yaml(manifest_path)
    manifest["id"] = "wrong-id"
    manifest["version"] = "not-semver"
    manifest["source-sha"] = "short"
    manifest_path.write_text(dump_yaml(manifest), encoding="utf-8")
    undeclared = manifest_path.parent / "skills" / "undeclared-skill"
    undeclared.mkdir()

    # Skill metadata, resources, links, helper, and size failures.
    skill_dir = manifest_path.parent / "skills" / "python-project-layout"
    skill_file = skill_dir / "SKILL.md"
    skill_file.write_text(
        "---\nname: wrong-name\ndescription: 42\nlicense: MIT\ncompatibility: short\n"
        "metadata: not-a-map\nunsupported: true\n---\n# Incomplete\n[escape](../../outside.md)\n"
        "[missing](references/missing.md)\n",
        encoding="utf-8",
    )
    (skill_dir / "scripts" / "unsafe.py").write_text(
        'requests.get("https://example.com")\nthis is invalid python\n', encoding="utf-8"
    )
    (skill_dir / "large.bin").write_bytes(b"x" * 1_000_001)
    (repo_copy / ".env").write_text("SECRET=value\n", encoding="utf-8")
    (repo_copy / "docs" / "legacy-placeholder.md").write_text(
        "Legacy owner: your-github-handle.\n", encoding="utf-8"
    )

    # Compatibility and generated drift failures.
    expected = manifest_path.parent / "tests" / "compatibility" / "expected-skills.json"
    expected.write_text('{"skills": []}\n', encoding="utf-8")
    (repo_copy / "catalog.json").write_text("{}\n", encoding="utf-8")

    result = validate_repository(repo_copy, check_generated=True, strict_placeholders=True)
    assert not result.ok
    combined = "\n".join(result.errors + result.warnings)
    for expected_text in (
        "pull_request_target",
        "declare explicit workflow permissions",
        "must be 'python-best-practices'",
        "invalid Semantic Version",
        "source-sha",
        "undeclared skill directory",
        "unsupported frontmatter",
        "must match directory",
        "description must be a string",
        "license must be Apache-2.0",
        "metadata must be a mapping",
        "missing required headings",
        "link escapes",
        "broken relative link",
        "must not access the network",
        "Python syntax error",
        "file exceeds 1 MB",
        "skills must exactly match",
        "Generated files are missing or stale",
        "credential file must not be committed",
        "contains 'your-github-handle'",
    ):
        assert expected_text in combined
    with pytest.raises(SkillpackError, match="Repository validation failed"):
        raise_for_result(result)


def test_generation_ignores_legacy_sha_cleans_legacy_roots_and_handles_missing_packs(
    repo_copy: Path,
) -> None:
    manifest_path = repo_copy / "packs" / "python" / "best-practices" / "skillpack.yaml"
    manifest = load_yaml(manifest_path)
    manifest["source-sha"] = "a" * 40
    manifest_path.write_text(dump_yaml(manifest), encoding="utf-8")
    generated = build_generated_files(repo_copy)
    marketplace = json.loads(generated[".claude-plugin/marketplace.json"])
    assert marketplace["plugins"] == []
    development = json.loads(generated["dist/dev/claude/.claude-plugin/marketplace.json"])
    source = next(
        item for item in development["plugins"] if item["name"] == "python-best-practices"
    )["source"]
    assert source == "./plugins/python-best-practices"

    # Pre-v2 output roots are migration cleanup targets, never current generated surfaces.
    stale = repo_copy / "dist" / "install" / "stale.txt"
    stale.parent.mkdir(parents=True)
    stale.write_text("stale\n", encoding="utf-8")
    changed = apply_generated_files(repo_copy)
    assert "dist/install/stale.txt" in changed
    assert not stale.exists()

    shutil.rmtree(repo_copy / "packs")
    with pytest.raises(SkillpackError, match=r"No skillpack\.yaml"):
        build_generated_files(repo_copy)
