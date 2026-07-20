from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import yaml

from .path_safety import read_regular_text, walk_tree
from .util import SkillpackError


@dataclass(frozen=True)
class AuthorizedReviewer:
    github: str
    github_id: int


@dataclass(frozen=True)
class CompatibilityEvidencePolicy:
    max_age_days: int
    future_skew_minutes: int
    independent_review_required: bool
    authorized_reviewers: tuple[AuthorizedReviewer, ...]


@dataclass(frozen=True)
class TrustedSigner:
    kind: Literal["ssh", "openpgp"]
    github: str
    fingerprint: str


def _load_repository_yaml(path: Path, root: Path) -> dict[str, Any]:
    try:
        data = yaml.safe_load(read_regular_text(path, root))
    except UnicodeDecodeError as exc:
        raise SkillpackError(
            f"Required YAML file is not valid UTF-8: {path.relative_to(root)}"
        ) from exc
    except yaml.YAMLError as exc:
        raise SkillpackError(f"Invalid YAML in {path.relative_to(root)}: {exc}") from exc
    if not isinstance(data, dict):
        raise SkillpackError(f"Expected a YAML mapping in {path.relative_to(root)}.")
    return data


@dataclass(frozen=True)
class RepositoryConfig:
    root: Path
    raw: dict[str, Any]

    @property
    def owner(self) -> str:
        return str(self.raw["repository"]["owner"])

    @property
    def name(self) -> str:
        return str(self.raw["repository"]["name"])

    @property
    def slug(self) -> str:
        return f"{self.owner}/{self.name}"

    @property
    def project_name(self) -> str:
        return str(self.raw.get("project", {}).get("name", "Genaptic Skillsets"))

    @property
    def project_description(self) -> str:
        return str(
            self.raw.get("project", {}).get(
                "description", self.raw.get("marketplace", {}).get("description", "")
            )
        )

    @property
    def git_url(self) -> str:
        return f"https://github.com/{self.slug}.git"

    @property
    def web_url(self) -> str:
        return f"https://github.com/{self.slug}"

    @property
    def default_branch(self) -> str:
        return str(self.raw["repository"]["default-branch"])

    @property
    def publisher_name(self) -> str:
        return str(self.raw.get("publisher", {}).get("name", self.maintainer_name))

    @property
    def copyright_owner(self) -> str:
        return str(self.raw.get("publisher", {}).get("copyright-owner", self.publisher_name))

    @property
    def maintainer_name(self) -> str:
        return str(self.raw["maintainer"]["name"])

    @property
    def maintainer_github(self) -> str:
        return str(self.raw["maintainer"]["github"])

    @property
    def security_email(self) -> str | None:
        security = self.raw.get("security", {})
        value = security.get("email", self.raw.get("maintainer", {}).get("security-email"))
        return str(value) if value else None

    @property
    def security_channel(self) -> str:
        return str(
            self.raw.get("security", {}).get("channel", "github-private-vulnerability-reporting")
        )

    @property
    def security_url(self) -> str:
        if self.security_channel == "github-private-vulnerability-reporting":
            return f"{self.web_url}/security/advisories/new"
        if self.security_email:
            return f"mailto:{self.security_email}"
        raise ValueError(f"Unsupported security channel: {self.security_channel}")

    @property
    def marketplace_name(self) -> str:
        return str(self.raw["marketplace"]["name"])

    @property
    def marketplace_display_name(self) -> str:
        return str(self.raw["marketplace"]["display-name"])

    @property
    def marketplace_description(self) -> str:
        return str(self.raw["marketplace"]["description"])

    @property
    def compatibility_evidence(self) -> CompatibilityEvidencePolicy:
        policy = self.raw["compatibility-evidence"]
        return CompatibilityEvidencePolicy(
            max_age_days=int(policy["max-age-days"]),
            future_skew_minutes=int(policy["future-skew-minutes"]),
            independent_review_required=bool(policy["independent-review-required"]),
            authorized_reviewers=tuple(
                AuthorizedReviewer(
                    github=str(reviewer["github"]),
                    github_id=int(reviewer["github-id"]),
                )
                for reviewer in policy["authorized-reviewers"]
            ),
        )

    @property
    def license(self) -> str:
        return str(self.raw["release"]["license"])

    @property
    def initial_year(self) -> int:
        return int(self.raw["release"]["initial-year"])

    @property
    def trusted_signers(self) -> tuple[TrustedSigner, ...]:
        return tuple(
            TrustedSigner(
                kind=signer["type"],
                github=str(signer["github"]),
                fingerprint=str(signer["fingerprint"]),
            )
            for signer in self.raw["release"]["trusted-signers"]
        )


