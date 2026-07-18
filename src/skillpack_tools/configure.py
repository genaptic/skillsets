from __future__ import annotations

import json
import os
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

from .generate import apply_generated_files
from .models import discover_packs
from .schema_validation import load_json_schema, validate_schema_instance
from .util import atomic_write, dump_yaml, load_yaml

PLACEHOLDER_GITHUB = "your-github-handle"
PLACEHOLDER_NAME = "Your Name"
PLACEHOLDER_EMAIL = "security@example.com"
GITHUB_PRIVATE_REPORTING = "github-private-vulnerability-reporting"
IDENTITY_TEXT_SURFACES = (
    "README.md",
    "CHANGELOG.md",
    "SECURITY.md",
    "SUPPORT.md",
    "CODE_OF_CONDUCT.md",
    "AGENTS.md",
    "COMPATIBILITY.md",
    "CONTRIBUTING.md",
    "GOVERNANCE.md",
    "REPOSITORY_SETUP.md",
    ".github/ISSUE_TEMPLATE/config.yml",
    "docs/architecture.md",
    "docs/authoring.md",
    "docs/distribution.md",
    "docs/evals.md",
    "docs/github-pages.md",
    "docs/maintainer-signing.md",
    "docs/release-process.md",
    "docs/solo-maintainer-governance.md",
    "docs/threat-model.md",
    "schemas/repository.schema.json",
    "schemas/skillpack.schema.json",
    "schemas/evals.schema.json",
    "schemas/catalog.schema.json",
    "schemas/generated-files.schema.json",
    "schemas/eval-report.schema.json",
    "schemas/compatibility-report.schema.json",
)


def _write_if_changed(root: Path, relative: str, content: str, changed: list[str]) -> None:
    path = root / relative
    current = path.read_text(encoding="utf-8") if path.is_file() else None
    if current != content:
        atomic_write(path, content)
        changed.append(relative)


def _replace_placeholder_maintainers(data: dict[str, Any], github: str) -> bool:
    maintainers = data.get("maintainers")
    if not isinstance(maintainers, list):
        return False
    replaced = False
    for item in maintainers:
        if isinstance(item, dict) and item.get("github") != github:
            item["github"] = github
            replaced = True
    return replaced


def _rewrite_skill_asset_schema_ids(
    root: Path,
    *,
    owner: str,
    repository: str,
    default_branch: str,
    changed: list[str],
) -> None:
    """Derive every canonical skill asset schema ID from repository identity."""

    for path in sorted(root.glob("packs/**/skills/*/assets/*.schema.json")):
        if path.is_symlink():
            raise ValueError(f"skill asset schema must not be a symlink: {path.relative_to(root)}")
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"invalid JSON schema in {relative}: {exc}") from exc
        if not isinstance(data, dict):
            raise ValueError(f"skill asset schema must be a JSON object: {relative}")
        expected_id = (
            f"https://raw.githubusercontent.com/{owner}/{repository}/{default_branch}/{relative}"
        )
        if data.get("$id") != expected_id:
            data["$id"] = expected_id
            _write_if_changed(
                root,
                relative,
                json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                changed,
            )


