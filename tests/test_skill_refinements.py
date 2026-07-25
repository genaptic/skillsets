from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
SKILL_FILES = sorted(ROOT.glob("packs/**/skills/*/SKILL.md"))
TIMEOUT_RENDERER = (
    ROOT
    / "packs/shared/postgres-databases/skills/postgres-schema-review"
    / "scripts/render_review_queries.py"
)
FRONTMATTER_KEYS = {"name", "description", "license", "metadata"}
INTERFACE_KEYS = {"display_name", "short_description", "default_prompt"}
MARKDOWN_LINK = re.compile(r"\[[^]]+\]\(([^)]+)\)")


def parse_skill(path: Path) -> tuple[dict[str, object], str]:
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), path
    frontmatter_text, body = text[4:].split("\n---\n", maxsplit=1)
    frontmatter = yaml.safe_load(frontmatter_text)
    assert isinstance(frontmatter, dict), path
    return frontmatter, body


def run_renderer(flag: str, value: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-I",
            "-S",
            str(TIMEOUT_RENDERER),
            "--section",
            "context",
            flag,
            value,
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        timeout=10,
    )


def test_skill_frontmatter_mirrors_owning_pack_lifecycle() -> None:
    assert len(SKILL_FILES) == 26
    for path in SKILL_FILES:
        frontmatter, body = parse_skill(path)
        assert set(frontmatter) == FRONTMATTER_KEYS, path
        assert frontmatter["name"] == path.parent.name, path
        assert frontmatter["license"] == "Apache-2.0", path

        metadata = frontmatter["metadata"]
        assert isinstance(metadata, dict), path
        manifest = yaml.safe_load((path.parents[2] / "skillpack.yaml").read_text(encoding="utf-8"))
        assert metadata["skillpack"] == manifest["id"], path
        assert metadata["version"] == manifest["version"], path
        assert metadata["maturity"] == manifest["maturity"], path
        assert all(isinstance(value, str) for value in metadata.values()), path
        assert "## Compatibility\n" in body, path


def test_skill_resource_links_resolve_without_boilerplate_readmes() -> None:
    readmes = list(ROOT.glob("packs/**/skills/*/assets/README.md"))
    readmes.extend(ROOT.glob("packs/**/skills/*/references/README.md"))
    readmes.extend(ROOT.glob("packs/**/skills/*/scripts/README.md"))
    assert readmes == []

    resource_directories = [
        path
        for kind in ("assets", "references", "scripts")
        for path in ROOT.glob(f"packs/**/skills/*/{kind}")
    ]
    assert all(any(child.is_file() for child in path.rglob("*")) for path in resource_directories)

    for skill_path in SKILL_FILES:
        for path in skill_path.parent.rglob("*.md"):
            text = path.read_text(encoding="utf-8")
            for target in MARKDOWN_LINK.findall(text):
                if target.startswith(("#", "https://", "http://")):
                    continue
                relative_target = target.split("#", maxsplit=1)[0]
                destination = path.parent / relative_target
                assert destination.is_file() or destination.is_dir(), f"{path}: {target}"


def test_every_skill_has_minimal_openai_interface_metadata() -> None:
    for path in SKILL_FILES:
        skill_name = path.parent.name
        openai_path = path.parent / "agents/openai.yaml"
        data = yaml.safe_load(openai_path.read_text(encoding="utf-8"))
        assert set(data) == {"interface"}, openai_path

        interface = data["interface"]
        assert set(interface) == INTERFACE_KEYS, openai_path
        assert all(isinstance(value, str) for value in interface.values()), openai_path
        assert interface["display_name"].strip(), openai_path
        assert 25 <= len(interface["short_description"]) <= 64, openai_path
        assert f"${skill_name}" in interface["default_prompt"], openai_path


