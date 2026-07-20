from __future__ import annotations

import datetime as dt
import json
import shutil
import subprocess
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import pytest

import skillpack_tools.signing as signing
from skillpack_tools.evidence import (
    EvidenceAsset,
    build_evidence_envelope,
    evidence_freshness_errors,
    repository_relative_report_path,
    reviewer_authorization_errors,
    sha256_file,
    strict_load_json,
    validate_evidence_asset,
    validate_evidence_envelope,
)
from skillpack_tools.models import TrustedSigner, load_repository
from skillpack_tools.schema_validation import load_json_schema, schema_errors
from skillpack_tools.signing import (
    SigningKeyCandidate,
    ssh_key_fingerprint,
    verify_tag,
)
from skillpack_tools.util import SkillpackError, load_yaml

ROOT = Path(__file__).resolve().parents[1]


def test_repository_exposes_freshness_reviewer_and_signer_policy() -> None:
    config = load_repository(ROOT)
    policy = config.compatibility_evidence
    assert policy.max_age_days == 45
    assert policy.future_skew_minutes == 5
    assert not policy.independent_review_required
    assert [(item.github, item.github_id) for item in policy.authorized_reviewers] == [
        ("jecsand838", 170039284)
    ]
    assert config.trusted_signers == (
        TrustedSigner(
            kind="ssh",
            github="jecsand838",
            fingerprint="SHA256:RXn4sQSc9mwJb13oQVvUUkQvPw+B5N+WrRWH4elMJHg",
        ),
    )


def test_repository_schema_rejects_malformed_trust_policy() -> None:
    schema = load_json_schema(ROOT / "schemas/repository.schema.json")
    data = load_yaml(ROOT / "repository.yaml")
    invalid = deepcopy(data)
    invalid["release"]["trusted-signers"][0]["fingerprint"] = "SHA256:short"
    assert "release.trusted-signers" in "\n".join(schema_errors(invalid, schema, "repository.yaml"))
    invalid = deepcopy(data)
    invalid["compatibility-evidence"]["authorized-reviewers"][0]["github-id"] = 0
    assert "authorized-reviewers" in "\n".join(schema_errors(invalid, schema, "repository.yaml"))


def test_strict_evidence_json_rejects_duplicate_and_nonfinite_values(tmp_path: Path) -> None:
    path = tmp_path / "report.json"
    path.write_text('{"schemaVersion":2,"schemaVersion":2}', encoding="utf-8")
    with pytest.raises(SkillpackError, match="duplicate object key"):
        strict_load_json(path)
    path.write_text('{"value":NaN}', encoding="utf-8")
    with pytest.raises(SkillpackError, match="non-finite number"):
        strict_load_json(path)
    target = tmp_path / "target.json"
    target.write_text("{}", encoding="utf-8")
    path.unlink()
    path.symlink_to(target)
    with pytest.raises(SkillpackError, match="symlinks"):
        strict_load_json(path)


def test_freshness_and_reviewer_identity_are_fail_closed() -> None:
    policy = load_repository(ROOT).compatibility_evidence
    now = dt.datetime(2026, 7, 19, 12, 0, tzinfo=dt.UTC)
    assert evidence_freshness_errors("2026-06-04T12:00:00Z", policy, now=now) == []
    assert (
        "older than 45 days"
        in evidence_freshness_errors("2026-06-04T11:59:59Z", policy, now=now)[0]
    )
    assert evidence_freshness_errors("2026-07-19T12:05:00Z", policy, now=now) == []
    assert (
        "more than 5 minutes"
        in evidence_freshness_errors("2026-07-19T12:05:01Z", policy, now=now)[0]
    )

    reviewer = {"github": "JecSand838", "githubId": 170039284}
    assert (
        reviewer_authorization_errors(
            reviewer,
            policy,
            actor="jecsand838",
            actor_id=170039284,
            triggering_actor="JECSAND838",
        )
        == []
    )
    errors = reviewer_authorization_errors(
        reviewer,
        policy,
        actor="jecsand838",
        actor_id=1,
        triggering_actor="somebody-else",
    )
    assert "actor ID" in "\n".join(errors)
    assert "triggering actor" in "\n".join(errors)
    independent = replace(policy, independent_review_required=True)
    errors = reviewer_authorization_errors(
        reviewer,
        independent,
        pack_maintainers=["jecsand838"],
    )
    assert "independent" in "\n".join(errors)


