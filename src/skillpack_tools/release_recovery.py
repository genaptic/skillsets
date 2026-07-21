from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from .models import get_pack
from .publication import strict_json_bytes
from .release import render_release_notes
from .schema_validation import load_json_schema, validate_schema_instance
from .signing import VerifiedTag
from .util import SkillpackError, sha256_bytes, sha256_file

_SHA = re.compile(r"^[0-9a-f]{40}$")
_SSH_FINGERPRINT = re.compile(r"^SHA256:[A-Za-z0-9+/]{43}$")
_OPENPGP_FINGERPRINT = re.compile(r"^(?:[0-9A-F]{40}|[0-9A-F]{64})$")
_HEX_DIGEST = r"[0-9a-f]{64}"


def _is_safe_asset_name(value: Any) -> bool:
    return (
        isinstance(value, str)
        and bool(value)
        and value not in {".", ".."}
        and "/" not in value
        and "\\" not in value
        and not any(ord(character) < 32 or ord(character) == 127 for character in value)
        and Path(value).name == value
    )


def expected_asset_names(tag: str) -> list[str]:
    """Return the exact immutable release asset-name contract in stable order."""

    return sorted(
        [
            f"{tag}.zip",
            f"{tag}.zip.sha256",
            *(
                f"{client}.{suffix}"
                for client in ("claude-code", "codex", "opencode")
                for suffix in ("json", "envelope.json", "attestation.jsonl")
            ),
        ]
    )


def expected_publishable_body(
    root: Path,
    pack_id: str,
    release: dict[str, Any],
    *,
    source_sha: str,
    signature_kind: str,
    signer_fingerprint: str,
) -> str:
    """Validate and return the exact deterministic publishable release-note body.

    An interrupted draft can be missing assets, so recovery cannot always rebuild every
    digest before deciding whether inspection or removal is safe.  The body contract is
    nevertheless closed: canonical tagged metadata and changelog text are literal, every
    expected digest occupies one fixed position, and any asset already present must match
    the digest declared for it.  Resume later rebuilds every byte and performs an exact
    body comparison before publication.
    """

    if not _SHA.fullmatch(source_sha):
        raise SkillpackError("release-note source must be a full lowercase Git SHA")
    fingerprint_pattern = _SSH_FINGERPRINT if signature_kind == "ssh" else _OPENPGP_FINGERPRINT
    if signature_kind not in {"ssh", "openpgp"} or not fingerprint_pattern.fullmatch(
        signer_fingerprint
    ):
        raise SkillpackError("release-note signer type/fingerprint is invalid")
    body = release.get("body")
    if not isinstance(body, str):
        raise SkillpackError("release body must be deterministic text")

    pack = get_pack(root, pack_id)
    lines = body.rstrip("\n").splitlines()
    archive_prefix = "- Archive SHA-256: `"
    archive_matches = [
        line.removeprefix(archive_prefix).removesuffix("`")
        for line in lines
        if line.startswith(archive_prefix) and line.endswith("`")
    ]
    if len(archive_matches) != 1 or not re.fullmatch(_HEX_DIGEST, archive_matches[0]):
        raise SkillpackError("release body has an invalid archive digest declaration")
    archive_digest = archive_matches[0]
    digest_values: dict[str, str] = {f"{pack.tag}.zip": archive_digest}
    evidence_records: list[dict[str, str]] = []
    for client in ("claude-code", "codex", "opencode"):
        pattern = (
            re.escape(f"- `{client}`: report `{client}.json` (`")
            + rf"(?P<report>{_HEX_DIGEST})"
            + re.escape(f"`), envelope `{client}.envelope.json` (`")
            + rf"(?P<envelope>{_HEX_DIGEST})"
            + re.escape(f"`), attestation bundle `{client}.attestation.jsonl` (`")
            + rf"(?P<attestation>{_HEX_DIGEST})"
            + re.escape("`)")
        )
        matches = [match for line in lines if (match := re.fullmatch(pattern, line))]
        if len(matches) != 1:
            raise SkillpackError(
                f"release body must contain one exact {client} evidence declaration"
            )
        match = matches[0]
        evidence_records.append(
            {
                "client": client,
                "reportAsset": f"{client}.json",
                "reportSha256": match.group("report"),
                "provenanceAsset": f"{client}.envelope.json",
                "provenanceSha256": match.group("envelope"),
                "attestationBundleAsset": f"{client}.attestation.jsonl",
                "attestationBundleSha256": match.group("attestation"),
            }
        )
        digest_values[f"{client}.json"] = match.group("report")
        digest_values[f"{client}.envelope.json"] = match.group("envelope")
        digest_values[f"{client}.attestation.jsonl"] = match.group("attestation")

    changelog = (pack.path / "CHANGELOG.md").read_text(encoding="utf-8")
    rendered = render_release_notes(
        pack,
        draft=False,
        source_sha=source_sha,
        signer=VerifiedTag(
            source_sha=source_sha,
            kind=signature_kind,
            fingerprint=signer_fingerprint,
        ),
        archive_digest=archive_digest,
        evidence_records=evidence_records,
        changelog=changelog,
    ).decode("utf-8")
    if rendered != body:
        raise SkillpackError("release body does not match the deterministic publishable contract")

    expected_existing_digests = {name: f"sha256:{digest}" for name, digest in digest_values.items()}
    checksum_name = f"{pack.tag}.zip.sha256"
    checksum = f"{archive_digest}  {pack.tag}.zip\n".encode()
    expected_existing_digests[checksum_name] = f"sha256:{sha256_bytes(checksum)}"
    seen: set[str] = set()
    for asset in release.get("assets", []):
        if not isinstance(asset, dict):
            raise SkillpackError("release assets must be objects")
        name = asset.get("name")
        if name not in expected_existing_digests:
            continue
        assert isinstance(name, str)
        if name in seen:
            raise SkillpackError(f"release contains duplicate expected asset {name!r}")
        seen.add(name)
        expected_digest = expected_existing_digests[name]
        if asset.get("digest") != expected_digest:
            raise SkillpackError(
                f"release body digest for {name!r} does not match the existing asset"
            )
    return body


