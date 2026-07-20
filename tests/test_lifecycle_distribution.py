from __future__ import annotations

import json
import re
import shutil
import subprocess
from copy import deepcopy
from html import escape as html_escape
from pathlib import Path, PurePosixPath, PureWindowsPath

import pytest
import yaml
from jsonschema import Draft202012Validator

from skillpack_tools.generate import (
    _skill_relative_posix,
    apply_generated_files,
    build_generated_files,
)
from skillpack_tools.lifecycle import (
    pages_absent_paths,
    select_packs,
    semantic_version_key,
    validate_pack_lifecycle,
)
from skillpack_tools.models import Pack, discover_packs, get_pack
from skillpack_tools.validate import _validate_vendor_artifact_structure

ROOT = Path(__file__).resolve().parents[1]


EXPECTED_SHORT_DESCRIPTIONS = {
    "python-best-practices": "Structure, test, and harden production Python projects.",
    "python-cli-apps": "Design and test reliable Python command-line interfaces.",
    "rust-best-practices": "Design, review, and maintain repository-aware Rust systems.",
    "rust-cli-apps": "Design portable Rust CLIs and evolve commands safely.",
    "postgres-databases": "Design and review safe, evidence-backed PostgreSQL changes.",
    "genaptic-skillsets-development": (
        "Author and validate skills and skillpacks for genaptic/skillsets."
    ),
}


@pytest.mark.parametrize(
    "version",
    ["1.0.0-01", "1.0.0-alpha..1", "1.0.0-.", "1.0.0+build..x"],
)
def test_semantic_versions_reject_invalid_identifiers_everywhere(version: str) -> None:
    with pytest.raises(ValueError, match="Invalid Semantic Version"):
        semantic_version_key(version)

    schema_patterns = [
        json.loads((ROOT / "schemas/skillpack.schema.json").read_text(encoding="utf-8"))["$defs"][
            "semantic-version"
        ]["pattern"],
        json.loads((ROOT / "schemas/publication-record.schema.json").read_text(encoding="utf-8"))[
            "properties"
        ]["version"]["pattern"],
        json.loads((ROOT / "schemas/release-metadata.schema.json").read_text(encoding="utf-8"))[
            "$defs"
        ]["semver"]["pattern"],
        json.loads((ROOT / "schemas/catalog.schema.json").read_text(encoding="utf-8"))["$defs"][
            "semantic-version"
        ]["pattern"],
        json.loads((ROOT / "schemas/compatibility-report.schema.json").read_text(encoding="utf-8"))[
            "properties"
        ]["pack"]["properties"]["version"]["pattern"],
    ]
    assert all(re.fullmatch(pattern, version) is None for pattern in schema_patterns)


@pytest.mark.parametrize(
    "version",
    ["0.0.0", "1.2.3-alpha.1", "1.2.3-0A.-", "1.2.3+build.007"],
)
def test_semantic_versions_accept_valid_identifiers(version: str) -> None:
    semantic_version_key(version)


def _copy_repository(tmp_path: Path, *, stable_packs: tuple[str, ...] = ()) -> Path:
    target = tmp_path / "repository"
    shutil.copytree(
        ROOT,
        target,
        ignore=shutil.ignore_patterns(".git", ".venv", ".pytest_cache", "__pycache__"),
    )
    for pack_id in stable_packs:
        _set_lifecycle(target, pack_id, maturity="stable")
    subprocess.run(["git", "init", "-q", str(target)], check=True)
    subprocess.run(["git", "-C", str(target), "config", "user.name", "Fixture"], check=True)
    subprocess.run(
        ["git", "-C", str(target), "config", "user.email", "fixture@example.invalid"],
        check=True,
    )
    subprocess.run(["git", "-C", str(target), "add", "packs"], check=True)
    subprocess.run(
        ["git", "-C", str(target), "commit", "-q", "--no-gpg-sign", "-m", "fixture"],
        check=True,
    )
    return target


def _set_lifecycle(root: Path, pack_id: str, **values: object) -> None:
    pack = get_pack(root, pack_id)
    path = pack.path / "skillpack.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    for key, value in values.items():
        if key == "visibility":
            data["distribution"]["visibility"] = value
        elif key == "state":
            data["publication"]["state"] = value
        elif key == "latest_release":
            if value is None:
                data["publication"].pop("latest-release", None)
            else:
                data["publication"]["latest-release"] = value
        else:
            data[key.replace("_", "-")] = value
    path.write_text(yaml.safe_dump(data, sort_keys=False, width=1000), encoding="utf-8")


