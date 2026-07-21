from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from .models import Pack
from .path_safety import read_regular_bytes
from .schema_validation import load_json_schema, validate_schema_instance
from .util import sha256_bytes


class VerifiedSigner(Protocol):
    kind: str
    fingerprint: str


@dataclass(frozen=True)
class ReleaseEvidence:
    client: str
    tested_at: str
    report_path: Path
    provenance_path: Path
    attestation_bundle_path: Path
    ingestion_run_id: int
    ingestion_artifact_id: int
    ingestion_artifact_digest: str

    def as_metadata(self) -> dict[str, Any]:
        report_digest = sha256_bytes(read_regular_bytes(self.report_path, self.report_path.parent))
        provenance_digest = sha256_bytes(
            read_regular_bytes(self.provenance_path, self.provenance_path.parent)
        )
        bundle_digest = sha256_bytes(
            read_regular_bytes(self.attestation_bundle_path, self.attestation_bundle_path.parent)
        )
        return {
            "client": self.client,
            "testedAt": self.tested_at,
            "reportAsset": self.report_path.name,
            "reportSha256": report_digest,
            "provenanceAsset": self.provenance_path.name,
            "provenanceSha256": provenance_digest,
            "attestationBundleAsset": self.attestation_bundle_path.name,
            "attestationBundleSha256": bundle_digest,
            "ingestionRunId": self.ingestion_run_id,
            "ingestionArtifactId": self.ingestion_artifact_id,
            "ingestionArtifactDigest": self.ingestion_artifact_digest,
        }


def _pack_maturity(pack: Pack) -> str:
    return pack.maturity


def _pack_visibility(pack: Pack) -> str:
    return pack.visibility


def release_metadata(
    root: Path,
    pack: Pack,
    *,
    mode: str,
    source_sha: str | None,
    signer: VerifiedSigner | None,
    evidence: list[ReleaseEvidence],
    maturity: str | None = None,
    visibility: str | None = None,
) -> dict[str, Any]:
    """Build and schema-check the deterministic metadata embedded in a release ZIP."""

    evidence_metadata = [item.as_metadata() for item in evidence]
    data: dict[str, Any] = {
        "schemaVersion": 1,
        "mode": mode,
        "pack": {
            "id": pack.id,
            "version": pack.version,
            "maturity": maturity or _pack_maturity(pack),
            "releaseTag": pack.tag,
            "sourceSha": source_sha,
            "license": pack.license,
            "distributionVisibility": visibility or _pack_visibility(pack),
            "skills": list(pack.skills),
        },
        "tagSignature": (
            None if signer is None else {"type": signer.kind, "fingerprint": signer.fingerprint}
        ),
        "compatibilityEvidence": {
            "required": mode == "publishable",
            "reports": evidence_metadata,
        },
    }
    schema = load_json_schema(
        root / "schemas" / "release-metadata.schema.json",
        label="schemas/release-metadata.schema.json",
        root=root,
    )
    validate_schema_instance(data, schema, label="RELEASE-METADATA.json")
    return data


def release_metadata_bytes(data: dict[str, Any]) -> bytes:
    """Serialize without wall-clock data so equal inputs produce equal archive bytes."""

    return (json.dumps(data, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