def test_evidence_envelope_binds_raw_report_and_conventional_assets(tmp_path: Path) -> None:
    report = tmp_path / "codex.json"
    report_data = {
        "testedAt": "2026-07-18T00:00:00Z",
        "client": {"name": "codex"},
        "pack": {"id": "python-best-practices", "sourceSha": "a" * 40},
        "reviewer": {"github": "jecsand838", "githubId": 170039284},
    }
    report.write_text(json.dumps(report_data, separators=(",", ":")) + "\n", encoding="utf-8")
    envelope_data = build_evidence_envelope(
        repository_id=123,
        repository_slug="genaptic/skillsets",
        run_id=456,
        run_attempt=1,
        workflow_ref="genaptic/skillsets/.github/workflows/native-compatibility.yml@refs/heads/main",
        workflow_sha="c" * 40,
        event="workflow_dispatch",
        actor="jecsand838",
        actor_id=170039284,
        triggering_actor="jecsand838",
        source_sha="a" * 40,
        evidence_sha="b" * 40,
        report_repository_path="compatibility/reports/codex.json",
        report_sha256=sha256_file(report),
        client="codex",
        pack_id="python-best-practices",
        tested_at="2026-07-18T00:00:00Z",
    )
    assets = EvidenceAsset.from_report(report)
    assets.envelope.write_text(json.dumps(envelope_data) + "\n", encoding="utf-8")
    errors, loaded = validate_evidence_envelope(
        ROOT,
        assets.envelope,
        report_path=report,
        report_repository_path="compatibility/reports/codex.json",
        source_sha="a" * 40,
        evidence_sha="b" * 40,
        client="codex",
        pack_id="python-best-practices",
        repository_slug="genaptic/skillsets",
        workflow_run_id=456,
    )
    assert errors == []
    assert loaded == envelope_data

    errors, evidence = validate_evidence_asset(ROOT, report)
    assert evidence is None
    assert "attestation bundle" in "\n".join(errors)
    assets.attestation_bundle.write_text("{}\n", encoding="utf-8")
    errors, evidence = validate_evidence_asset(ROOT, report)
    assert errors == []
    assert evidence is not None and evidence.assets == assets

    report.write_text(json.dumps(report_data, indent=2) + "\n", encoding="utf-8")
    errors, _ = validate_evidence_envelope(ROOT, assets.envelope, report_path=report)
    assert "raw report bytes" in "\n".join(errors)


@pytest.mark.parametrize(
    "value",
    [
        "report.json",
        "/compatibility/reports/report.json",
        "compatibility/reports/../report.json",
        "compatibility//reports/report.json",
        "compatibility/reports/report.txt",
        "compatibility/reports/report:bad.json",
        r"compatibility\reports\report.json",
    ],
)
def test_evidence_report_path_is_strictly_repository_scoped(value: str) -> None:
    with pytest.raises(SkillpackError, match="compatibility/reports"):
        repository_relative_report_path(value)
    assert repository_relative_report_path("compatibility/reports/codex.json") == (
        "compatibility/reports/codex.json"
    )


def _git(root: Path, *arguments: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *arguments],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


