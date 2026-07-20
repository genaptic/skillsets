from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from skillpack_tools.configure import configure_repository
from skillpack_tools.models import RepositoryConfig, load_repository
from skillpack_tools.util import dump_yaml
from skillpack_tools.validate import (
    MAX_SKILL_ASSET_JSON_BYTES,
    MAX_SKILL_ASSET_JSON_NESTING,
    _schema_errors,
    _validate_skill_asset_schemas,
)

ROOT = Path(__file__).resolve().parents[1]


def _repository_data() -> dict:
    return {
        "schema-version": 1,
        "project": {
            "name": "Fixture Skillsets",
            "description": "Portable fixture skills for repository contract tests.",
        },
        "repository": {
            "owner": "fixture-owner",
            "name": "fixture-skills",
            "default-branch": "main",
        },
        "publisher": {"name": "Fixture", "copyright-owner": "Fixture"},
        "maintainer": {"name": "Fixture Maintainer", "github": "fixture-maintainer"},
        "security": {"channel": "github-private-vulnerability-reporting"},
        "marketplace": {
            "name": "fixture-skillsets",
            "display-name": "Fixture Skillsets",
            "description": "Portable fixture skills for repository contract tests.",
        },
        "compatibility-evidence": {
            "max-age-days": 45,
            "future-skew-minutes": 5,
            "independent-review-required": False,
            "authorized-reviewers": [
                {
                    "github": "fixture-maintainer",
                    "github-id": 1,
                }
            ],
        },
        "release": {
            "license": "Apache-2.0",
            "initial-year": 2026,
            "trusted-signers": [
                {
                    "type": "ssh",
                    "github": "fixture-maintainer",
                    "fingerprint": "SHA256:RXn4sQSc9mwJb13oQVvUUkQvPw+B5N+WrRWH4elMJHg",
                }
            ],
        },
    }


def _schema_assets(root: Path) -> Path:
    assets = root / "packs/shared/fixture/skills/fixture-skill/assets"
    assets.mkdir(parents=True)
    return assets


def _schema(schema_id: str) -> dict:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": schema_id,
        "type": "object",
        "additionalProperties": False,
        "required": ["name", "source"],
        "properties": {
            "name": {"type": "string", "minLength": 3},
            "source": {
                "type": "string",
                "format": "uri",
                "pattern": r"^https?://(?![^/?#]*@)[^\s]+$",
            },
        },
    }


def _write_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _valid_contract_files(tmp_path: Path) -> tuple[RepositoryConfig, dict[str, Path]]:
    (tmp_path / "repository.yaml").write_text(dump_yaml(_repository_data()), encoding="utf-8")
    config = load_repository(tmp_path)
    assets = _schema_assets(tmp_path)
    schema_path = assets / "request.schema.json"
    schema_id = (
        "https://raw.githubusercontent.com/fixture-owner/fixture-skills/main/"
        "packs/shared/fixture/skills/fixture-skill/assets/request.schema.json"
    )
    paths = {
        "schema": schema_path,
        "template": assets / "request.template.json",
        "example": assets / "request.example.json",
    }
    _write_json(schema_path, _schema(schema_id))
    for kind in ("template", "example"):
        _write_json(
            paths[kind],
            {"name": kind, "source": f"https://example.com/{kind}"},
        )
    return config, paths


def test_skill_asset_schema_requires_canonical_identity_and_valid_schema(tmp_path: Path) -> None:
    (tmp_path / "repository.yaml").write_text(dump_yaml(_repository_data()), encoding="utf-8")
    config = load_repository(tmp_path)
    assets = _schema_assets(tmp_path)
    schema_path = assets / "request.schema.json"
    _write_json(schema_path, _schema("https://example.invalid/request.schema.json"))

    errors: list[str] = []
    _validate_skill_asset_schemas(tmp_path, config, errors)
    expected = (
        "https://raw.githubusercontent.com/fixture-owner/fixture-skills/main/"
        "packs/shared/fixture/skills/fixture-skill/assets/request.schema.json"
    )
    assert any(f"$id must be {expected!r}" in error for error in errors)

    invalid_schema = _schema(expected)
    invalid_schema["type"] = 42
    _write_json(schema_path, invalid_schema)
    errors = []
    _validate_skill_asset_schemas(tmp_path, config, errors)
    assert any("invalid JSON Schema" in error for error in errors)


def test_skill_asset_schema_validates_template_example_and_uri_formats(tmp_path: Path) -> None:
    (tmp_path / "repository.yaml").write_text(dump_yaml(_repository_data()), encoding="utf-8")
    config = load_repository(tmp_path)
    assets = _schema_assets(tmp_path)
    schema_path = assets / "request.schema.json"
    schema_id = (
        "https://raw.githubusercontent.com/fixture-owner/fixture-skills/main/"
        "packs/shared/fixture/skills/fixture-skill/assets/request.schema.json"
    )
    _write_json(schema_path, _schema(schema_id))
    _write_json(
        assets / "request.template.json",
        {"name": "ok", "source": "not a URI"},
    )
    _write_json(
        assets / "request.example.json",
        {"name": "example", "source": "https://user@example.com/private"},
    )

    errors: list[str] = []
    _validate_skill_asset_schemas(tmp_path, config, errors)
    joined = "\n".join(errors)
    assert "request.template.json:source" in joined
    assert "is not a 'uri'" in joined
    assert "request.example.json:source" in joined
    assert "does not match" in joined

    _write_json(
        assets / "request.template.json",
        {"name": "template", "source": "https://example.com/reference"},
    )
    _write_json(
        assets / "request.example.json",
        {"name": "example", "source": "http://example.org/reference"},
    )
    errors = []
    _validate_skill_asset_schemas(tmp_path, config, errors)
    assert errors == []


