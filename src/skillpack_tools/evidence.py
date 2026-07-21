from __future__ import annotations

import datetime as dt
import json
import math
import os
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from .models import CompatibilityEvidencePolicy
from .path_safety import inspect_path, read_regular_bytes
from .schema_validation import load_json_schema, schema_errors
from .util import SkillpackError, sha256_bytes

MAX_EVIDENCE_JSON_BYTES = 1024 * 1024
MAX_EVIDENCE_JSON_NESTING = 64
_CANONICAL_UTC_RE = re.compile(
    r"^[0-9]{4}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12][0-9]|3[01])"
    r"T(?:[01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9]Z$"
)


class _DuplicateKeyError(ValueError):
    pass


class _NonFiniteNumberError(ValueError):
    pass


@dataclass(frozen=True)
class EvidenceAsset:
    """The three durable files produced by one protected evidence-ingestion run."""

    report: Path
    envelope: Path
    attestation_bundle: Path

    @classmethod
    def from_report(cls, report: Path) -> EvidenceAsset:
        if report.name.endswith(".envelope.json") or not report.name.endswith(".json"):
            raise SkillpackError(f"Evidence report must use a plain <client>.json name: {report}")
        stem = report.name.removesuffix(".json")
        if not stem:
            raise SkillpackError(f"Evidence report has no client filename stem: {report}")
        return cls(
            report=report,
            envelope=report.with_name(f"{stem}.envelope.json"),
            attestation_bundle=report.with_name(f"{stem}.attestation.jsonl"),
        )


@dataclass(frozen=True)
class ValidatedEvidence:
    assets: EvidenceAsset
    report: dict[str, Any]
    envelope: dict[str, Any]


def _object_without_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateKeyError(f"duplicate object key {key!r}")
        result[key] = value
    return result


def _finite_float(value: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise _NonFiniteNumberError(f"non-finite number {value!r} is not permitted")
    return number


def _reject_constant(value: str) -> None:
    raise _NonFiniteNumberError(f"non-finite number {value!r} is not permitted")


def _nesting_exceeds(value: Any, maximum: int) -> bool:
    stack: list[tuple[Any, int]] = [(value, 1)]
    while stack:
        current, depth = stack.pop()
        if not isinstance(current, (dict, list)):
            continue
        if depth > maximum:
            return True
        children = current.values() if isinstance(current, dict) else current
        stack.extend((child, depth + 1) for child in children)
    return False


def strict_load_json(path: Path, *, root: Path | None = None) -> dict[str, Any]:
    """Load a bounded evidence object while rejecting duplicate keys and non-finite numbers."""

    read_root = root or Path(os.path.abspath(os.fspath(path.parent)))
    try:
        content = read_regular_bytes(path, read_root)
    except (OSError, SkillpackError) as exc:
        raise SkillpackError(f"Could not read evidence JSON {path}: {exc}") from exc
    if len(content) > MAX_EVIDENCE_JSON_BYTES:
        raise SkillpackError(
            f"Evidence JSON {path} exceeds the {MAX_EVIDENCE_JSON_BYTES}-byte limit."
        )
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise SkillpackError(f"Evidence JSON {path} is not valid UTF-8: {exc}") from exc
    try:
        value = json.loads(
            text,
            object_pairs_hook=_object_without_duplicates,
            parse_float=_finite_float,
            parse_constant=_reject_constant,
        )
    except (_DuplicateKeyError, _NonFiniteNumberError, json.JSONDecodeError) as exc:
        raise SkillpackError(f"Invalid evidence JSON in {path}: {exc}") from exc
    except RecursionError as exc:
        raise SkillpackError(
            f"Evidence JSON {path} exceeds {MAX_EVIDENCE_JSON_NESTING} container levels."
        ) from exc
    if _nesting_exceeds(value, MAX_EVIDENCE_JSON_NESTING):
        raise SkillpackError(
            f"Evidence JSON {path} exceeds {MAX_EVIDENCE_JSON_NESTING} container levels."
        )
    if not isinstance(value, dict):
        raise SkillpackError(f"Evidence JSON {path} must contain one JSON object.")
    return value


def sha256_file(path: Path) -> str:
    """Hash one safely inspected regular file without following a sibling-path symlink."""

    root = Path(os.path.abspath(os.fspath(path.parent)))
    return sha256_bytes(read_regular_bytes(path, root))


def parse_tested_at(value: str) -> dt.datetime:
    """Parse the report contract's canonical second-precision UTC timestamp."""

    if not _CANONICAL_UTC_RE.fullmatch(value):
        raise ValueError("testedAt must be canonical UTC YYYY-MM-DDTHH:MM:SSZ")
    try:
        return dt.datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.UTC)
    except ValueError as exc:
        raise ValueError(f"testedAt is not a real RFC 3339 timestamp: {exc}") from exc


