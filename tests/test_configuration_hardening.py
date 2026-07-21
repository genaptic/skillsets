from __future__ import annotations

import json
import re
import stat
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from skillpack_tools import cli
from skillpack_tools import schema_validation as schema_validation_module
from skillpack_tools.configure import configure_repository
from skillpack_tools.schema_validation import (
    MAX_SCHEMA_BYTES,
    format_checker,
    load_json_schema,
    schema_errors,
    validate_schema_instance,
)
from skillpack_tools.util import dump_yaml, load_yaml
from skillpack_tools.validate import validate_repository

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture()
def configuration_root(tmp_path: Path) -> Path:
    root = tmp_path / "repository"
    (root / "schemas").mkdir(parents=True)
    (root / "repository.yaml").write_bytes((ROOT / "repository.yaml").read_bytes())
    (root / "schemas/repository.schema.json").write_bytes(
        (ROOT / "schemas/repository.schema.json").read_bytes()
    )
    return root


def _snapshot(root: Path) -> dict[str, tuple[int, int, bytes | None]]:
    snapshot: dict[str, tuple[int, int, bytes | None]] = {}
    for path in sorted((root, *root.rglob("*"))):
        metadata = path.lstat()
        relative = "." if path == root else path.relative_to(root).as_posix()
        content = path.read_bytes() if stat.S_ISREG(metadata.st_mode) else None
        snapshot[relative] = (metadata.st_mode, metadata.st_mtime_ns, content)
    return snapshot


@pytest.mark.parametrize(
    ("arguments", "location"),
    [
        ({"owner": ""}, "repository.owner"),
        ({"project_name": "x"}, "project.name"),
        ({"project_name": "   "}, "project.name"),
        ({"project_description": "too short"}, "project.description"),
        ({"publisher_name": ""}, "publisher.name"),
        ({"publisher_name": "Bad\nPublisher"}, "publisher.name"),
        ({"maintainer_github": ""}, "maintainer.github"),
        ({"security_email": ""}, "security.email"),
        ({"security_email": "a@"}, "security.email"),
        ({"security_email": "@example.org"}, "security.email"),
        ({"security_email": "a b@example.org"}, "security.email"),
        ({"security_email": "a\nb@example.org"}, "security.email"),
        ({"security_email": "a\x00@example.org"}, "security.email"),
        ({"security_email": "a,b@example.org"}, "security.email"),
        ({"security_email": "a..b@example.org"}, "security.email"),
        ({"security_email": "a@-example.org"}, "security.email"),
        ({"security_email": "a@example-.org"}, "security.email"),
        ({"marketplace_name": "A"}, "marketplace.name"),
        ({"marketplace_display_name": "x"}, "marketplace.display-name"),
        ({"marketplace_description": "too short"}, "marketplace.description"),
        ({"license_id": "x"}, "release.license"),
        ({"license_id": "   "}, "release.license"),
        ({"initial_year": 0}, "release.initial-year"),
    ],
)
def test_configuration_rejects_explicit_invalid_values_before_writing(
    configuration_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    arguments: dict[str, Any],
    location: str,
) -> None:
    def unexpected_generation(_root: Path) -> list[str]:
        raise AssertionError("generation must not run for invalid configuration")

    monkeypatch.setattr(
        "skillpack_tools.configure.apply_generated_files",
        unexpected_generation,
    )
    before = _snapshot(configuration_root)
    with pytest.raises(ValueError, match=location.replace(".", r"\.")):
        configure_repository(configuration_root, **arguments)
    assert _snapshot(configuration_root) == before


def test_configuration_preserves_unknown_fields_for_schema_rejection(
    configuration_root: Path,
) -> None:
    path = configuration_root / "repository.yaml"
    data = load_yaml(path)
    data["repository"]["unexpected"] = True
    path.write_text(dump_yaml(data), encoding="utf-8")
    before = _snapshot(configuration_root)

    with pytest.raises(ValueError, match=re.escape("repository.yaml:repository")):
        configure_repository(configuration_root)

    assert _snapshot(configuration_root) == before


def test_configuration_does_not_coerce_invalid_existing_values(
    configuration_root: Path,
) -> None:
    path = configuration_root / "repository.yaml"
    data = load_yaml(path)
    data["repository"]["owner"] = 123
    path.write_text(dump_yaml(data), encoding="utf-8")
    before = _snapshot(configuration_root)

    with pytest.raises(ValueError, match=r"repository\.yaml:repository\.owner"):
        configure_repository(configuration_root)

    assert _snapshot(configuration_root) == before


@pytest.mark.parametrize(
    ("section", "value"),
    [
        ("project", None),
        ("publisher", []),
        ("security", "private"),
        ("marketplace", 42),
    ],
)
def test_configuration_rejects_missing_or_wrong_type_sections_before_indexing(
    configuration_root: Path,
    section: str,
    value: object,
) -> None:
    path = configuration_root / "repository.yaml"
    data = load_yaml(path)
    if value is None:
        data.pop(section)
    else:
        data[section] = value
    path.write_text(dump_yaml(data), encoding="utf-8")
    before = _snapshot(configuration_root)

    with pytest.raises(ValueError, match=re.escape("repository.yaml")):
        configure_repository(configuration_root)

    assert _snapshot(configuration_root) == before