def _release(root: Path, version: str = "1.0.0") -> dict[str, object]:
    source_sha = subprocess.check_output(
        ["git", "-C", str(root), "rev-parse", "HEAD"], text=True
    ).strip()
    return {
        "version": version,
        "source-sha": source_sha,
        "release-id": 123456,
        "released-at": "2026-07-19T18:30:00Z",
    }


def test_current_repository_has_empty_public_and_isolated_preview_development() -> None:
    packs = discover_packs(ROOT)
    generated = build_generated_files(ROOT)

    assert select_packs(packs, "public") == []
    assert len(select_packs(packs, "preview")) == 5
    assert len(select_packs(packs, "development")) == 6
    assert json.loads(generated["catalog.json"])["packs"] == []
    assert json.loads(generated[".claude-plugin/marketplace.json"])["plugins"] == []
    assert json.loads(generated[".agents/plugins/marketplace.json"])["plugins"] == []
    assert {path for path in generated if path.startswith("dist/public/")} == {
        "dist/public/index.html"
    }
    assert "No stable releases are currently published" in generated["dist/public/index.html"]

    preview_ids = {
        item["id"] for item in json.loads(generated["dist/preview/catalog.json"])["packs"]
    }
    development_ids = {
        item["id"] for item in json.loads(generated["dist/dev/catalog.json"])["packs"]
    }
    maintainer = next(pack for pack in packs if pack.visibility == "maintainers")
    assert maintainer.id not in preview_ids
    assert maintainer.id in development_ids
    assert all(maintainer.id not in path for path in generated if path.startswith("dist/public/"))

    public_text = "\n".join(
        content
        for path, content in generated.items()
        if path.startswith("dist/public/") and isinstance(content, str)
    )
    for pack in packs:
        assert pack.id not in public_text


def test_pages_legacy_denylist_excludes_a_newly_published_pack() -> None:
    packs = discover_packs(ROOT)
    canary = get_pack(ROOT, "python-best-practices")
    raw = deepcopy(canary.raw)
    raw["maturity"] = "stable"
    raw["publication"] = {
        "state": "published",
        "latest-release": {
            "version": canary.version,
            "source-sha": "a" * 40,
            "release-id": 1,
            "released-at": "2026-07-19T18:30:00Z",
        },
    }
    published = Pack(root=canary.root, path=canary.path, raw=raw)
    packs = [published if pack.id == canary.id else pack for pack in packs]
    legacy = json.loads(
        (ROOT / "tests/fixtures/pages-legacy-public-urls-v1.json").read_text(encoding="utf-8")
    )
    absent = pages_absent_paths(packs, legacy["paths"])
    assert "install/python-best-practices.sh" not in absent
    assert "install/python-best-practices.ps1" not in absent
    assert "opencode/python/best-practices/index.json" not in absent
    assert "install/python-cli-apps.sh" in absent
    assert "install/repository-development.sh" in absent
    assert "opencode/shared/repository-development/index.json" in absent


@pytest.mark.parametrize("path_type", [PurePosixPath, PureWindowsPath])
def test_skill_resource_order_is_independent_of_path_flavor(
    path_type: type[PurePosixPath] | type[PureWindowsPath],
) -> None:
    skill_dir = path_type("skills/rust-project-architecture")
    resources = [
        skill_dir / "assets/templates/workspace-root/apps/tool/Cargo.toml",
        skill_dir / "assets/templates/workspace-root/Cargo.toml",
    ]

    ordered = sorted(
        resources,
        key=lambda resource: _skill_relative_posix(resource, skill_dir),
    )

    assert [resource.relative_to(skill_dir).as_posix() for resource in ordered] == [
        "assets/templates/workspace-root/Cargo.toml",
        "assets/templates/workspace-root/apps/tool/Cargo.toml",
    ]