def evidence_freshness_errors(
    tested_at: str,
    policy: CompatibilityEvidencePolicy,
    *,
    now: dt.datetime | None = None,
    label: str = "compatibility report",
) -> list[str]:
    try:
        timestamp = parse_tested_at(tested_at)
    except ValueError as exc:
        return [f"{label}: {exc}"]
    current = now or dt.datetime.now(dt.UTC)
    if current.tzinfo is None or current.utcoffset() is None:
        raise ValueError("evidence freshness now= must be timezone-aware")
    current = current.astimezone(dt.UTC)
    future_limit = current + dt.timedelta(minutes=policy.future_skew_minutes)
    if timestamp > future_limit:
        return [
            f"{label}: testedAt is more than {policy.future_skew_minutes} minutes in the future."
        ]
    oldest = current - dt.timedelta(days=policy.max_age_days)
    if timestamp < oldest:
        return [f"{label}: evidence is older than {policy.max_age_days} days."]
    return []


def reviewer_authorization_errors(
    reviewer: Mapping[str, Any],
    policy: CompatibilityEvidencePolicy,
    *,
    actor: str | None = None,
    actor_id: int | None = None,
    triggering_actor: str | None = None,
    pack_maintainers: Iterable[str] = (),
    label: str = "compatibility report",
) -> list[str]:
    """Enforce stable GitHub identity and optional independent-review policy."""

    github = str(reviewer.get("github", ""))
    try:
        github_id = int(reviewer.get("githubId", 0))
    except (TypeError, ValueError):
        github_id = 0
    authorized = any(
        github.casefold() == candidate.github.casefold() and github_id == candidate.github_id
        for candidate in policy.authorized_reviewers
    )
    errors: list[str] = []
    if not authorized:
        errors.append(f"{label}: reviewer {github!r} with GitHub ID {github_id} is not authorized.")
    if actor is not None and github.casefold() != actor.casefold():
        errors.append(f"{label}: reviewer.github must match the workflow actor.")
    if actor_id is not None and github_id != actor_id:
        errors.append(f"{label}: reviewer.githubId must match the workflow actor ID.")
    if triggering_actor is not None and github.casefold() != triggering_actor.casefold():
        errors.append(f"{label}: reviewer.github must match the workflow triggering actor.")
    if policy.independent_review_required and github.casefold() in {
        maintainer.casefold() for maintainer in pack_maintainers
    }:
        errors.append(f"{label}: policy requires a reviewer independent of the pack maintainers.")
    return errors


def build_evidence_envelope(
    *,
    repository_id: int,
    repository_slug: str,
    run_id: int,
    run_attempt: int,
    workflow_ref: str,
    workflow_sha: str,
    event: str,
    actor: str,
    actor_id: int,
    triggering_actor: str,
    source_sha: str,
    evidence_sha: str,
    report_repository_path: str,
    report_sha256: str,
    client: str,
    pack_id: str,
    tested_at: str,
) -> dict[str, Any]:
    """Build the deterministic workflow-controlled provenance statement."""

    return {
        "schemaVersion": 1,
        "repository": {"id": repository_id, "slug": repository_slug},
        "workflow": {
            "runId": run_id,
            "runAttempt": run_attempt,
            "workflowRef": workflow_ref,
            "workflowSha": workflow_sha,
            "event": event,
            "actor": {"github": actor, "githubId": actor_id},
            # A rerun by a different login is rejected before construction, so both identities
            # resolve to the stable actor ID recorded by GitHub for this run.
            "triggeringActor": {"github": triggering_actor, "githubId": actor_id},
        },
        "source": {"sha": source_sha},
        "evidence": {
            "commitSha": evidence_sha,
            "reportPath": report_repository_path,
            "reportSha256": report_sha256,
        },
        "client": client,
        "packId": pack_id,
        "testedAt": tested_at,
    }