def _asset_inventory(release: dict[str, Any]) -> list[dict[str, Any]]:
    inventory: list[dict[str, Any]] = []
    for raw in release.get("assets", []):
        inventory.append(
            {
                "id": raw.get("id"),
                "name": raw.get("name"),
                "size": raw.get("size"),
                "state": raw.get("state"),
                "digest": raw.get("digest"),
                "uploader": (raw.get("uploader") or {}).get("login"),
            }
        )
    return sorted(inventory, key=lambda item: (str(item["name"]), int(item["id"] or 0)))


def _release_intent_schema(root: Path) -> dict[str, Any]:
    return load_json_schema(
        root / "schemas" / "release-intent.schema.json",
        label="schemas/release-intent.schema.json",
        root=root,
    )


def validate_release_intent(root: Path, intent: dict[str, Any]) -> None:
    """Validate the strict workflow handoff contract."""

    validate_schema_instance(intent, _release_intent_schema(root), label="release-intent.json")


def seal_release_intent(
    root: Path,
    release: dict[str, Any],
    *,
    mode: str,
    repository_slug: str,
    policy_sha: str,
    workflow_name: str,
    workflow_run_id: int,
    workflow_run_attempt: int,
    pack_id: str,
    release_id: int,
    tag: str,
    tag_object_sha: str,
    source_sha: str,
    signature_kind: str,
    signer_fingerprint: str,
    github_tag_verified: bool,
    expected_title: str,
    expected_body: str,
    expected_target_commitish: str,
) -> dict[str, Any]:
    """Seal one exact, verified draft or reconstructed immutable release state."""

    if mode not in {"sealed-draft", "reconstructed-published"}:
        raise SkillpackError("release intent mode is unsupported")
    inspection = inspect_release(
        release,
        release_id=release_id,
        tag=tag,
        policy_sha=policy_sha,
        tag_object_sha=tag_object_sha,
        source_sha=source_sha,
        signature_kind=signature_kind,
        signer_fingerprint=signer_fingerprint,
        github_tag_verified=github_tag_verified,
        expected_title=expected_title,
        expected_body=expected_body,
        expected_target_commitish=expected_target_commitish,
    )
    if mode == "sealed-draft":
        if inspection["draft"] is not True or inspection["immutable"] is not False:
            raise SkillpackError("a sealed release intent requires one mutable draft")
        if release.get("published_at") is not None:
            raise SkillpackError("a sealed draft must not have a publication time")
    else:
        if inspection["draft"] is not False or inspection["immutable"] is not True:
            raise SkillpackError("a reconstructed intent requires one immutable publication")
        if not isinstance(release.get("published_at"), str) or not release["published_at"]:
            raise SkillpackError("an immutable publication requires published_at")
    if inspection["prerelease"] is not False:
        raise SkillpackError("release intent refuses prerelease state")
    assets = inspection["assets"]
    names = [item.get("name") for item in assets]
    if names != expected_asset_names(tag):
        raise SkillpackError("release intent requires the exact canonical asset-name inventory")
    for asset in assets:
        if (
            isinstance(asset.get("id"), bool)
            or not isinstance(asset.get("id"), int)
            or asset["id"] < 1
            or asset.get("state") != "uploaded"
            or isinstance(asset.get("size"), bool)
            or not isinstance(asset.get("size"), int)
            or asset["size"] < 0
            or not isinstance(asset.get("digest"), str)
            or re.fullmatch(r"sha256:[0-9a-f]{64}", asset["digest"]) is None
            or not isinstance(asset.get("uploader"), str)
            or not asset["uploader"]
        ):
            raise SkillpackError(f"release intent asset {asset.get('name')!r} is incomplete")
    intent = {
        "schemaVersion": 1,
        "mode": mode,
        "repository": {"slug": repository_slug, "policySha": policy_sha},
        "workflow": {
            "name": workflow_name,
            "runId": workflow_run_id,
            "runAttempt": workflow_run_attempt,
        },
        "packId": pack_id,
        "releaseId": release_id,
        "tag": tag,
        "url": inspection["url"],
        "tagObjectSha": tag_object_sha,
        "sourceSha": source_sha,
        "signer": {"type": signature_kind, "fingerprint": signer_fingerprint},
        "title": expected_title,
        "body": expected_body,
        "targetCommitish": expected_target_commitish,
        "releaseState": {
            "draft": release.get("draft"),
            "prerelease": release.get("prerelease"),
            "immutable": release.get("immutable"),
            "publishedAt": release.get("published_at"),
        },
        "assets": assets,
    }
    validate_release_intent(root, intent)
    return intent