def test_opencode_v1_18_3_protocol_and_self_contained_marketplaces() -> None:
    protocol = json.loads(
        (ROOT / "tests/fixtures/opencode-v1.18.3-protocol.json").read_text(encoding="utf-8")
    )
    generated = build_generated_files(ROOT)
    assert protocol["configuration"] == {
        "skills": {"urls": ["https://example.invalid/opencode/python/best-practices/"]}
    }

    for pack in select_packs(discover_packs(ROOT), "development"):
        if "opencode" not in pack.targets:
            continue
        base = f"dist/dev/opencode/{pack.language}/{pack.subject}"
        index = json.loads(generated[f"{base}/index.json"])
        assert [entry["name"] for entry in index["skills"]] == pack.skills
        for entry in index["skills"]:
            assert sorted(entry) == protocol["indexEntryKeys"]
            assert entry["files"][0] == protocol["requiredSkillFile"]
            assert entry["files"][1:] == sorted(entry["files"][1:])
            for relative in entry["files"]:
                assert f"{base}/{entry['name']}/{relative}" in generated
            assert not any(relative.endswith(f"{entry['name']}.md") for relative in entry["files"])
            if pack.id == "rust-best-practices" and entry["name"] == "rust-project-architecture":
                root_manifest = "assets/templates/workspace-root/Cargo.toml"
                nested_manifest = "assets/templates/workspace-root/apps/tool/Cargo.toml"
                assert entry["files"].index(root_manifest) < entry["files"].index(nested_manifest)

    for channel in ("preview", "dev"):
        for client, marketplace_suffix in (
            ("claude", ".claude-plugin/marketplace.json"),
            ("codex", ".agents/plugins/marketplace.json"),
        ):
            marketplace_path = f"dist/{channel}/{client}/{marketplace_suffix}"
            marketplace = json.loads(generated[marketplace_path])
            for entry in marketplace["plugins"]:
                source = entry["source"]
                assert source == f"./plugins/{entry['name']}"
                assert ".." not in Path(source).parts
                plugin_suffix = (
                    ".claude-plugin/plugin.json"
                    if client == "claude"
                    else ".codex-plugin/plugin.json"
                )
                assert (
                    f"dist/{channel}/{client}/plugins/{entry['name']}/{plugin_suffix}" in generated
                )

    for relative in generated:
        path = Path(relative)
        assert not path.is_absolute()
        assert ".." not in path.parts


def test_published_old_release_survives_new_candidate_and_withdrawal(tmp_path: Path) -> None:
    root = _copy_repository(tmp_path, stable_packs=("python-best-practices",))
    skill_path = root / "packs/python/best-practices/skills/python-project-layout/SKILL.md"
    released_skill = skill_path.read_bytes()
    skill_path.write_bytes(released_skill + b"\nCandidate-only guidance.\n")
    _set_lifecycle(
        root,
        "python-best-practices",
        version="1.0.1",
        maturity="release-candidate",
        state="published",
        latest_release=_release(root),
    )
    generated = build_generated_files(root)
    public = json.loads(generated["catalog.json"])["packs"]
    preview = json.loads(generated["dist/preview/catalog.json"])["packs"]
    development = json.loads(generated["dist/dev/catalog.json"])["packs"]
    assert [(item["id"], item["version"]) for item in public] == [
        ("python-best-practices", "1.0.0")
    ]
    assert (
        next(item for item in preview if item["id"] == "python-best-practices")["version"]
        == "1.0.1"
    )
    assert (
        next(item for item in development if item["id"] == "python-best-practices")["version"]
        == "1.0.1"
    )
    assert "dist/public/install/python-best-practices.sh" in generated
    index = json.loads(generated["dist/public/opencode/python/best-practices/index.json"])
    assert {entry["version"] for entry in index["skills"]} == {"1.0.0"}
    assert (
        generated["dist/public/opencode/python/best-practices/python-project-layout/SKILL.md"]
        == released_skill
    )
    assert (
        b"Candidate-only guidance"
        in generated["dist/preview/opencode/python/best-practices/python-project-layout/SKILL.md"]
    )
    page = generated["dist/public/index.html"]
    assert EXPECTED_SHORT_DESCRIPTIONS["python-best-practices"] in page
    assert get_pack(root, "python-best-practices").description not in page
    tag = "python-best-practices-v1.0.0"
    source_sha = _release(root)["source-sha"]
    repository_url = "https://github.com/genaptic/skillsets"
    for url in (
        f"{repository_url}/releases/tag/{tag}",
        f"{repository_url}/commit/{source_sha}",
        f"{repository_url}/releases/download/{tag}/{tag}.zip.sha256",
        f"{repository_url}/attestations",
    ):
        assert f'href="{url}"' in page

    _set_lifecycle(root, "python-best-practices", state="withdrawn")
    withdrawn = build_generated_files(root)
    for catalog_path in ("catalog.json", "dist/preview/catalog.json", "dist/dev/catalog.json"):
        assert "python-best-practices" not in {
            item["id"] for item in json.loads(withdrawn[catalog_path])["packs"]
        }
    assert not any(
        "python-best-practices" in path for path in withdrawn if path.startswith("dist/public/")
    )