def configure_repository(
    root: Path,
    *,
    owner: str | None = None,
    repository: str | None = None,
    project_name: str | None = None,
    project_description: str | None = None,
    default_branch: str | None = None,
    publisher_name: str | None = None,
    copyright_owner: str | None = None,
    maintainer_name: str | None = None,
    maintainer_github: str | None = None,
    security_channel: str | None = None,
    security_email: str | None = None,
    marketplace_name: str | None = None,
    marketplace_display_name: str | None = None,
    marketplace_description: str | None = None,
    license_id: str | None = None,
    initial_year: int | None = None,
) -> list[str]:
    """Update canonical identity and regenerate all client-facing artifacts.

    The command deliberately does not add an optional ``source-sha``. A commit cannot
    contain its own identifier, so immutable SHA catalog pins are added only in a
    post-release marketplace update that points back to the already tagged commit.
    """

    root = Path(os.path.abspath(os.fspath(root)))
    data = load_yaml(root / "repository.yaml")
    schema = load_json_schema(
        root / "schemas" / "repository.schema.json",
        label="schemas/repository.schema.json",
        root=root,
    )
    # Reject malformed current configuration before indexing required sections. This keeps
    # every failure path deterministic and read-only instead of leaking KeyError/TypeError.
    validate_schema_instance(data, schema, label="repository.yaml")
    current_project = data.get("project", {})
    current_publisher = data.get("publisher", {})
    current_security = data.get("security", {})
    old_project_name = str(current_project.get("name", "Agent Skillpacks"))
    old_project_description = str(
        current_project.get("description", data["marketplace"]["description"])
    )
    old_owner = str(data["repository"]["owner"])
    old_repository = str(data["repository"]["name"])
    old_branch = str(data["repository"]["default-branch"])
    old_slug = f"{old_owner}/{old_repository}"
    old_publisher = str(current_publisher.get("name", data["maintainer"]["name"]))
    old_maintainer = str(data["maintainer"]["name"])
    old_github = str(data["maintainer"]["github"])
    old_marketplace = str(data["marketplace"]["name"])

    owner = data["repository"]["owner"] if owner is None else owner
    repository = data["repository"]["name"] if repository is None else repository
    project_name = (
        current_project.get("name", "Genaptic Skillsets") if project_name is None else project_name
    )
    project_description = (
        current_project.get("description", data["marketplace"]["description"])
        if project_description is None
        else project_description
    )
    default_branch = (
        data["repository"]["default-branch"] if default_branch is None else default_branch
    )
    maintainer_name = data["maintainer"]["name"] if maintainer_name is None else maintainer_name
    maintainer_github = (
        data["maintainer"]["github"] if maintainer_github is None else maintainer_github
    )
    publisher_name = (
        current_publisher.get("name", maintainer_name) if publisher_name is None else publisher_name
    )
    copyright_owner = (
        current_publisher.get("copyright-owner", publisher_name)
        if copyright_owner is None
        else copyright_owner
    )
    security_channel = (
        current_security.get("channel", GITHUB_PRIVATE_REPORTING)
        if security_channel is None
        else security_channel
    )
    if security_email is None:
        if "email" in current_security:
            security_email = current_security["email"]
        else:
            security_email = data.get("maintainer", {}).get("security-email")
    marketplace_name = data["marketplace"]["name"] if marketplace_name is None else marketplace_name
    marketplace_display_name = (
        data["marketplace"]["display-name"]
        if marketplace_display_name is None
        else marketplace_display_name
    )
    marketplace_description = (
        data["marketplace"]["description"]
        if marketplace_description is None
        else marketplace_description
    )
    license_id = data["release"]["license"] if license_id is None else license_id
    initial_year = data["release"]["initial-year"] if initial_year is None else initial_year

    candidate = deepcopy(data)
    candidate["project"]["name"] = project_name
    candidate["project"]["description"] = project_description
    candidate["repository"]["owner"] = owner
    candidate["repository"]["name"] = repository
    candidate["repository"]["default-branch"] = default_branch
    candidate["publisher"]["name"] = publisher_name
    candidate["publisher"]["copyright-owner"] = copyright_owner
    candidate["maintainer"]["name"] = maintainer_name
    candidate["maintainer"]["github"] = maintainer_github
    candidate["maintainer"].pop("security-email", None)
    candidate["security"]["channel"] = security_channel
    if security_email is None:
        candidate["security"].pop("email", None)
    else:
        candidate["security"]["email"] = security_email
    candidate["marketplace"]["name"] = marketplace_name
    candidate["marketplace"]["display-name"] = marketplace_display_name
    candidate["marketplace"]["description"] = marketplace_description
    candidate["release"]["license"] = license_id
    candidate["release"]["initial-year"] = initial_year

    validate_schema_instance(candidate, schema, label="repository.yaml")

    changed: list[str] = []
    data = candidate
    _write_if_changed(root, "repository.yaml", dump_yaml(data), changed)

    replacements = [
        (
            f"https://{old_owner}.github.io/{old_repository}",
            f"https://{owner}.github.io/{repository}",
        ),
        (
            f"https://raw.githubusercontent.com/{old_slug}/{old_branch}",
            f"https://raw.githubusercontent.com/{owner}/{repository}/{default_branch}",
        ),
        (
            f"https://github.com/{old_slug}/security/advisories/new",
            f"https://github.com/{owner}/{repository}/security/advisories/new",
        ),
        (f"https://github.com/{old_slug}", f"https://github.com/{owner}/{repository}"),
        (old_slug, f"{owner}/{repository}"),
        (old_project_description, project_description),
        (old_project_name, project_name),
        (old_marketplace, marketplace_name),
        (old_maintainer, maintainer_name),
        (f"@{old_github}", f"@{maintainer_github}"),
        (f"Publisher: {old_publisher}", f"Publisher: {publisher_name}"),
        (f"published by {old_publisher}", f"published by {publisher_name}"),
    ]
    for relative in IDENTITY_TEXT_SURFACES:
        path = root / relative
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        surface_replacements: dict[str, str] = {}
        for before, after in replacements:
            if before and before != after:
                if relative.startswith("schemas/") and relative.endswith(".json"):
                    encoded_before = json.dumps(before, ensure_ascii=False)[1:-1]
                    encoded_after = json.dumps(after, ensure_ascii=False)[1:-1]
                    surface_replacements.setdefault(encoded_before, encoded_after)
                else:
                    surface_replacements.setdefault(before, after)
        if surface_replacements:
            replacement_pattern = re.compile(
                "|".join(
                    re.escape(value)
                    for value in sorted(surface_replacements, key=len, reverse=True)
                )
            )
            text = replacement_pattern.sub(
                lambda match: surface_replacements[match.group(0)],
                text,
            )
        _write_if_changed(root, relative, text, changed)

    # Synchronize only the workflow fields that encode the canonical default branch;
    # replacing the word "main" globally would corrupt unrelated prose and shell code.
    workflow_branch_surfaces = (
        ".github/workflows/codeql.yml",
        ".github/workflows/compatibility.yml",
        ".github/workflows/eval.yml",
        ".github/workflows/pages.yml",
        ".github/workflows/validate.yml",
        ".github/workflows/native-compatibility.yml",
        ".github/workflows/release.yml",
    )
    old_branch_yaml = json.dumps(old_branch)
    default_branch_yaml = json.dumps(default_branch)
    branch_replacements = (
        (f"      - {old_branch}\n", f"      - {default_branch_yaml}\n"),
        (f"      - {old_branch_yaml}\n", f"      - {default_branch_yaml}\n"),
        (f"        default: {old_branch}\n", f"        default: {default_branch_yaml}\n"),
        (
            f"        default: {old_branch_yaml}\n",
            f"        default: {default_branch_yaml}\n",
        ),
        (
            f"          DEFAULT_BRANCH: {old_branch}\n",
            f"          DEFAULT_BRANCH: {default_branch_yaml}\n",
        ),
        (
            f"          DEFAULT_BRANCH: {old_branch_yaml}\n",
            f"          DEFAULT_BRANCH: {default_branch_yaml}\n",
        ),
        (
            f"success\\tworkflow_dispatch\\t{old_branch}\\t",
            f"success\\tworkflow_dispatch\\t{default_branch}\\t",
        ),
    )
    for relative in workflow_branch_surfaces:
        path = root / relative
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        for before, after in branch_replacements:
            text = text.replace(before, after)
        _write_if_changed(root, relative, text, changed)

    notice = (
        f"{project_name}\n"
        f"Copyright {initial_year} {copyright_owner}\n\n"
        "This product includes original documentation, validation tooling, and reusable "
        "Agent Skills\ndistributed under the Apache License, Version 2.0. See "
        "THIRD_PARTY_NOTICES.md for external\nstandards, documentation, and tools "
        "referenced by the project.\n"
    )
    _write_if_changed(root, "NOTICE", notice, changed)

    parts = maintainer_name.strip().split()
    if len(parts) > 1:
        given_names = " ".join(parts[:-1])
        family_names = parts[-1]
    else:
        given_names = parts[0]
        family_names = parts[0]
    citation = dump_yaml(
        {
            "cff-version": "1.2.0",
            "message": "Please cite this repository when you reuse or adapt its skillpacks.",
            "title": project_name,
            "type": "software",
            "authors": [
                {
                    "family-names": family_names,
                    "given-names": given_names,
                }
            ],
            "repository-code": f"https://github.com/{owner}/{repository}",
            "url": f"https://github.com/{owner}/{repository}",
            "license": license_id,
            "keywords": [
                "agent-skills",
                "claude-code",
                "codex",
                "opencode",
                "python",
                "postgresql",
            ],
        }
    )
    _write_if_changed(root, "CITATION.cff", citation, changed)

    env_path = root / ".env.example"
    env_lines = env_path.read_text(encoding="utf-8").splitlines() if env_path.is_file() else []
    retained = [
        line
        for line in env_lines
        if not re.match(
            r"^#?\s*(?:AGENT_SKILLPACKS|GENAPTIC_SKILLSETS)_(?:REPOSITORY|REF)=",
            line,
        )
    ]
    env_header = [
        "# Optional overrides used by generated direct installers.",
        f"GENAPTIC_SKILLSETS_REPOSITORY={owner}/{repository}",
        "GENAPTIC_SKILLSETS_REF=",
    ]
    # Keep application-specific examples (notably PostgreSQL smoke-test settings) intact.
    env_example = (
        "\n".join(env_header + [line for line in retained if line not in env_header]) + "\n"
    )
    _write_if_changed(root, ".env.example", env_example, changed)

    pyproject_path = root / "pyproject.toml"
    pyproject_text = pyproject_path.read_text(encoding="utf-8")
    author_line = f"authors = [{{ name = {json.dumps(publisher_name, ensure_ascii=False)} }}]"
    pyproject_text = re.sub(
        r'(?m)^authors = \[\{ name = "(?:\\.|[^"\\])*" \}\]$',
        lambda _match: author_line,
        pyproject_text,
        count=1,
    )
    _write_if_changed(root, "pyproject.toml", pyproject_text, changed)

    codeowners_path = root / ".github" / "CODEOWNERS"
    if codeowners_path.is_file():
        codeowners = re.sub(
            r"(?m)(^|\s)@[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})(?=\s|$)",
            lambda match: f"{match.group(1)}@{maintainer_github}",
            codeowners_path.read_text(encoding="utf-8"),
        )
        _write_if_changed(root, ".github/CODEOWNERS", codeowners, changed)

    for pack in discover_packs(root):
        manifest_path = pack.path / "skillpack.yaml"
        manifest = load_yaml(manifest_path)
        if _replace_placeholder_maintainers(manifest, maintainer_github):
            relative = manifest_path.relative_to(root).as_posix()
            _write_if_changed(root, relative, dump_yaml(manifest), changed)

    template_path = root / "templates" / "skillpack" / "skillpack.yaml"
    if template_path.is_file():
        template = load_yaml(template_path)
        if _replace_placeholder_maintainers(template, maintainer_github):
            _write_if_changed(
                root,
                template_path.relative_to(root).as_posix(),
                dump_yaml(template),
                changed,
            )

    _rewrite_skill_asset_schema_ids(
        root,
        owner=owner,
        repository=repository,
        default_branch=default_branch,
        changed=changed,
    )

    generated = apply_generated_files(root)
    return sorted(set(changed + generated))