def test_configure_rewrites_nested_schema_ids_and_is_idempotent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / "schemas").mkdir()
    (tmp_path / "schemas/repository.schema.json").write_bytes(
        (ROOT / "schemas/repository.schema.json").read_bytes()
    )
    (tmp_path / "repository.yaml").write_text(dump_yaml(_repository_data()), encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nauthors = [{ name = "Fixture" }]\n',
        encoding="utf-8",
    )
    (tmp_path / ".env.example").write_text("PGHOST=localhost\n", encoding="utf-8")
    assets = _schema_assets(tmp_path)
    schema_path = assets / "request.schema.json"
    _write_json(schema_path, _schema("https://example.invalid/request.schema.json"))
    monkeypatch.setattr("skillpack_tools.configure.apply_generated_files", lambda _root: [])

    arguments = {
        "owner": "new-owner",
        "repository": "new-repository",
        "default_branch": "release/v2",
    }
    changed = configure_repository(tmp_path, **arguments)
    relative = schema_path.relative_to(tmp_path).as_posix()
    assert relative in changed
    assert json.loads(schema_path.read_text(encoding="utf-8"))["$id"] == (
        f"https://raw.githubusercontent.com/new-owner/new-repository/release/v2/{relative}"
    )
    assert "PGHOST=localhost" in (tmp_path / ".env.example").read_text(encoding="utf-8")
    assert configure_repository(tmp_path, **arguments) == []


def test_canonical_genaptic_skillsets_development_contracts_and_source_uris() -> None:
    errors: list[str] = []
    _validate_skill_asset_schemas(ROOT, load_repository(ROOT), errors)
    assert errors == []

    schema_paths = sorted(
        (ROOT / "packs/shared/genaptic-skillsets-development/skills").glob("*/assets/*.schema.json")
    )
    assert len(schema_paths) == 2
    for schema_path in schema_paths:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        example_path = schema_path.with_name(
            schema_path.name.replace(".schema.json", ".example.json")
        )
        example = json.loads(example_path.read_text(encoding="utf-8"))
        for unsafe_source in (
            "ftp://example.com/reference",
            "https://user@example.com/private",
        ):
            unsafe = deepcopy(example)
            unsafe["userSources"] = [unsafe_source]
            assert _schema_errors(unsafe, schema, example_path.as_posix())


@pytest.mark.parametrize("document_kind", ["schema", "template", "example"])
@pytest.mark.parametrize(
    ("fault", "expected_error"),
    [
        ("duplicate", "duplicate object key 'name'"),
        ("non-finite", "non-finite number '1e999' is not permitted"),
        ("utf-8", "Invalid UTF-8"),
        ("oversize", "exceeds the 1 MiB"),
        ("nesting", f"maximum of {MAX_SKILL_ASSET_JSON_NESTING} container levels"),
    ],
)
def test_contract_loader_rejects_unsafe_json_documents(
    tmp_path: Path,
    document_kind: str,
    fault: str,
    expected_error: str,
) -> None:
    config, paths = _valid_contract_files(tmp_path)
    if fault == "duplicate":
        invalid_content = b'{"name":"first","name":"second"}'
    elif fault == "non-finite":
        invalid_content = b'{"value":1e999}'
    elif fault == "utf-8":
        invalid_content = b'{"value":"\xff"}'
    elif fault == "oversize":
        invalid_content = b" " * (MAX_SKILL_ASSET_JSON_BYTES + 1)
    else:
        nested: object = "leaf"
        for _ in range(MAX_SKILL_ASSET_JSON_NESTING + 1):
            nested = [nested]
        invalid_content = json.dumps(nested).encode("utf-8")
    paths[document_kind].write_bytes(invalid_content)

    errors: list[str] = []
    _validate_skill_asset_schemas(tmp_path, config, errors)
    assert any(
        paths[document_kind].name in error and expected_error in error for error in errors
    ), errors


@pytest.mark.parametrize("constant", ["NaN", "Infinity", "-Infinity"])
def test_contract_loader_rejects_non_standard_numeric_constants(
    tmp_path: Path,
    constant: str,
) -> None:
    config, paths = _valid_contract_files(tmp_path)
    paths["template"].write_bytes(f'{{"value":{constant}}}'.encode("ascii"))

    errors: list[str] = []
    _validate_skill_asset_schemas(tmp_path, config, errors)
    assert any(
        paths["template"].name in error
        and f"non-finite number {constant!r} is not permitted" in error
        for error in errors
    ), errors
