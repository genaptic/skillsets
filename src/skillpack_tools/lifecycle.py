from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Literal

from .models import Pack

DistributionChannel = Literal["public", "preview", "development"]

BASELINE_RELEASE_GATES = ("native-evidence", "deterministic-archive")
RUST_RELEASE_GATES = (*BASELINE_RELEASE_GATES, "rust-assets")
MATURITIES = frozenset({"draft", "release-candidate", "stable", "deprecated"})
PUBLICATION_STATES = frozenset({"unpublished", "published", "withdrawn"})
VISIBILITIES = frozenset({"public", "maintainers"})

_SEMVER_PRERELEASE_IDENTIFIER = r"(?:0|[1-9][0-9]*|[0-9]*[A-Za-z-][0-9A-Za-z-]*)"
SEMVER_PATTERN = (
    r"^(?P<major>0|[1-9][0-9]*)\."
    r"(?P<minor>0|[1-9][0-9]*)\."
    r"(?P<patch>0|[1-9][0-9]*)"
    rf"(?:-(?P<prerelease>{_SEMVER_PRERELEASE_IDENTIFIER}"
    rf"(?:\.{_SEMVER_PRERELEASE_IDENTIFIER})*))?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)
_SEMVER = re.compile(SEMVER_PATTERN)


def _prerelease_key(value: str | None) -> tuple[tuple[int, int | str], ...]:
    if value is None:
        return ((2, 0),)
    parts: list[tuple[int, int | str]] = []
    for part in value.split("."):
        parts.append((0, int(part)) if part.isdigit() else (1, part))
    return tuple(parts)


def semantic_version_key(value: str) -> tuple[int, int, int, tuple[tuple[int, int | str], ...]]:
    match = _SEMVER.fullmatch(value)
    if not match:
        raise ValueError(f"Invalid Semantic Version {value!r}.")
    return (
        int(match.group("major")),
        int(match.group("minor")),
        int(match.group("patch")),
        _prerelease_key(match.group("prerelease")),
    )


def validate_pack_lifecycle(pack: Pack) -> list[str]:
    """Validate invariants that require comparing fields in one manifest."""

    errors: list[str] = []
    label = f"{pack.relative_path}/skillpack.yaml"
    if pack.maturity not in MATURITIES:
        errors.append(f"{label}: unsupported maturity {pack.maturity!r}.")
    if pack.visibility not in VISIBILITIES:
        errors.append(f"{label}: unsupported distribution visibility {pack.visibility!r}.")
    if pack.publication_state not in PUBLICATION_STATES:
        errors.append(f"{label}: unsupported publication state {pack.publication_state!r}.")

    expected_gates = RUST_RELEASE_GATES if pack.language == "rust" else BASELINE_RELEASE_GATES
    if tuple(pack.release_gates) != expected_gates:
        errors.append(
            f"{label}: release-gates must be {list(expected_gates)!r} for {pack.language!r}."
        )

    latest = pack.latest_release
    if pack.publication_state == "unpublished":
        if latest is not None:
            errors.append(f"{label}: unpublished packs must not declare latest-release.")
    elif latest is None:
        errors.append(f"{label}: {pack.publication_state} packs require latest-release.")

    if pack.visibility == "maintainers" and pack.publication_state != "unpublished":
        errors.append(f"{label}: maintainer-only packs must remain unpublished.")

    short_description = pack.short_description
    if not short_description.endswith((".", "!", "?")):
        errors.append(
            f"{label}: interface.short-description must end with sentence punctuation; "
            "truncated fragments are not allowed."
        )
    if any(
        marker in short_description.casefold() for marker in ("replace with", "placeholder", "todo")
    ):
        errors.append(f"{label}: interface.short-description contains boilerplate.")

    if latest is not None:
        latest_version = str(latest.get("version", ""))
        try:
            current_key = semantic_version_key(pack.version)
            latest_key = semantic_version_key(latest_version)
        except ValueError as exc:
            errors.append(f"{label}: {exc}")
        else:
            if current_key < latest_key:
                errors.append(
                    f"{label}: current version {pack.version} cannot precede latest release "
                    f"{latest_version}."
                )
            if current_key == latest_key and pack.maturity not in {"stable", "deprecated"}:
                errors.append(
                    f"{label}: a current version equal to latest-release requires stable or "
                    "deprecated maturity."
                )

    declared = set(pack.skills)
    prompts = pack.starter_prompts
    prompt_texts = [str(item.get("prompt", "")) for item in prompts]
    for index, item in enumerate(prompts):
        skill = str(item.get("skill", ""))
        prompt = str(item.get("prompt", ""))
        if skill not in declared:
            errors.append(f"{label}: interface.starter-prompts[{index}].skill is undeclared.")
        if f"${skill}" not in prompt:
            errors.append(
                f"{label}: interface.starter-prompts[{index}].prompt must reference ${skill}."
            )
        lowered = prompt.casefold()
        if any(marker in lowered for marker in ("replace with", "placeholder", "todo")):
            errors.append(f"{label}: interface.starter-prompts[{index}] contains boilerplate.")
    if len(prompt_texts) != len(set(prompt_texts)):
        errors.append(f"{label}: starter prompt text must be unique.")
    return errors


def select_packs(packs: Iterable[Pack], channel: DistributionChannel) -> list[Pack]:
    """Select packs for a generated channel from canonical lifecycle metadata."""

    selected: list[Pack] = []
    for pack in packs:
        if channel == "public":
            include = (
                pack.visibility == "public"
                and pack.publication_state == "published"
                and pack.latest_release is not None
            )
        elif channel == "preview":
            include = (
                pack.visibility == "public"
                and pack.publication_state != "withdrawn"
                and (
                    pack.latest_release is None
                    or pack.version != pack.published_version
                    or pack.maturity == "release-candidate"
                )
            )
        elif channel == "development":
            include = pack.publication_state != "withdrawn"
        else:  # pragma: no cover - protected by the Literal and direct tests
            raise ValueError(f"Unknown distribution channel: {channel}")
        if include:
            selected.append(pack)
    return selected


def pages_absent_paths(packs: Iterable[Pack], legacy_paths: Iterable[str]) -> list[str]:
    """Return HTTP paths that must remain absent from the public Pages deployment."""

    pack_list = list(packs)
    public_ids = {pack.id for pack in select_packs(pack_list, "public")}
    absent = set(legacy_paths)
    for pack in pack_list:
        paths = {
            f"install/{pack.id}.sh",
            f"install/{pack.id}.ps1",
            f"opencode/{pack.language}/{pack.subject}/index.json",
        }
        if pack.id in public_ids:
            absent.difference_update(paths)
        else:
            absent.update(paths)
    return sorted(absent)