def test_mixed_publication_membership_excludes_unpublished_withdrawn_and_maintainers(
    tmp_path: Path,
) -> None:
    root = _copy_repository(
        tmp_path,
        stable_packs=("python-best-practices", "python-cli-apps"),
    )
    release = _release(root)
    for pack_id in ("python-best-practices", "python-cli-apps"):
        _set_lifecycle(
            root,
            pack_id,
            maturity="stable",
            state="published",
            latest_release=release,
        )
    _set_lifecycle(root, "python-cli-apps", state="withdrawn")

    packs = discover_packs(root)
    generated = build_generated_files(root)
    public_ids = {item["id"] for item in json.loads(generated["catalog.json"])["packs"]}
    assert public_ids == {"python-best-practices"}
    assert {
        entry["name"]
        for entry in json.loads(generated[".claude-plugin/marketplace.json"])["plugins"]
    } == public_ids
    assert {
        entry["name"]
        for entry in json.loads(generated[".agents/plugins/marketplace.json"])["plugins"]
    } == public_ids

    public_paths = {path for path in generated if path.startswith("dist/public/")}
    assert "dist/public/install/python-best-practices.sh" in public_paths
    assert "dist/public/opencode/python/best-practices/index.json" in public_paths
    excluded = {pack.id for pack in packs} - public_ids
    public_text = "\n".join(
        content
        for path, content in generated.items()
        if path.startswith("dist/public/") and isinstance(content, str)
    )
    for pack_id in excluded:
        assert all(pack_id not in path for path in public_paths)
        assert pack_id not in public_text

    development_ids = {
        item["id"] for item in json.loads(generated["dist/dev/catalog.json"])["packs"]
    }
    assert "genaptic-skillsets-development" in development_ids
    assert "python-cli-apps" not in development_ids


def test_published_pages_card_escapes_released_metadata(tmp_path: Path) -> None:
    root = _copy_repository(tmp_path, stable_packs=("python-best-practices",))
    pack = get_pack(root, "python-best-practices")
    manifest_path = pack.path / "skillpack.yaml"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    display_name = '<img src="x" onerror="pack">'
    short_description = 'Review <strong>Python</strong> & "quoted" systems safely.'
    target = 'target<script>alert("target")</script>'
    manifest["display-name"] = display_name
    manifest["interface"]["short-description"] = short_description
    manifest["targets"].append(target)
    manifest_path.write_text(
        yaml.safe_dump(manifest, sort_keys=False, width=1000), encoding="utf-8"
    )
    subprocess.run(["git", "-C", str(root), "add", "packs"], check=True)
    subprocess.run(
        ["git", "-C", str(root), "commit", "-q", "--no-gpg-sign", "-m", "released metadata"],
        check=True,
    )
    _set_lifecycle(
        root,
        "python-best-practices",
        maturity="stable",
        state="published",
        latest_release=_release(root),
    )

    page = build_generated_files(root)["dist/public/index.html"]
    for value in (display_name, short_description, target):
        assert html_escape(value) in page
    assert "<script>" not in page
    assert "<img " not in page


def test_interface_metadata_is_authored_consistent_and_mapped_to_clients() -> None:
    generated = build_generated_files(ROOT)
    for pack in discover_packs(ROOT):
        assert pack.short_description == EXPECTED_SHORT_DESCRIPTIONS[pack.id]
        assert 25 <= len(pack.short_description) <= 120
        assert 2 <= len(pack.starter_prompts) <= 4
        assert len({item["prompt"] for item in pack.starter_prompts}) == len(pack.starter_prompts)

        sidecar_prompts: dict[str, str] = {}
        for item in pack.starter_prompts:
            sidecar = yaml.safe_load(
                (pack.path / "skills" / item["skill"] / "agents" / "openai.yaml").read_text(
                    encoding="utf-8"
                )
            )
            sidecar_prompts[item["skill"]] = sidecar["interface"]["default_prompt"]
        assert [item["prompt"] for item in pack.starter_prompts] == [
            sidecar_prompts[item["skill"]] for item in pack.starter_prompts
        ]

        claude = json.loads(generated[f"{pack.relative_path}/.claude-plugin/plugin.json"])
        codex = json.loads(generated[f"{pack.relative_path}/.codex-plugin/plugin.json"])
        assert claude["description"] == pack.short_description
        assert codex["interface"]["shortDescription"] == pack.short_description
        assert codex["interface"]["longDescription"] == pack.description
        assert codex["interface"]["defaultPrompt"] == [
            item["prompt"] for item in pack.starter_prompts
        ]