@pytest.mark.skipif(shutil.which("ssh-keygen") is None, reason="ssh-keygen is required")
def test_tag_verification_requires_the_exact_pinned_ssh_fingerprint(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    _git(repository, "init", "-q")
    _git(repository, "config", "user.name", "Signer")
    _git(repository, "config", "user.email", "signer@example.com")
    _git(repository, "config", "commit.gpgsign", "false")
    tracked = repository / "tracked.txt"
    tracked.write_text("release\n", encoding="utf-8")
    _git(repository, "add", "tracked.txt")
    _git(repository, "commit", "-q", "--no-gpg-sign", "-m", "release")

    key = tmp_path / "signing-key"
    subprocess.run(
        ["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(key)],
        check=True,
    )
    public_key = key.with_suffix(".pub").read_text(encoding="utf-8")
    fingerprint = ssh_key_fingerprint(public_key)
    _git(repository, "config", "gpg.format", "ssh")
    _git(repository, "config", "user.signingkey", str(key.with_suffix(".pub")))
    _git(repository, "tag", "-s", "fixture-v1.0.0", "-m", "fixture v1.0.0")

    verified = verify_tag(
        repository,
        "fixture-v1.0.0",
        [TrustedSigner(kind="ssh", github="fixture", fingerprint=fingerprint)],
        candidate_keys=[SigningKeyCandidate(kind="ssh", material=public_key)],
    )
    assert verified.kind == "ssh"
    assert verified.fingerprint == fingerprint
    assert verified.source_sha == _git(repository, "rev-parse", "HEAD")

    with pytest.raises(SkillpackError, match="matched 0 trusted fingerprints"):
        verify_tag(
            repository,
            "fixture-v1.0.0",
            [
                TrustedSigner(
                    kind="ssh",
                    github="fixture",
                    fingerprint="SHA256:" + "A" * 43,
                )
            ],
            candidate_keys=[SigningKeyCandidate(kind="ssh", material=public_key)],
        )

    mismatched_key = tmp_path / "mismatched-key"
    subprocess.run(
        ["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(mismatched_key)],
        check=True,
    )
    mismatched_public_key = mismatched_key.with_suffix(".pub").read_text(encoding="utf-8")
    mismatched_fingerprint = ssh_key_fingerprint(mismatched_public_key)
    with pytest.raises(SkillpackError, match="matched 0 trusted fingerprints"):
        verify_tag(
            repository,
            "fixture-v1.0.0",
            [TrustedSigner(kind="ssh", github="fixture", fingerprint=mismatched_fingerprint)],
            candidate_keys=[SigningKeyCandidate(kind="ssh", material=mismatched_public_key)],
        )


def test_ssh_verifier_rejects_ambiguous_successful_candidates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    first = "SHA256:" + "A" * 43
    second = "SHA256:" + "B" * 43
    monkeypatch.setattr(signing, "_ssh_public_key", lambda material: material)
    monkeypatch.setattr(
        signing,
        "ssh_key_fingerprint",
        lambda material: first if material == "first" else second,
    )
    monkeypatch.setattr(
        signing,
        "_git",
        lambda *_args: subprocess.CompletedProcess(_args, 0, "", ""),
    )
    with pytest.raises(SkillpackError, match="matched 2 trusted fingerprints"):
        signing._verify_ssh_tag(
            tmp_path,
            "fixture-v1.0.0",
            {first, second},
            [
                SigningKeyCandidate(kind="ssh", material="first"),
                SigningKeyCandidate(kind="ssh", material="second"),
            ],
        )


def _openpgp_result(status: str) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(["gpg"], 0, "", status)


def test_openpgp_verifier_requires_the_full_validsig_fingerprint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fingerprint = "A" * 40
    monkeypatch.setattr(signing, "_openpgp_candidate_fingerprints", lambda _home: {fingerprint})
    monkeypatch.setattr(
        signing,
        "_run",
        lambda command, **_kwargs: (
            _openpgp_result(f"[GNUPG:] VALIDSIG {fingerprint} 0 0 0 0 0 0 0 0\n")
            if command[0] == "git"
            else subprocess.CompletedProcess(command, 0, "", "")
        ),
    )
    assert (
        signing._verify_openpgp_tag(
            tmp_path,
            "fixture-v1.0.0",
            {fingerprint},
            [SigningKeyCandidate(kind="openpgp", material="public key")],
        )
        == fingerprint
    )

    short = fingerprint[-16:]
    monkeypatch.setattr(
        signing,
        "_run",
        lambda command, **_kwargs: (
            _openpgp_result(f"[GNUPG:] VALIDSIG {short} 0 0 0 0 0 0 0 0\n")
            if command[0] == "git"
            else subprocess.CompletedProcess(command, 0, "", "")
        ),
    )
    with pytest.raises(SkillpackError, match="matched 0 trusted signing fingerprints"):
        signing._verify_openpgp_tag(
            tmp_path,
            "fixture-v1.0.0",
            {fingerprint},
            [SigningKeyCandidate(kind="openpgp", material="public key")],
        )


@pytest.mark.parametrize("revocation_status", ["REVKEYSIG", "KEYREVOKED"])
def test_openpgp_verifier_rejects_revoked_status_even_with_validsig(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, revocation_status: str
) -> None:
    fingerprint = "B" * 40
    monkeypatch.setattr(signing, "_openpgp_candidate_fingerprints", lambda _home: {fingerprint})
    status = (
        f"[GNUPG:] {revocation_status} DEADBEEF Fixture\n"
        f"[GNUPG:] VALIDSIG {fingerprint} 0 0 0 0 0 0 0 0\n"
    )
    monkeypatch.setattr(
        signing,
        "_run",
        lambda command, **_kwargs: (
            _openpgp_result(status)
            if command[0] == "git"
            else subprocess.CompletedProcess(command, 0, "", "")
        ),
    )
    with pytest.raises(SkillpackError, match="matched 0 trusted signing fingerprints"):
        signing._verify_openpgp_tag(
            tmp_path,
            "fixture-v1.0.0",
            {fingerprint},
            [SigningKeyCandidate(kind="openpgp", material="public key")],
        )