@dataclass(frozen=True)
class Pack:
    root: Path
    path: Path
    raw: dict[str, Any]

    @property
    def relative_path(self) -> str:
        return self.path.relative_to(self.root).as_posix()

    @property
    def id(self) -> str:
        return str(self.raw["id"])

    @property
    def display_name(self) -> str:
        return str(self.raw["display-name"])

    @property
    def description(self) -> str:
        return str(self.raw["description"]).strip()

    @property
    def language(self) -> str:
        return str(self.raw["language"])

    @property
    def subject(self) -> str:
        return str(self.raw["subject"])

    @property
    def version(self) -> str:
        return str(self.raw["version"])

    @property
    def maturity(self) -> str:
        return str(self.raw["maturity"])

    @property
    def visibility(self) -> str:
        return str(self.raw["distribution"]["visibility"])

    @property
    def tag(self) -> str:
        return f"{self.id}-v{self.version}"

    @property
    def source_sha(self) -> str | None:
        """Return the last published source SHA, when one exists.

        This compatibility property intentionally reads only the nested v2 release snapshot;
        a legacy top-level ``source-sha`` is never accepted as publication state.
        """

        value = (self.latest_release or {}).get("source-sha")
        return str(value) if value else None

    @property
    def latest_release(self) -> dict[str, Any] | None:
        value = self.raw["publication"].get("latest-release")
        return dict(value) if isinstance(value, dict) else None

    @property
    def published_version(self) -> str | None:
        value = (self.latest_release or {}).get("version")
        return str(value) if value else None

    @property
    def published_tag(self) -> str | None:
        return f"{self.id}-v{self.published_version}" if self.published_version else None

    @property
    def license(self) -> str:
        return str(self.raw["license"])

    @property
    def maintainers(self) -> list[dict[str, str]]:
        return list(self.raw["maintainers"])

    @property
    def skills(self) -> list[str]:
        return list(self.raw["skills"])

    @property
    def targets(self) -> list[str]:
        return list(self.raw["targets"])

    @property
    def category(self) -> str:
        return str(self.raw["category"])

    @property
    def keywords(self) -> list[str]:
        return list(self.raw["keywords"])

    @property
    def compatibility(self) -> dict[str, Any]:
        return dict(self.raw["compatibility"])

    @property
    def publication_state(self) -> str:
        return str(self.raw["publication"]["state"])

    @property
    def release_gates(self) -> list[str]:
        return list(self.raw["release-gates"])

    @property
    def short_description(self) -> str:
        return str(self.raw["interface"]["short-description"])

    @property
    def starter_prompts(self) -> list[dict[str, str]]:
        return [dict(item) for item in self.raw["interface"]["starter-prompts"]]

    @property
    def operations(self) -> dict[str, str]:
        return dict(self.raw["operations"])


def load_repository(root: Path) -> RepositoryConfig:
    root = Path(os.path.abspath(os.fspath(root)))
    return RepositoryConfig(root=root, raw=_load_repository_yaml(root / "repository.yaml", root))


def discover_packs(root: Path) -> list[Pack]:
    root = Path(os.path.abspath(os.fspath(root)))
    snapshot = walk_tree(root / "packs", root, allow_missing=True)
    packs: list[Pack] = []
    manifests = [
        path
        for path, _metadata in snapshot.files
        if path.relative_to(root / "packs").parts[-1:] == ("skillpack.yaml",)
        and len(path.relative_to(root / "packs").parts) == 3
    ]
    for manifest in manifests:
        packs.append(
            Pack(
                root=root,
                path=manifest.parent,
                raw=_load_repository_yaml(manifest, root),
            )
        )
    return packs


def get_pack(root: Path, pack_id: str) -> Pack:
    root = Path(os.path.abspath(os.fspath(root)))
    matches = [pack for pack in discover_packs(root) if pack.id == pack_id]
    if not matches:
        known = ", ".join(pack.id for pack in discover_packs(root)) or "(none)"
        raise KeyError(f"Unknown pack {pack_id!r}. Known packs: {known}")
    return matches[0]