def test_interface_policy_rejects_duplicate_and_boilerplate_prompts() -> None:
    pack = get_pack(ROOT, "python-best-practices")
    invalid = deepcopy(pack.raw)
    invalid["interface"]["starter-prompts"][1]["prompt"] = invalid["interface"]["starter-prompts"][
        0
    ]["prompt"]
    duplicate = type(pack)(root=pack.root, path=pack.path, raw=invalid)
    assert any(
        "prompt text must be unique" in error for error in validate_pack_lifecycle(duplicate)
    )

    invalid = deepcopy(pack.raw)
    invalid["interface"]["starter-prompts"][0]["prompt"] = (
        "Use $python-project-layout to replace with placeholder content."
    )
    boilerplate = type(pack)(root=pack.root, path=pack.path, raw=invalid)
    assert any("contains boilerplate" in error for error in validate_pack_lifecycle(boilerplate))

    invalid = deepcopy(pack.raw)
    invalid["interface"]["short-description"] = (
        "This deliberately reaches an interface boundary without sentence punctuation"
    )
    fragment = type(pack)(root=pack.root, path=pack.path, raw=invalid)
    assert any("truncated fragments" in error for error in validate_pack_lifecycle(fragment))


def test_vendor_validation_rejects_presentation_metadata_drift(tmp_path: Path) -> None:
    root = _copy_repository(tmp_path)
    apply_generated_files(root)
    pack = get_pack(root, "python-best-practices")
    path = pack.path / ".codex-plugin/plugin.json"
    plugin = json.loads(path.read_text(encoding="utf-8"))
    plugin["interface"]["shortDescription"] = "Structure, test, and harden production Python proj"
    plugin["interface"]["defaultPrompt"] = ["Placeholder starter prompt"]
    path.write_text(json.dumps(plugin), encoding="utf-8")

    errors: list[str] = []
    _validate_vendor_artifact_structure(root, discover_packs(root), errors)
    assert any("interface.shortDescription" in error for error in errors)
    assert any("interface.defaultPrompt" in error for error in errors)


def test_codex_short_description_fallback_never_slices_a_word(tmp_path: Path) -> None:
    root = _copy_repository(tmp_path)
    pack = get_pack(root, "python-best-practices")
    manifest_path = pack.path / "skillpack.yaml"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    words = [
        "Review",
        "production",
        "Python",
        "architecture",
        "with",
        "careful",
        "packaging",
        "testing",
        "failure",
        "boundaries",
        "portability",
        "maintenance",
        "and",
        "operational",
        "safeguards",
    ]
    authored = " ".join(words)
    assert len(authored) > 120
    manifest["interface"]["short-description"] = authored
    manifest_path.write_text(
        yaml.safe_dump(manifest, sort_keys=False, width=1000),
        encoding="utf-8",
    )

    plugin = json.loads(
        build_generated_files(root)["packs/python/best-practices/.codex-plugin/plugin.json"]
    )
    rendered = plugin["interface"]["shortDescription"]
    assert len(rendered) <= 120
    assert rendered.endswith("…")
    whole_word_prefixes = {" ".join(words[:index]) for index in range(1, len(words) + 1)}
    assert rendered.removesuffix("…") in whole_word_prefixes


def test_manifest_v2_schema_and_cross_field_lifecycle_fail_closed(tmp_path: Path) -> None:
    schema = json.loads((ROOT / "schemas/skillpack.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    pack = get_pack(ROOT, "python-best-practices")
    assert list(Draft202012Validator(schema).iter_errors(pack.raw)) == []
    assert validate_pack_lifecycle(pack) == []

    invalid = json.loads(json.dumps(pack.raw))
    invalid["publication"] = {"state": "published"}
    assert list(Draft202012Validator(schema).iter_errors(invalid))

    invalid = json.loads(json.dumps(pack.raw))
    invalid["release-gates"] = ["deterministic-archive", "native-evidence"]
    assert list(Draft202012Validator(schema).iter_errors(invalid))
