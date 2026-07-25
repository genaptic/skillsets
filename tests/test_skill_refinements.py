from __future__ import annotations

import json
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
            "python-test-architecture",
        )
    }
    assert all(len(description) <= 500 for description in descriptions.values())
    required_prefix_terms = {
        "python-cli-error-output": ("python-error-handling",),
        "python-cli-testing": ("python-test-architecture",),
        "python-error-handling": (),
        "python-project-layout": (),
        "python-test-architecture": (),
    }
    for skill, partners in required_prefix_terms.items():
        description = descriptions[skill]
        assert description.index("Use when") < 250, skill
        exclusion_markers = (
            marker for marker in ("Do not use", "Never use") if marker in description
        )
        assert min(description.index(marker) for marker in exclusion_markers) < 400, skill
        for partner in partners:
            assert description.index(partner) < 350, (skill, partner)

    for skill in (
        "python-error-handling",
        "python-project-layout",
        "python-test-architecture",
    ):
        assert all(
            neighbor not in descriptions[skill] for neighbor in descriptions if neighbor != skill
        )

    error_output = descriptions["python-cli-error-output"]
    assert "Do not use when the request excludes Python or CLI changes." in error_output
    assert "only for explicit internal taxonomy or translation work" in error_output
    assert "an exception merely causing CLI output keeps this skill alone" in error_output
    assert "Do not use for internal exception work or command-tree design." in error_output

    cli_testing = descriptions["python-cli-testing"]
    assert "A comprehensive CLI-only matrix uses this skill alone." in cli_testing
    assert "only when explicitly combining it with repository-wide test architecture" in cli_testing
    assert "Do not use for broad strategy without a CLI deliverable" in cli_testing
    assert "or running an existing smoke command." in cli_testing

    error_handling = descriptions["python-error-handling"]
    assert error_handling.startswith(
        "Use when—and only when—the request explicitly asks for internal exception taxonomy, "
        "translation boundaries, chaining, propagation, cleanup ownership, exception "
        "logging/warnings, or retry policy."
    )
    assert "Do not use unless at least one listed internal exception or recovery-policy" in (
        error_handling
    )
    assert all(
        phrase not in error_handling.lower()
        for phrase in (
            "cli",
            "streams",
            "exit status",
            "http",
            "rpc",
            "message error",
        )
    )

    error_handling_body = next(
        path for path in SKILL_FILES if path.parent.name == "python-error-handling"
    ).read_text(encoding="utf-8")
    assert "exclusively user-facing CLI messages" in error_handling_body
    assert "without internal exception-taxonomy or translation work" in error_handling_body

    project_layout = descriptions["python-project-layout"]
    assert project_layout.startswith(
        "Use when—and only when—the request explicitly asks for package layout, import isolation, "
        "package discovery, namespace-package boundaries, distribution build metadata, packaged "
        "resources/typing metadata, or wheel/sdist contents."
    )
    assert "Do not use unless at least one listed packaging, import, or artifact outcome" in (
        project_layout
    )
    assert all(
        phrase not in project_layout.lower()
        for phrase in (
            "cli interface",
            "subcommands",
            "global options",
            "flags",
            "help text",
            "configuration precedence",
        )
    )

    testing_strategy = descriptions["python-test-architecture"]
    assert testing_strategy.startswith(
        "Use when—and only when—the request explicitly asks for repository-wide test strategy, "
        "multi-level test architecture, suite-wide fixture ownership, global determinism, "
        "coverage policy, flake elimination, CI selection, or runtime budgets."
    )
    assert (
        "Do not use unless at least one listed repository-wide or multi-layer outcome"
        in testing_strategy
    )
    assert all(
        phrase not in testing_strategy.lower()
        for phrase in (
            "one cli command",
            "subprocess",
            "stdout",
            "stderr",
            "stream",
            "exit-code",
        )
    )

    generated_roots = {
        "python-cli-error-output": "python-cli-apps",
        "python-cli-testing": "python-cli-apps",
        "python-error-handling": "python-best-practices",
        "python-project-layout": "python-best-practices",
        "python-test-architecture": "python-best-practices",
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
    assert "records repository, distribution, and import names separately" in project_layout_body
    assert "mark each" in project_layout_body
    assert "unavailable identity explicitly" in project_layout_body

    testing_strategy_body = next(
        path for path in SKILL_FILES if path.parent.name == "python-test-architecture"
    ).read_text(encoding="utf-8")
    assert "Always name a bounded fast pull-request subset." in testing_strategy_body
    assert "risk-critical unit, contract, and integration checks" in testing_strategy_body
    assert "Put repeated or randomized runs, parallel stress" in testing_strategy_body
    assert "Do not defer a risk-critical check merely because it is" in testing_strategy_body
    assert "exact bounded fast" in testing_strategy_body
    assert "capture the first-failure artifacts" in testing_strategy_body
    assert "repetition count" in testing_strategy_body
    assert "explicit measured pass threshold" in testing_strategy_body


def test_python_release_routing_guards_match_existing_negative_evals() -> None:
    expectations = {
        "python-project-layout": (
            "negative-cli-command-tree",
            "Design subcommands, global options, help text, and configuration precedence for our "
            "Python executable.",
            "Use when—and only when—the request explicitly asks for package layout, import "
            "isolation, package discovery,",
        ),
        "python-test-architecture": (
            "negative-single-cli-contract",
            "Write subprocess assertions for one CLI command's stderr and exit code contract.",
            "Use when—and only when—the request explicitly asks for repository-wide test strategy,",
        ),
        "python-error-handling": (
            "negative-cli-stderr",
            "Map command failures to stable exit codes and ensure human diagnostics go to stderr "
            "while JSON remains on stdout.",
            "Use when—and only when—the request explicitly asks for internal exception taxonomy,",
        ),
    }

    for skill, (case_id, prompt, opening) in expectations.items():
        skill_path = next(path for path in SKILL_FILES if path.parent.name == skill)
        frontmatter, _body = parse_skill(skill_path)
        description = str(frontmatter["description"])
        assert description.startswith(opening)

        evals = json.loads((skill_path.parent / "evals/evals.json").read_text(encoding="utf-8"))
        case = next(item for item in evals["routing"] if item["id"] == case_id)
        assert case["prompt"] == prompt
        assert case["shouldTrigger"] is False

    error_path = next(path for path in SKILL_FILES if path.parent.name == "python-error-handling")
    error_evals = json.loads((error_path.parent / "evals/evals.json").read_text(encoding="utf-8"))
    http_case = next(
        item for item in error_evals["routing"] if item["id"] == "negative-http-errors"
    )
    assert http_case["shouldTrigger"] is False
    assert http_case["prompt"] == (
        "Design RFC-style HTTP error response bodies and status-code mapping for our FastAPI "
        "service."
    )
    error_description = str(parse_skill(error_path)[0]["description"])
    assert all(
        phrase not in error_description.lower() for phrase in ("http", "rpc", "message error")
    )


def test_python_release_guidance_rejects_unverified_commands() -> None:
    bodies = {
        skill: parse_skill(next(path for path in SKILL_FILES if path.parent.name == skill))[1]
        for skill in (
            "python-error-handling",
            "python-project-layout",
            "python-test-architecture",
        )
    }
    assert all("Never invent helper or tool flags." in body for body in bodies.values())
    assert (
        "the backend identifier is exactly `setuptools.build_meta`"
        in bodies["python-project-layout"]
    )
    assert (
        "cannot be verified before the package\n  sources actually move under `src/`"
        in bodies["python-project-layout"]
    )
    assert (
        "unsupported helper flags or an unverified plugin invocation"
        in bodies["python-test-architecture"]
    )


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