def test_python_boundary_routing_descriptions_coordinate_only_explicit_joint_work() -> None:
    descriptions = {
        skill: str(
            parse_skill(next(path for path in SKILL_FILES if path.parent.name == skill))[0][
                "description"
            ]
        )
        for skill in (
            "python-cli-error-output",
            "python-cli-testing",
            "python-error-handling",
            "python-project-layout",
            "python-testing-strategy",
        )
    }

    error_output = descriptions["python-cli-error-output"]
    assert "alongside python-error-handling" in error_output
    assert "also requires internal exception taxonomy or translation boundaries" in error_output
    assert "Both skills are required" in error_output
    assert "CLI diagnostics, streams, traceback policy, or exit statuses" in error_output
    assert "exclusively internal exception work without a CLI process mapping" in error_output

    cli_testing = descriptions["python-cli-testing"]
    assert "alongside python-testing-strategy" in cli_testing
    assert "also requires repository-wide test layers or CI selection" in cli_testing
    assert "Both skills are required" in cli_testing
    assert "focused CLI behavior matrix" in cli_testing
    assert "merely to execute or report an already-defined smoke or health command" in cli_testing
    assert "without a CLI-specific test deliverable" in cli_testing

    error_handling = descriptions["python-error-handling"]
    assert "alongside python-cli-error-output" in error_handling
    assert "Both skills are required" in error_handling
    assert "CLI diagnostics, streams, traceback policy, or exit statuses" in error_handling
    assert "exclusively CLI-facing stderr and exit-code design" in error_handling

    error_handling_body = next(
        path for path in SKILL_FILES if path.parent.name == "python-error-handling"
    ).read_text(encoding="utf-8")
    assert "exclusively user-facing CLI messages" in error_handling_body
    assert "without internal exception-taxonomy or translation work" in error_handling_body

    project_layout = descriptions["python-project-layout"]
    assert "alongside python-testing-strategy" in project_layout
    assert "Both skills are required" in project_layout
    assert "combined layout-and-test-architecture work" in project_layout
    assert "test-case architecture that leaves package layout unchanged" in project_layout

    testing_strategy = descriptions["python-testing-strategy"]
    assert "alongside python-cli-testing" in testing_strategy
    assert "repository-wide strategy also needs a CLI-specific matrix" in testing_strategy
    assert "alongside python-project-layout" in testing_strategy
    assert "migration also requires redesigning" in testing_strategy
    assert "Both skills in the applicable pair are required" in testing_strategy
    assert "layout changes that leave test architecture unchanged" in testing_strategy

    generated_roots = {
        "python-cli-error-output": "python-cli-apps",
        "python-cli-testing": "python-cli-apps",
        "python-error-handling": "python-best-practices",
        "python-project-layout": "python-best-practices",
        "python-testing-strategy": "python-best-practices",
    }
    for skill, pack in generated_roots.items():
        canonical = next(path for path in SKILL_FILES if path.parent.name == skill)
        generated = ROOT / "dist/dev/codex/plugins" / pack / "skills" / skill / "SKILL.md"
        assert generated.read_bytes() == canonical.read_bytes()

    project_layout_body = next(
        path for path in SKILL_FILES if path.parent.name == "python-project-layout"
    ).read_text(encoding="utf-8")
    assert "Plan an ordered, rollback-friendly implementation." in project_layout_body
    assert "Always number the implementation" in project_layout_body
    assert "last known-good rollback point" in project_layout_body
    assert "For a new project, order metadata" in project_layout_body
    assert "numbered implementation sequence with an explicit rollback point" in project_layout_body


@pytest.mark.parametrize("flag", ["--statement-timeout", "--lock-timeout"])
@pytest.mark.parametrize("value", ["500ms", "5s", "2min", "1h"])
def test_review_query_renderer_accepts_bounded_timeouts(flag: str, value: str) -> None:
    completed = run_renderer(flag, value)
    assert completed.returncode == 0, completed.stderr
    assert f"'{value}'" in completed.stdout


@pytest.mark.parametrize("flag", ["--statement-timeout", "--lock-timeout"])
@pytest.mark.parametrize(
    "value",
    [
        "0ms",
        "0s",
        "infinity",
        "5 s",
        " 5s",
        "5s ",
        "5seconds",
        "-1s",
        "1.5s",
        "25h",
        "1441min",
        "5s; SELECT 1",
        "'; SELECT pg_sleep(1); --",
    ],
)
def test_review_query_renderer_rejects_unbounded_or_unsafe_timeouts(flag: str, value: str) -> None:
    completed = run_renderer(flag, value)
    assert completed.returncode == 2
    assert completed.stdout == ""
    assert "timeout" in completed.stderr.lower()