def verify_published_release(
    root: Path,
    release: dict[str, Any],
    intent: dict[str, Any],
) -> dict[str, Any]:
    """Require an immutable release to equal the pre-publication intent exactly."""

    validate_release_intent(root, intent)
    inspection = inspect_release(
        release,
        release_id=intent["releaseId"],
        tag=intent["tag"],
        policy_sha=intent["repository"]["policySha"],
        tag_object_sha=intent["tagObjectSha"],
        source_sha=intent["sourceSha"],
        signature_kind=intent["signer"]["type"],
        signer_fingerprint=intent["signer"]["fingerprint"],
        github_tag_verified=True,
        expected_title=intent["title"],
        expected_body=intent["body"],
        expected_url=intent["url"],
        expected_target_commitish=intent["targetCommitish"],
    )
    if inspection["draft"] is not False or inspection["prerelease"] is not False:
        raise SkillpackError("published release must be a non-prerelease publication")
    if inspection["immutable"] is not True:
        raise SkillpackError("published release must be immutable")
    if not isinstance(release.get("published_at"), str) or not release["published_at"]:
        raise SkillpackError("published release must have a publication time")
    if inspection["assets"] != intent["assets"]:
        raise SkillpackError("published asset inventory differs from the sealed release intent")
    sealed_state = intent["releaseState"]
    expected_state = (
        {
            "draft": True,
            "prerelease": False,
            "immutable": False,
            "publishedAt": None,
        }
        if intent["mode"] == "sealed-draft"
        else {
            "draft": False,
            "prerelease": False,
            "immutable": True,
            "publishedAt": release["published_at"],
        }
    )
    if sealed_state != expected_state:
        raise SkillpackError("release state differs from the sealed release intent")
    return {
        "schemaVersion": 1,
        "releaseId": intent["releaseId"],
        "policySha": intent["repository"]["policySha"],
        "tag": intent["tag"],
        "url": intent["url"],
        "publishedAt": release["published_at"],
        "immutable": True,
        "sourceSha": intent["sourceSha"],
        "signer": intent["signer"],
        "intentSha256": sha256_bytes(
            json.dumps(intent, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ),
        "assets": inspection["assets"],
    }


def inspect_release(
    release: dict[str, Any],
    *,
    release_id: int,
    tag: str,
    policy_sha: str | None = None,
    tag_object_sha: str | None = None,
    source_sha: str | None = None,
    signature_kind: str | None = None,
    signer_fingerprint: str | None = None,
    github_tag_verified: bool | None = None,
    expected_title: str | None = None,
    expected_body: str | None = None,
    expected_url: str | None = None,
    expected_target_commitish: str | None = None,
) -> dict[str, Any]:
    """Return a deterministic, non-mutating inventory for an exact numeric release."""

    if release.get("id") != release_id:
        raise SkillpackError(
            f"release API returned ID {release.get('id')!r}, expected {release_id}"
        )
    if release.get("tag_name") != tag:
        raise SkillpackError(
            f"release {release_id} has tag {release.get('tag_name')!r}, expected {tag!r}"
        )
    if policy_sha is not None and not _SHA.fullmatch(policy_sha):
        raise SkillpackError("inspection policy SHA must be a full lowercase Git SHA")
    release_url = release.get("html_url")
    if (
        not isinstance(release_url, str)
        or re.fullmatch(r"https://github\.com/[^/]+/[^/]+/releases/tag/[^/?#]+", release_url)
        is None
    ):
        raise SkillpackError("release API returned an invalid canonical HTTPS release URL")
    expected_values = {
        "url": (release_url, expected_url),
        "title": (release.get("name"), expected_title),
        "body": (str(release.get("body") or ""), expected_body),
        "target_commitish": (release.get("target_commitish"), expected_target_commitish),
    }
    for field, (actual, expected) in expected_values.items():
        if expected is not None and actual != expected:
            raise SkillpackError(f"release {field} does not match the deterministic expectation")

    tag_values = (tag_object_sha, source_sha, signature_kind, signer_fingerprint)
    if any(value is not None for value in tag_values) or github_tag_verified is not None:
        if not all(value is not None for value in tag_values) or github_tag_verified is not True:
            raise SkillpackError("inspection requires one complete verified annotated-tag identity")
        assert tag_object_sha is not None
        assert source_sha is not None
        assert signature_kind is not None
        assert signer_fingerprint is not None
        if not _SHA.fullmatch(tag_object_sha) or not _SHA.fullmatch(source_sha):
            raise SkillpackError("verified tag object and source must be full lowercase Git SHAs")
        fingerprint_pattern = _SSH_FINGERPRINT if signature_kind == "ssh" else _OPENPGP_FINGERPRINT
        if signature_kind not in {"ssh", "openpgp"} or not fingerprint_pattern.fullmatch(
            signer_fingerprint
        ):
            raise SkillpackError("verified tag signer type/fingerprint is invalid")
        tag_object: dict[str, Any] | None = {
            "type": "tag",
            "objectSha": tag_object_sha,
            "sourceSha": source_sha,
            "githubVerified": True,
            "signature": {"type": signature_kind, "fingerprint": signer_fingerprint},
        }
    else:
        tag_object = None
    return {
        "schemaVersion": 2,
        "releaseId": release_id,
        "policySha": policy_sha,
        "tag": tag,
        "url": release_url,
        "title": release.get("name"),
        "body": release.get("body"),
        "targetCommitish": release.get("target_commitish"),
        "draft": release.get("draft"),
        "prerelease": release.get("prerelease"),
        "immutable": release.get("immutable"),
        "tagObject": tag_object,
        "expectedAssetNames": expected_asset_names(tag),
        "assets": _asset_inventory(release),
    }


def reinspect_bound_release(
    release: dict[str, Any],
    trusted_inspection: dict[str, Any],
    *,
    release_id: int,
    tag: str,
) -> dict[str, Any]:
    """Re-read a release and require it to match a prior verified inspection exactly.

    The trusted inspection must come from the successful read-only job in the same
    recovery run.  Its complete annotated-tag identity is carried into the fresh
    inspection, while all release fields and the asset inventory are rebound to the
    current API response for a second read-only consistency check.
    """

    if trusted_inspection.get("schemaVersion") != 2:
        raise SkillpackError("trusted release inspection must use schema version 2")
    if trusted_inspection.get("releaseId") != release_id or trusted_inspection.get("tag") != tag:
        raise SkillpackError("trusted release inspection does not match the requested release")
    tag_object = trusted_inspection.get("tagObject")
    if not isinstance(tag_object, dict) or tag_object.get("type") != "tag":
        raise SkillpackError("trusted release inspection lacks a verified annotated-tag identity")
    signature = tag_object.get("signature")
    if not isinstance(signature, dict):
        raise SkillpackError("trusted release inspection lacks a verified signer identity")
    canonical_assets = expected_asset_names(tag)
    if trusted_inspection.get("expectedAssetNames") != canonical_assets:
        raise SkillpackError("trusted inspection has a non-canonical expected asset-name set")

    current = inspect_release(
        release,
        release_id=release_id,
        tag=tag,
        policy_sha=trusted_inspection.get("policySha"),
        tag_object_sha=tag_object.get("objectSha"),
        source_sha=tag_object.get("sourceSha"),
        signature_kind=signature.get("type"),
        signer_fingerprint=signature.get("fingerprint"),
        github_tag_verified=tag_object.get("githubVerified"),
        expected_title=trusted_inspection.get("title"),
        expected_body=str(trusted_inspection.get("body") or ""),
        expected_url=trusted_inspection.get("url"),
        expected_target_commitish=trusted_inspection.get("targetCommitish"),
    )
    bound_fields = (
        "releaseId",
        "policySha",
        "tag",
        "url",
        "title",
        "body",
        "targetCommitish",
        "draft",
        "prerelease",
        "immutable",
        "tagObject",
        "expectedAssetNames",
        "assets",
    )
    changed = [
        field for field in bound_fields if current.get(field) != trusted_inspection.get(field)
    ]
    if changed:
        raise SkillpackError("release changed after the trusted inspection: " + ", ".join(changed))
    return current


def _portable_expected_asset(raw: Any) -> dict[str, Any]:
    """Return the runner-independent subset of one expected asset record."""

    if not isinstance(raw, dict):
        raise SkillpackError("recovery expected assets must be objects")
    name = raw.get("name")
    if not _is_safe_asset_name(name):
        raise SkillpackError("recovery expected asset names must be safe basenames")
    assert isinstance(name, str)
    size = raw.get("size")
    if isinstance(size, bool) or not isinstance(size, int) or size < 0:
        raise SkillpackError(f"recovery expected asset {name!r} has an invalid size")
    digest = raw.get("digest")
    if not isinstance(digest, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
        raise SkillpackError(f"recovery expected asset {name!r} has an invalid digest")
    return {"name": name, "size": size, "digest": digest}


def expected_assets(paths: list[Path]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in paths:
        if not path.is_file() or path.is_symlink():
            raise SkillpackError(f"recovery expected asset must be a regular file: {path}")
        records.append(
            _portable_expected_asset(
                {
                    "name": path.name,
                    "size": path.stat().st_size,
                    "digest": f"sha256:{sha256_file(path)}",
                }
            )
        )
    names = [str(item["name"]) for item in records]
    if len(names) != len(set(names)):
        raise SkillpackError("recovery expected assets must have unique basenames")
    return sorted(records, key=lambda item: item["name"])


def plan_resume(
    inspection: dict[str, Any],
    expected: list[dict[str, Any]],
) -> dict[str, Any]:
    """Fail closed on suspicious drafts and identify only safely missing assets."""

    if inspection.get("immutable") is not False or inspection.get("draft") is not True:
        raise SkillpackError("Only a mutable draft release can be resumed.")
    if inspection.get("prerelease") is not False:
        raise SkillpackError("The production recovery path refuses prerelease drafts.")
    actual_assets = inspection.get("assets", [])
    if not isinstance(actual_assets, list) or not all(
        isinstance(item, dict) for item in actual_assets
    ):
        raise SkillpackError("Inspected release assets must be objects.")
    actual_names: list[str] = []
    for item in actual_assets:
        name = item.get("name")
        if not _is_safe_asset_name(name):
            raise SkillpackError("Inspected release asset names must be safe basenames.")
        assert isinstance(name, str)
        actual_names.append(name)
    portable_expected = [_portable_expected_asset(item) for item in expected]
    expected_names = [str(item["name"]) for item in portable_expected]
    if len(actual_names) != len(set(actual_names)):
        raise SkillpackError("Draft contains duplicate asset names.")
    if len(expected_names) != len(set(expected_names)):
        raise SkillpackError("Rebuilt expected assets contain duplicate names.")
    actual_by_name = {str(item["name"]): item for item in actual_assets}
    expected_by_name = {str(item["name"]): item for item in portable_expected}
    declared_names = inspection.get("expectedAssetNames")
    if declared_names is not None and declared_names != sorted(expected_by_name):
        raise SkillpackError("Rebuilt expected assets do not match the inspected asset-name set.")
    unexpected = sorted(set(actual_by_name) - set(expected_by_name))
    if unexpected:
        raise SkillpackError("Draft contains unexpected assets: " + ", ".join(unexpected))
    mismatched: list[str] = []
    for name in sorted(set(actual_by_name) & set(expected_by_name)):
        actual = actual_by_name[name]
        wanted = expected_by_name[name]
        if (
            actual.get("state") != "uploaded"
            or actual.get("size") != wanted.get("size")
            or actual.get("digest") != wanted.get("digest")
        ):
            mismatched.append(name)
    if mismatched:
        raise SkillpackError("Draft contains mismatched assets: " + ", ".join(mismatched))
    missing_names = sorted(set(expected_by_name) - set(actual_by_name))
    return {
        "schemaVersion": 1,
        "releaseId": inspection["releaseId"],
        "tag": inspection["tag"],
        "existing": sorted(actual_by_name),
        "missing": [expected_by_name[name] for name in missing_names],
        "complete": not missing_names,
    }


def prepare_draft_removal_dossier(inspection: dict[str, Any]) -> tuple[dict[str, Any], str]:
    """Describe a manual break-glass boundary without authorizing or performing deletion."""

    if inspection.get("immutable") is not False or inspection.get("draft") is not True:
        raise SkillpackError("Only a mutable draft can receive manual removal guidance.")
    if inspection.get("prerelease") is not False:
        raise SkillpackError("The production recovery path refuses prerelease drafts.")
    tag_object = inspection.get("tagObject")
    if not isinstance(tag_object, dict) or tag_object.get("type") != "tag":
        raise SkillpackError("Removal guidance requires a verified annotated-tag identity.")
    url = inspection.get("url")
    if not isinstance(url, str) or not url.startswith("https://"):
        raise SkillpackError("Removal guidance requires the exact HTTPS release URL.")
    policy_sha = inspection.get("policySha")
    if not isinstance(policy_sha, str) or not _SHA.fullmatch(policy_sha):
        raise SkillpackError("Removal guidance requires the protected policy commit.")
    assets = inspection.get("assets")
    if not isinstance(assets, list):
        raise SkillpackError("Removal guidance requires an exact release asset inventory.")
    seen_names: set[str] = set()
    for asset in assets:
        if not isinstance(asset, dict):
            raise SkillpackError("Removal guidance release assets must be objects.")
        asset_id = asset.get("id")
        name = asset.get("name")
        size = asset.get("size")
        digest = asset.get("digest")
        uploader = asset.get("uploader")
        if isinstance(asset_id, bool) or not isinstance(asset_id, int) or asset_id < 1:
            raise SkillpackError("Removal guidance requires positive numeric asset IDs.")
        if not _is_safe_asset_name(name):
            raise SkillpackError("Removal guidance requires safe asset basenames.")
        assert isinstance(name, str)
        if name in seen_names:
            raise SkillpackError("Removal guidance refuses duplicate asset names.")
        seen_names.add(name)
        if isinstance(size, bool) or not isinstance(size, int) or size < 0:
            raise SkillpackError("Removal guidance requires exact non-negative asset sizes.")
        if asset.get("state") != "uploaded":
            raise SkillpackError("Removal guidance requires uploaded asset state.")
        if not isinstance(digest, str) or re.fullmatch(r"sha256:[0-9a-f]{64}", digest) is None:
            raise SkillpackError("Removal guidance requires exact SHA-256 asset digests.")
        if not isinstance(uploader, str) or not uploader:
            raise SkillpackError("Removal guidance requires exact asset uploaders.")
    dossier = {
        "schemaVersion": 1,
        "operation": "manual-break-glass-only",
        "releaseId": inspection["releaseId"],
        "policySha": policy_sha,
        "url": url,
        "tag": inspection["tag"],
        "tagObject": tag_object,
        "draft": True,
        "immutable": False,
        "mutable": True,
        "assets": assets,
        "warning": (
            "GitHub provides no conditional release DELETE precondition. Re-read the numeric "
            "release immediately before any separately authorized manual action."
        ),
    }
    assets_json = json.dumps(assets, indent=2, sort_keys=True)
    markdown = f"""# Manual draft-removal dossier

- Release ID: `{dossier["releaseId"]}`
- Protected policy commit: `{dossier["policySha"]}`
- Release URL: {dossier["url"]}
- Tag: `{dossier["tag"]}`
- Tag object: `{tag_object["objectSha"]}`
- Draft: `true`
- Immutable: `false`
- Mutable: `true`

## Exact release assets

```json
{assets_json}
```

GitHub does not provide a compare-and-delete precondition for releases. This workflow does not
authorize or perform deletion. An authorized maintainer must re-read the numeric release, confirm
it is still the same mutable draft, and then perform any break-glass action directly in GitHub.
The signed tag must not be removed or moved.
"""
    return dossier, markdown


def _read(path: Path) -> Any:
    return strict_json_bytes(path.read_bytes(), label=str(path))


def _write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Inspect and safely plan draft release recovery.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    inspect = subparsers.add_parser("inspect")
    inspect.add_argument("--release", type=Path, required=True)
    inspect.add_argument("--release-id", type=int, required=True)
    inspect.add_argument("--tag", required=True)
    inspect.add_argument("--policy-sha", required=True)
    inspect.add_argument("--tag-object-sha")
    inspect.add_argument("--source-sha")
    inspect.add_argument("--signature-kind", choices=("ssh", "openpgp"))
    inspect.add_argument("--signer-fingerprint")
    inspect.add_argument("--github-tag-verified", action="store_true")
    inspect.add_argument("--expected-title")
    inspect.add_argument("--expected-body-file", type=Path)
    inspect.add_argument("--expected-target-commitish")
    inspect.add_argument("--output", type=Path, required=True)
    body = subparsers.add_parser("expected-body")
    body.add_argument("--root", type=Path, required=True)
    body.add_argument("--pack", required=True)
    body.add_argument("--release", type=Path, required=True)
    body.add_argument("--source-sha", required=True)
    body.add_argument("--signature-kind", choices=("ssh", "openpgp"), required=True)
    body.add_argument("--signer-fingerprint", required=True)
    body.add_argument("--output", type=Path, required=True)
    reinspect = subparsers.add_parser("reinspect-bound")
    reinspect.add_argument("--release", type=Path, required=True)
    reinspect.add_argument("--trusted-inspection", type=Path, required=True)
    reinspect.add_argument("--release-id", type=int, required=True)
    reinspect.add_argument("--tag", required=True)
    reinspect.add_argument("--output", type=Path, required=True)
    resume = subparsers.add_parser("plan-resume")
    resume.add_argument("--inspection", type=Path, required=True)
    resume.add_argument("--expected", type=Path, nargs="+", required=True)
    resume.add_argument("--output", type=Path, required=True)
    removal = subparsers.add_parser("prepare-removal-dossier")
    removal.add_argument("--inspection", type=Path, required=True)
    removal.add_argument("--output", type=Path, required=True)
    removal.add_argument("--markdown-output", type=Path, required=True)
    seal = subparsers.add_parser("seal-intent")
    seal.add_argument("--root", type=Path, required=True)
    seal.add_argument("--release", type=Path, required=True)
    seal.add_argument("--mode", choices=("sealed-draft", "reconstructed-published"), required=True)
    seal.add_argument("--repository", required=True)
    seal.add_argument("--policy-sha", required=True)
    seal.add_argument("--workflow-name", required=True)
    seal.add_argument("--workflow-run-id", type=int, required=True)
    seal.add_argument("--workflow-run-attempt", type=int, required=True)
    seal.add_argument("--pack", required=True)
    seal.add_argument("--release-id", type=int, required=True)
    seal.add_argument("--tag", required=True)
    seal.add_argument("--tag-object-sha", required=True)
    seal.add_argument("--source-sha", required=True)
    seal.add_argument("--signature-kind", choices=("ssh", "openpgp"), required=True)
    seal.add_argument("--signer-fingerprint", required=True)
    seal.add_argument("--github-tag-verified", action="store_true")
    seal.add_argument("--expected-title", required=True)
    seal.add_argument("--expected-body-file", type=Path, required=True)
    seal.add_argument("--expected-target-commitish", required=True)
    seal.add_argument("--output", type=Path, required=True)
    verify = subparsers.add_parser("verify-published")
    verify.add_argument("--root", type=Path, required=True)
    verify.add_argument("--release", type=Path, required=True)
    verify.add_argument("--intent", type=Path, required=True)
    verify.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "inspect":
            release = _read(args.release)
            if not isinstance(release, dict):
                raise SkillpackError("release API response must be an object")
            _write(
                args.output,
                inspect_release(
                    release,
                    release_id=args.release_id,
                    tag=args.tag,
                    policy_sha=args.policy_sha,
                    tag_object_sha=args.tag_object_sha,
                    source_sha=args.source_sha,
                    signature_kind=args.signature_kind,
                    signer_fingerprint=args.signer_fingerprint,
                    github_tag_verified=args.github_tag_verified or None,
                    expected_title=args.expected_title,
                    expected_body=(
                        args.expected_body_file.read_text(encoding="utf-8")
                        if args.expected_body_file
                        else None
                    ),
                    expected_target_commitish=args.expected_target_commitish,
                ),
            )
            return 0
        if args.command == "expected-body":
            release = _read(args.release)
            if not isinstance(release, dict):
                raise SkillpackError("release API response must be an object")
            expected = expected_publishable_body(
                args.root,
                args.pack,
                release,
                source_sha=args.source_sha,
                signature_kind=args.signature_kind,
                signer_fingerprint=args.signer_fingerprint,
            )
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(expected, encoding="utf-8")
            return 0
        if args.command == "reinspect-bound":
            release = _read(args.release)
            trusted_inspection = _read(args.trusted_inspection)
            if not isinstance(release, dict):
                raise SkillpackError("release API response must be an object")
            if not isinstance(trusted_inspection, dict):
                raise SkillpackError("trusted inspection must be an object")
            _write(
                args.output,
                reinspect_bound_release(
                    release,
                    trusted_inspection,
                    release_id=args.release_id,
                    tag=args.tag,
                ),
            )
            return 0
        if args.command == "seal-intent":
            release = _read(args.release)
            if not isinstance(release, dict):
                raise SkillpackError("release API response must be an object")
            _write(
                args.output,
                seal_release_intent(
                    args.root,
                    release,
                    mode=args.mode,
                    repository_slug=args.repository,
                    policy_sha=args.policy_sha,
                    workflow_name=args.workflow_name,
                    workflow_run_id=args.workflow_run_id,
                    workflow_run_attempt=args.workflow_run_attempt,
                    pack_id=args.pack,
                    release_id=args.release_id,
                    tag=args.tag,
                    tag_object_sha=args.tag_object_sha,
                    source_sha=args.source_sha,
                    signature_kind=args.signature_kind,
                    signer_fingerprint=args.signer_fingerprint,
                    github_tag_verified=args.github_tag_verified,
                    expected_title=args.expected_title,
                    expected_body=args.expected_body_file.read_text(encoding="utf-8"),
                    expected_target_commitish=args.expected_target_commitish,
                ),
            )
            return 0
        if args.command == "verify-published":
            release = _read(args.release)
            intent = _read(args.intent)
            if not isinstance(release, dict) or not isinstance(intent, dict):
                raise SkillpackError("release and intent inputs must be objects")
            _write(args.output, verify_published_release(args.root, release, intent))
            return 0
        inspection = _read(args.inspection)
        if not isinstance(inspection, dict):
            raise SkillpackError("inspection must be an object")
        if args.command == "plan-resume":
            plan = plan_resume(inspection, expected_assets(args.expected))
            _write(args.output, plan)
            return 0
        dossier, markdown = prepare_draft_removal_dossier(inspection)
        _write(args.output, dossier)
        args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
        args.markdown_output.write_text(markdown, encoding="utf-8")
        return 0
    except (OSError, SkillpackError, ValueError) as exc:
        parser.exit(1, f"error: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
