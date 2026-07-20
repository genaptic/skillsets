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