@pytest.mark.parametrize(
    "schema_text",
    [
        "{not-json\n",
        json.dumps({"$schema": "https://json-schema.org/draft/2020-12/schema", "type": 7}),
        '{"type": 7, "type": "object"}',
        '{"const": NaN}',
        '{"const": Infinity}',
    ],
)
def test_configuration_rejects_malformed_or_invalid_schema_before_writing(
    configuration_root: Path,
    schema_text: str,
) -> None:
    schema_path = configuration_root / "schemas/repository.schema.json"
    schema_path.write_text(schema_text, encoding="utf-8")
    before = _snapshot(configuration_root)

    with pytest.raises(ValueError, match=re.escape("schemas/repository.schema.json")):
        configure_repository(configuration_root)

    assert _snapshot(configuration_root) == before


def test_configuration_rejects_oversized_or_overdeep_schema_before_writing(
    configuration_root: Path,
) -> None:
    schema_path = configuration_root / "schemas/repository.schema.json"
    overdeep: object = {}
    for _ in range(70):
        overdeep = [overdeep]
    for schema_text in (
        '{"description":"' + ("x" * MAX_SCHEMA_BYTES) + '"}',
        json.dumps({"allOf": overdeep}),
    ):
        schema_path.write_text(schema_text, encoding="utf-8")
        before = _snapshot(configuration_root)
        with pytest.raises(ValueError, match=re.escape("schemas/repository.schema.json")):
            configure_repository(configuration_root)
        assert _snapshot(configuration_root) == before


def test_format_checker_overrides_ambient_uri_and_email_behavior(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ambient = schema_validation_module.FormatChecker()
    ambient.checkers["uri"] = (lambda _value: True, ())
    ambient.checkers["email"] = (lambda _value: True, ())
    monkeypatch.setattr(schema_validation_module, "FormatChecker", lambda: ambient)

    checker = format_checker()
    assert checker.conforms("https://example.org/reference", "uri")
    assert not checker.conforms("not a URI", "uri")
    assert checker.conforms("security@example.org", "email")
    assert not checker.conforms("a@", "email")
    assert not checker.conforms("a b@example.org", "email")
    assert not checker.conforms("a\x00@example.org", "email")
    assert not checker.conforms("a,b@example.org", "email")
    assert not checker.conforms("a..b@example.org", "email")
    assert not checker.conforms("a@-example.org", "email")


@pytest.mark.parametrize(
    "branch",
    [
        "main",
        "release/v2",
        "feature/foo-bar_1.2",
        "foo/-bar",
        "a" * 100,
    ],
)
def test_repository_schema_accepts_portable_git_branches(branch: str) -> None:
    schema = load_json_schema(ROOT / "schemas/repository.schema.json")
    candidate = deepcopy(load_yaml(ROOT / "repository.yaml"))
    candidate["repository"]["default-branch"] = branch
    assert schema_errors(candidate, schema, "repository.yaml") == []


@pytest.mark.parametrize(
    "branch",
    [
        ".",
        "..",
        ".hidden",
        "topic/.hidden",
        "/main",
        "main/",
        "main//x",
        "topic..name",
        "topic.lock",
        "topic/foo.lock",
        "main.",
        "-main",
        "HEAD",
        "main\n",
        "main\x00",
        "main\x7f",
        "a" * 101,
    ],
)
def test_repository_schema_rejects_invalid_git_branches(branch: str) -> None:
    schema = load_json_schema(ROOT / "schemas/repository.schema.json")
    candidate = deepcopy(load_yaml(ROOT / "repository.yaml"))
    candidate["repository"]["default-branch"] = branch
    errors = schema_errors(candidate, schema, "repository.yaml")
    assert any("repository.default-branch" in error for error in errors)


def test_schema_errors_are_stable_and_path_qualified() -> None:
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "additionalProperties": False,
        "required": ["alpha", "omega"],
        "properties": {
            "alpha": {"type": "string", "minLength": 3},
            "omega": {"type": "integer", "minimum": 1},
        },
    }
    errors = schema_errors({"alpha": "x", "extra": True, "omega": 0}, schema, "config")
    assert errors == schema_errors({"alpha": "x", "extra": True, "omega": 0}, schema, "config")
    assert errors[0].startswith("config:<root>:")
    assert any(error.startswith("config:alpha:") for error in errors)
    assert any(error.startswith("config:omega:") for error in errors)
    with pytest.raises(ValueError, match="configuration validation failed"):
        validate_schema_instance(
            {"alpha": "x", "extra": True, "omega": 0},
            schema,
            label="config",
        )


def test_configure_cli_reports_schema_failure_without_writing(
    configuration_root: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    before = _snapshot(configuration_root)
    result = cli.main(
        [
            "--root",
            str(configuration_root),
            "configure",
            "--project-description",
            "short",
        ]
    )
    captured = capsys.readouterr()
    assert result == 1
    assert "repository.yaml:project.description" in captured.err
    assert _snapshot(configuration_root) == before


@pytest.mark.parametrize(("section", "value"), [("repository", None), ("project", [])])
def test_repository_validation_returns_schema_errors_for_malformed_sections(
    tmp_path: Path,
    section: str,
    value: object,
) -> None:
    repository = tmp_path / "repository"
    (repository / "schemas").mkdir(parents=True)
    (repository / ".github/workflows").mkdir(parents=True)
    data = deepcopy(load_yaml(ROOT / "repository.yaml"))
    if value is None:
        data.pop(section)
    else:
        data[section] = value
    (repository / "repository.yaml").write_text(dump_yaml(data), encoding="utf-8")
    for schema in ROOT.joinpath("schemas").glob("*.schema.json"):
        (repository / "schemas" / schema.name).write_bytes(schema.read_bytes())
    (repository / ".github/workflows/validate.yml").write_text(
        "name: validate\npermissions:\n  contents: read\n",
        encoding="utf-8",
    )

    result = validate_repository(repository)

    assert not result.ok
    assert any("repository.yaml" in error for error in result.errors)