def validate_evidence_envelope(
    root: Path,
    path: Path,
    *,
    report_path: Path | None = None,
    report_repository_path: str | None = None,
    source_sha: str | None = None,
    evidence_sha: str | None = None,
    client: str | None = None,
    pack_id: str | None = None,
    repository_slug: str | None = None,
    workflow_run_id: int | None = None,
) -> tuple[list[str], dict[str, Any] | None]:
    """Validate an envelope schema and its caller-supplied report/run bindings."""

    errors: list[str] = []
    try:
        data = strict_load_json(path)
    except SkillpackError as exc:
        return [str(exc)], None
    try:
        schema = load_json_schema(
            root / "schemas" / "compatibility-evidence-envelope.schema.json",
            label="schemas/compatibility-evidence-envelope.schema.json",
            root=root,
        )
    except ValueError as exc:
        return [str(exc)], data
    errors.extend(schema_errors(data, schema, str(path)))
    if errors:
        return errors, data

    expected = (
        (source_sha, data["source"]["sha"], "source.sha"),
        (evidence_sha, data["evidence"]["commitSha"], "evidence.commitSha"),
        (report_repository_path, data["evidence"]["reportPath"], "evidence.reportPath"),
        (client, data["client"], "client"),
        (pack_id, data["packId"], "packId"),
        (repository_slug, data["repository"]["slug"], "repository.slug"),
        (workflow_run_id, data["workflow"]["runId"], "workflow.runId"),
    )
    for wanted, actual, field in expected:
        if wanted is not None and actual != wanted:
            errors.append(f"{path}: {field} is {actual!r}, expected {wanted!r}.")
    if report_path is not None:
        actual_digest = sha256_file(report_path)
        if data["evidence"]["reportSha256"] != actual_digest:
            errors.append(f"{path}: evidence.reportSha256 does not match the raw report bytes.")
        try:
            report = strict_load_json(report_path)
        except SkillpackError as exc:
            errors.append(str(exc))
        else:
            report_expected = (
                (report.get("testedAt"), data["testedAt"], "testedAt"),
                (report.get("client", {}).get("name"), data["client"], "client"),
                (report.get("pack", {}).get("id"), data["packId"], "packId"),
                (report.get("pack", {}).get("sourceSha"), data["source"]["sha"], "source.sha"),
                (
                    report.get("reviewer", {}).get("github"),
                    data["workflow"]["actor"]["github"],
                    "reviewer.github/workflow.actor.github",
                ),
                (
                    report.get("reviewer", {}).get("githubId"),
                    data["workflow"]["actor"]["githubId"],
                    "reviewer.githubId/workflow.actor.githubId",
                ),
            )
            for wanted, actual, field in report_expected:
                if wanted != actual:
                    errors.append(f"{path}: envelope {field} does not match the report.")
        if data["workflow"]["actor"] != data["workflow"]["triggeringActor"]:
            errors.append(f"{path}: workflow actor and triggeringActor must be identical.")
    return errors, data


def validate_evidence_asset(
    root: Path,
    report_path: Path,
    **bindings: Any,
) -> tuple[list[str], ValidatedEvidence | None]:
    """Load the conventional report/envelope/bundle sibling set for release tooling."""

    try:
        assets = EvidenceAsset.from_report(report_path)
        report = strict_load_json(assets.report)
    except SkillpackError as exc:
        return [str(exc)], None
    try:
        inspect_path(
            assets.attestation_bundle,
            Path(os.path.abspath(os.fspath(assets.attestation_bundle.parent))),
            leaf_kind="file",
        )
    except SkillpackError as exc:
        return [f"Missing or unsafe evidence attestation bundle: {exc}"], None
    errors, envelope = validate_evidence_envelope(
        root,
        assets.envelope,
        report_path=assets.report,
        **bindings,
    )
    if errors or envelope is None:
        return errors, None
    return [], ValidatedEvidence(assets=assets, report=report, envelope=envelope)


def repository_relative_report_path(value: str) -> str:
    """Validate the workflow input without resolving through attacker-controlled symlinks."""

    path = PurePosixPath(value)
    if (
        value != path.as_posix()
        or path.is_absolute()
        or path.parts[:2] != ("compatibility", "reports")
        or any(part in {"", ".", ".."} for part in path.parts)
        or path.suffix != ".json"
        or re.fullmatch(r"compatibility/reports/[A-Za-z0-9._/-]+\.json", value) is None
        or "//" in value
        or (os.sep != "/" and os.sep in value)
        or "\\" in value
    ):
        raise SkillpackError(
            "report_path must be a safe compatibility/reports/*.json repository path"
        )
    return path.as_posix()
