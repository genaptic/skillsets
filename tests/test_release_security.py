from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest
import yaml

import skillpack_tools.publication as publication
from skillpack_tools.generate import apply_generated_files
from skillpack_tools.models import Pack, get_pack, load_repository
from skillpack_tools.publication import (
    load_publication_record,
    prepare_publication_update,
    reconcile_publications,
    validate_publication_record,
)
from skillpack_tools.release_metadata import (
    ReleaseEvidence,
    release_metadata,
    release_metadata_bytes,
)
from skillpack_tools.release_recovery import (
    expected_asset_names,
    expected_publishable_body,
    inspect_release,
    plan_resume,
    prepare_draft_removal_dossier,
    reinspect_bound_release,
)
from skillpack_tools.util import SkillpackError, dump_yaml, load_yaml, sha256_bytes

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class _Signer:
    kind: str = "ssh"
    fingerprint: str = "SHA256:RXn4sQSc9mwJb13oQVvUUkQvPw+B5N+WrRWH4elMJHg"


def _record(pack_id: str = "python-best-practices") -> dict[str, object]:
    pack = get_pack(ROOT, pack_id)
    repository = load_repository(ROOT)
    return {
        "schemaVersion": 1,
        "repository": repository.slug,
        "packId": pack.id,
        "version": pack.version,
        "releaseId": 123,
        "tag": pack.tag,
        "url": f"{repository.web_url}/releases/tag/{pack.tag}",
        "sourceSha": "a" * 40,
        "baseCommit": "c" * 40,
        "publishedAt": "2026-07-19T12:34:56Z",
        "immutable": True,
        "draft": False,
        "prerelease": False,
    }


def _evidence(tmp_path: Path, client: str, *, report_text: str = "{}\n") -> ReleaseEvidence:
    report = tmp_path / f"{client}.json"
    envelope = tmp_path / f"{client}.envelope.json"
    bundle = tmp_path / f"{client}.attestation.jsonl"
    report.write_text(report_text, encoding="utf-8")
    envelope.write_text('{"schemaVersion":1}\n', encoding="utf-8")
    bundle.write_text('{"dsseEnvelope":{}}\n', encoding="utf-8")
    return ReleaseEvidence(
        client=client,
        tested_at="2026-07-19T12:00:00Z",
        report_path=report,
        provenance_path=envelope,
        attestation_bundle_path=bundle,
        ingestion_run_id=10,
        ingestion_artifact_id=20,
        ingestion_artifact_digest="sha256:" + "b" * 64,
    )


def test_release_metadata_has_strict_draft_and_publishable_modes(tmp_path: Path) -> None:
    pack = get_pack(ROOT, "python-best-practices")
    draft = release_metadata(
        ROOT,
        pack,
        mode="draft-rehearsal",
        source_sha="a" * 40,
        signer=None,
        evidence=[],
    )
    assert draft["tagSignature"] is None
    assert draft["compatibilityEvidence"] == {"required": False, "reports": []}

    evidence = [_evidence(tmp_path, client) for client in ("claude-code", "codex", "opencode")]
    formal = release_metadata(
        ROOT,
        pack,
        mode="publishable",
        source_sha="a" * 40,
        signer=_Signer(),
        evidence=evidence,
        maturity="stable",
        visibility="public",
    )
    assert [item["client"] for item in formal["compatibilityEvidence"]["reports"]] == [
        "claude-code",
        "codex",
        "opencode",
    ]
    serialized = release_metadata_bytes(formal)
    assert b"generatedAt" not in serialized
    assert b"archiveSha256" not in serialized
    assert str(tmp_path).encode() not in serialized


def test_release_metadata_binds_exact_raw_evidence_bytes(tmp_path: Path) -> None:
    pack = get_pack(ROOT, "python-best-practices")
    items = [_evidence(tmp_path, client) for client in ("claude-code", "codex", "opencode")]
    first = release_metadata(
        ROOT,
        pack,
        mode="publishable",
        source_sha="a" * 40,
        signer=_Signer(),
        evidence=items,
        maturity="stable",
    )
    items[1].report_path.write_text("{ }\n", encoding="utf-8")
    second = release_metadata(
        ROOT,
        pack,
        mode="publishable",
        source_sha="a" * 40,
        signer=_Signer(),
        evidence=items,
        maturity="stable",
    )
    assert sha256_bytes(release_metadata_bytes(first)) != sha256_bytes(
        release_metadata_bytes(second)
    )


def test_publication_record_and_plan_are_exactly_bound(monkeypatch: pytest.MonkeyPatch) -> None:
    record = _record()
    pack = validate_publication_record(ROOT, record)
    assert pack.id == record["packId"]
    monkeypatch.setattr("skillpack_tools.publication._require_clean", lambda _root: None)
    monkeypatch.setattr("skillpack_tools.publication._git_head", lambda _root: "c" * 40)
    monkeypatch.setattr(
        "skillpack_tools.publication.apply_generated_files", lambda *_args, **_kwargs: []
    )
    monkeypatch.setattr(
        "skillpack_tools.publication._preview_publication_changes",
        lambda *_args, **_kwargs: {
            "unifiedPatch": "diff --git a/skillpack.yaml b/skillpack.yaml\n",
            "changedFiles": [
                {
                    "path": "packs/python/best-practices/skillpack.yaml",
                    "beforeSha256": "1" * 64,
                    "afterSha256": "2" * 64,
                    "beforeMode": "0644",
                    "afterMode": "0644",
                }
            ],
            "generatedOutputs": [{"path": "catalog.json", "sha256": "3" * 64, "mode": "0644"}],
            "generatedOutputSetSha256": "4" * 64,
        },
    )
    plan = prepare_publication_update(ROOT, record)
    assert plan["baseCommit"] == record["baseCommit"]
    assert plan["unifiedPatch"].startswith("diff --git")
    assert plan["changedFiles"][0]["afterSha256"] == "2" * 64
    assert plan["generatedOutputSetSha256"] == "4" * 64
    proposed = plan["proposedManifest"]
    assert "state: published" in proposed
    assert "latest-release:" in proposed
    assert "source-sha: " + "a" * 40 in proposed
    with pytest.raises(SkillpackError, match="plan-digest"):
        prepare_publication_update(ROOT, record, apply=True, plan_digest="0" * 64)
    with pytest.raises(SkillpackError, match="baseCommit"):
        prepare_publication_update(ROOT, {**record, "baseCommit": "b" * 40})


def test_publication_record_loads_safely_from_external_artifact_path(tmp_path: Path) -> None:
    path = tmp_path / "publication-record.json"
    path.write_text(json.dumps(_record()) + "\n", encoding="utf-8")
    assert load_publication_record(ROOT, path) == _record()


def test_full_index_patch_includes_untracked_binary_without_mutating_index(
    tmp_path: Path,
) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "Fixture"], check=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "config", "user.email", "fixture@example.com"],
        check=True,
    )
    tracked = tmp_path / "tracked.txt"
    tracked.write_text("before\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "tracked.txt"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-q", "-m", "fixture"], check=True)
    index_path = Path(
        subprocess.check_output(
            ["git", "-C", str(tmp_path), "rev-parse", "--git-path", "index"], text=True
        ).strip()
    )
    if not index_path.is_absolute():
        index_path = tmp_path / index_path
    index_before = index_path.read_bytes()
    tracked.write_text("after\n", encoding="utf-8")
    (tmp_path / "new.bin").write_bytes(b"\x00binary\xff")

    patch, changed = publication._git_patch_and_paths(tmp_path, ["tracked.txt", "new.bin"])
    assert changed == ["new.bin", "tracked.txt"]
    assert "diff --git a/new.bin b/new.bin" in patch
    assert "GIT binary patch" in patch
    assert "diff --git a/tracked.txt b/tracked.txt" in patch
    assert index_path.read_bytes() == index_before


def test_publication_preview_uses_exact_base_and_preserves_newer_candidate(
    tmp_path: Path,
) -> None:
    def ignore(_directory: str, names: list[str]) -> set[str]:
        excluded = {
            ".coverage",
            ".git",
            ".idea",
            ".pytest_cache",
            ".ruff_cache",
            ".venv",
            "__pycache__",
            "tmp",
        }
        return {name for name in names if name in excluded or name.endswith((".pyc", ".pyo"))}

    repository = tmp_path / "repository"
    shutil.copytree(ROOT, repository, ignore=ignore)
    manifest = repository / "packs/python/best-practices/skillpack.yaml"

    def set_lifecycle(version: str, maturity: str) -> None:
        data = load_yaml(manifest)
        data["version"] = version
        data["maturity"] = maturity
        manifest.write_text(dump_yaml(data), encoding="utf-8")
        pack = get_pack(repository, "python-best-practices")
        for skill in pack.skills:
            skill_file = pack.path / "skills" / skill / "SKILL.md"
            text = skill_file.read_text(encoding="utf-8")
            text = re.sub(r'(?m)^  version: "[^"]+"$', f'  version: "{version}"', text)
            text = re.sub(r'(?m)^  maturity: "[^"]+"$', f'  maturity: "{maturity}"', text)
            skill_file.write_text(text, encoding="utf-8")

    set_lifecycle("1.0.0", "stable")
    apply_generated_files(repository)
    subprocess.run(["git", "init", "-q", str(repository)], check=True)
    subprocess.run(["git", "-C", str(repository), "config", "user.name", "Fixture"], check=True)
    subprocess.run(
        ["git", "-C", str(repository), "config", "user.email", "fixture@example.com"],
        check=True,
    )
    subprocess.run(["git", "-C", str(repository), "add", "-A"], check=True)
    subprocess.run(
        ["git", "-C", str(repository), "commit", "-q", "-m", "released source"],
        check=True,
    )
    source_sha = subprocess.check_output(
        ["git", "-C", str(repository), "rev-parse", "HEAD"], text=True
    ).strip()

    set_lifecycle("1.1.0", "release-candidate")
    apply_generated_files(repository)
    subprocess.run(["git", "-C", str(repository), "add", "-A"], check=True)
    subprocess.run(
        ["git", "-C", str(repository), "commit", "-q", "-m", "next candidate"],
        check=True,
    )
    base_commit = subprocess.check_output(
        ["git", "-C", str(repository), "rev-parse", "HEAD"], text=True
    ).strip()
    config = load_repository(repository)
    record = {
        "schemaVersion": 1,
        "repository": config.slug,
        "packId": "python-best-practices",
        "version": "1.0.0",
        "releaseId": 123,
        "tag": "python-best-practices-v1.0.0",
        "url": f"{config.web_url}/releases/tag/python-best-practices-v1.0.0",
        "sourceSha": source_sha,
        "baseCommit": base_commit,
        "publishedAt": "2026-07-19T12:34:56Z",
        "immutable": True,
        "draft": False,
        "prerelease": False,
    }
    plan = prepare_publication_update(repository, record)
    assert plan["baseCommit"] == base_commit
    assert plan["unifiedPatch"].startswith("diff --git ")
    assert plan["changedFiles"]
    assert plan["generatedOutputs"]
    assert any(item["path"] == "catalog.json" for item in plan["generatedOutputs"])
    proposed = yaml.safe_load(plan["proposedManifest"])
    assert proposed["version"] == "1.1.0"
    assert proposed["maturity"] == "release-candidate"
    assert proposed["publication"]["latest-release"]["version"] == "1.0.0"
    applied = prepare_publication_update(
        repository,
        record,
        apply=True,
        plan_digest=plan["planDigest"],
    )
    assert applied == plan
    updated = get_pack(repository, "python-best-practices")
    assert updated.version == "1.1.0"
    assert updated.published_version == "1.0.0"
    assert updated.source_sha == source_sha


def test_publication_record_allows_released_history_but_not_newer_or_regressive() -> None:
    repository = load_repository(ROOT)
    historical = _record()
    historical["version"] = "0.9.0"
    historical["tag"] = "python-best-practices-v0.9.0"
    historical["url"] = f"{repository.web_url}/releases/tag/{historical['tag']}"
    assert validate_publication_record(ROOT, historical).version == "1.0.0"

    newer = {**historical, "version": "2.0.0", "tag": "python-best-practices-v2.0.0"}
    newer["url"] = f"{repository.web_url}/releases/tag/{newer['tag']}"
    with pytest.raises(SkillpackError, match="newer than canonical candidate"):
        validate_publication_record(ROOT, newer)

    published = Pack(
        root=ROOT,
        path=ROOT / "packs/example/history",
        raw={
            "id": "python-best-practices",
            "version": "1.1.0",
            "publication": {
                "state": "published",
                "latest-release": {
                    "version": "1.0.0",
                    "source-sha": "b" * 40,
                    "release-id": 99,
                    "released-at": "2026-07-18T12:34:56Z",
                },
            },
        },
    )
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr("skillpack_tools.publication.get_pack", lambda *_args: published)
        with pytest.raises(SkillpackError, match="precedes existing latest release"):
            validate_publication_record(ROOT, historical)


@pytest.mark.parametrize("failure_stage", ["generation", "validation"])
def test_publication_apply_rolls_back_manifest_and_generated_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure_stage: str
) -> None:
    manifest = tmp_path / "pack.yaml"
    generated = tmp_path / "generated.json"
    created = tmp_path / "created.json"
    manifest.write_text("before manifest\n", encoding="utf-8")
    generated.write_text("before generated\n", encoding="utf-8")
    plan = {
        "baseCommit": "c" * 40,
        "planDigest": "d" * 64,
        "manifestPath": "pack.yaml",
        "manifestPreimageSha256": sha256_bytes(manifest.read_bytes()),
        "proposedManifest": "after manifest\n",
        "changedFiles": [
            {
                "path": "pack.yaml",
                "beforeSha256": sha256_bytes(manifest.read_bytes()),
                "afterSha256": sha256_bytes(b"after manifest\n"),
                "beforeMode": "0644",
                "afterMode": "0644",
            },
            {
                "path": "generated.json",
                "beforeSha256": sha256_bytes(generated.read_bytes()),
                "afterSha256": sha256_bytes(b"after generated\n"),
                "beforeMode": "0644",
                "afterMode": "0644",
            },
            {
                "path": "created.json",
                "beforeSha256": None,
                "afterSha256": sha256_bytes(b"new generated\n"),
                "beforeMode": None,
                "afterMode": "0644",
            },
        ],
        "generatedOutputs": [],
        "generatedOutputSetSha256": sha256_bytes(b"[]"),
        "unifiedPatch": "unused",
    }
    monkeypatch.setattr("skillpack_tools.publication._plan_payload", lambda *_args: plan)
    monkeypatch.setattr("skillpack_tools.publication._git_head", lambda _root: "c" * 40)

    def generate(_root: Path, **_kwargs: object) -> list[str]:
        generated.write_text("after generated\n", encoding="utf-8")
        created.write_text("new generated\n", encoding="utf-8")
        if failure_stage == "generation":
            raise SkillpackError("generation failed")
        return ["generated.json"]

    monkeypatch.setattr("skillpack_tools.publication.apply_generated_files", generate)
    if failure_stage == "validation":
        monkeypatch.setattr(
            "skillpack_tools.publication.validate_repository", lambda *_args, **_kwargs: object()
        )
        monkeypatch.setattr(
            "skillpack_tools.publication.raise_for_result",
            lambda _result: (_ for _ in ()).throw(SkillpackError("validation failed")),
        )
    with pytest.raises(SkillpackError, match=f"{failure_stage} failed"):
        prepare_publication_update(
            tmp_path,
            {},
            apply=True,
            plan_digest="d" * 64,
        )
    assert manifest.read_text(encoding="utf-8") == "before manifest\n"
    assert generated.read_text(encoding="utf-8") == "before generated\n"
    assert not created.exists()


@pytest.mark.parametrize("failure", [KeyboardInterrupt(), SystemExit(29)])
def test_publication_apply_rolls_back_process_interrupts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure: BaseException,
) -> None:
    manifest = tmp_path / "pack.yaml"
    generated = tmp_path / "generated.json"
    created = tmp_path / "new-generated" / "created.json"
    manifest.write_text("before manifest\n", encoding="utf-8")
    generated.write_text("before generated\n", encoding="utf-8")
    manifest.chmod(0o600)
    generated.chmod(0o640)
    plan = {
        "baseCommit": "c" * 40,
        "planDigest": "d" * 64,
        "manifestPath": "pack.yaml",
        "manifestPreimageSha256": sha256_bytes(manifest.read_bytes()),
        "proposedManifest": "after manifest\n",
        "changedFiles": [
            {
                "path": "pack.yaml",
                "beforeSha256": sha256_bytes(manifest.read_bytes()),
                "afterSha256": sha256_bytes(b"after manifest\n"),
                "beforeMode": "0600",
                "afterMode": "0644",
            },
            {
                "path": "generated.json",
                "beforeSha256": sha256_bytes(generated.read_bytes()),
                "afterSha256": sha256_bytes(b"after generated\n"),
                "beforeMode": "0640",
                "afterMode": "0640",
            },
            {
                "path": "new-generated/created.json",
                "beforeSha256": None,
                "afterSha256": sha256_bytes(b"new generated\n"),
                "beforeMode": None,
                "afterMode": "0644",
            },
        ],
        "generatedOutputs": [],
        "generatedOutputSetSha256": sha256_bytes(b"[]"),
        "unifiedPatch": "unused",
    }
    monkeypatch.setattr("skillpack_tools.publication._plan_payload", lambda *_args: plan)
    monkeypatch.setattr("skillpack_tools.publication._git_head", lambda _root: "c" * 40)

    def interrupt(_root: Path, **_kwargs: object) -> list[str]:
        generated.write_text("after generated\n", encoding="utf-8")
        created.parent.mkdir()
        created.write_text("new generated\n", encoding="utf-8")
        raise failure

    monkeypatch.setattr("skillpack_tools.publication.apply_generated_files", interrupt)
    with pytest.raises(type(failure)) as raised:
        prepare_publication_update(tmp_path, {}, apply=True, plan_digest="d" * 64)
    if isinstance(failure, SystemExit):
        assert raised.value.code == 29
    assert manifest.read_text(encoding="utf-8") == "before manifest\n"
    assert generated.read_text(encoding="utf-8") == "before generated\n"
    assert manifest.stat().st_mode & 0o777 == 0o600
    assert generated.stat().st_mode & 0o777 == 0o640
    assert not created.exists()
    assert not created.parent.exists()


def test_publication_reconciliation_reports_both_drift_directions() -> None:
    pack = get_pack(ROOT, "python-best-practices")
    release = {
        "releaseId": 123,
        "tag": pack.tag,
        "sourceSha": "a" * 40,
        "publishedAt": "2026-07-19T12:34:56Z",
        "immutable": True,
        "draft": False,
        "prerelease": False,
    }
    report = reconcile_publications(ROOT, [release])
    assert not report["ok"]
    assert any(item["kind"] == "release-manifest-mismatch" for item in report["drift"])


def test_publication_reconciliation_reports_generated_membership_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def stale_outputs(_root: Path, *, check: bool = False) -> list[str]:
        assert check
        raise SkillpackError(
            "Generated files are missing or stale:\n"
            "  - dist/public/opencode/withdrawn-pack/index.json\n"
            "  - catalog.json"
        )

    monkeypatch.setattr("skillpack_tools.publication.apply_generated_files", stale_outputs)
    monkeypatch.setattr("skillpack_tools.publication.discover_packs", lambda _root: [])
    report = reconcile_publications(ROOT, [])
    assert report == {
        "schemaVersion": 1,
        "ok": False,
        "drift": [
            {"kind": "generated-output-drift", "path": "catalog.json"},
            {
                "kind": "generated-output-drift",
                "path": "dist/public/opencode/withdrawn-pack/index.json",
            },
        ],
    }


@pytest.mark.parametrize("state", ["published", "withdrawn"])
def test_publication_reconciliation_accepts_exact_published_history(
    state: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    pack = Pack(
        root=ROOT,
        path=ROOT / "packs/example/exact",
        raw={
            "id": "exact-pack",
            "version": "1.2.3",
            "publication": {
                "state": state,
                "latest-release": {
                    "version": "1.2.3",
                    "source-sha": "a" * 40,
                    "release-id": 123,
                    "released-at": "2026-07-19T12:34:56Z",
                },
            },
        },
    )
    monkeypatch.setattr("skillpack_tools.publication.discover_packs", lambda _root: [pack])
    report = reconcile_publications(
        ROOT,
        [
            {
                "releaseId": 123,
                "tag": "exact-pack-v1.2.3",
                "sourceSha": "a" * 40,
                "publishedAt": "2026-07-19T12:34:56Z",
                "immutable": True,
                "draft": False,
                "prerelease": False,
                "annotated": True,
                "tagVerified": True,
            }
        ],
    )
    assert report == {"schemaVersion": 1, "ok": True, "drift": []}


def test_reconciliation_preserves_published_history_while_candidate_advances(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pack = Pack(
        root=ROOT,
        path=ROOT / "packs/example/candidate",
        raw={
            "id": "candidate-pack",
            "version": "1.3.0",
            "publication": {
                "state": "published",
                "latest-release": {
                    "version": "1.2.3",
                    "source-sha": "a" * 40,
                    "release-id": 123,
                    "released-at": "2026-07-19T12:34:56Z",
                },
            },
        },
    )
    monkeypatch.setattr("skillpack_tools.publication.discover_packs", lambda _root: [pack])
    old_release = {
        "releaseId": 123,
        "tag": "candidate-pack-v1.2.3",
        "sourceSha": "a" * 40,
        "publishedAt": "2026-07-19T12:34:56Z",
        "immutable": True,
        "draft": False,
        "prerelease": False,
        "annotated": True,
        "tagVerified": True,
    }
    assert reconcile_publications(ROOT, [old_release])["ok"]

    current_release = {
        **old_release,
        "releaseId": 124,
        "tag": "candidate-pack-v1.3.0",
        "sourceSha": "b" * 40,
        "publishedAt": "2026-07-20T12:34:56Z",
    }
    report = reconcile_publications(ROOT, [old_release, current_release])
    assert not report["ok"]
    candidate_drift = [
        item for item in report["drift"] if item.get("tag") == "candidate-pack-v1.3.0"
    ]
    assert candidate_drift
    assert all(item["kind"] == "release-manifest-mismatch" for item in candidate_drift)

    missing = reconcile_publications(ROOT, [])
    assert missing["drift"] == [
        {
            "kind": "manifest-release-missing",
            "packId": "candidate-pack",
            "tag": "candidate-pack-v1.2.3",
        }
    ]


def test_reconciliation_audits_historical_releases_and_orphaned_tags(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pack = Pack(
        root=ROOT,
        path=ROOT / "packs/example/history",
        raw={
            "id": "history-pack",
            "version": "1.1.0",
            "publication": {
                "state": "published",
                "latest-release": {
                    "version": "1.1.0",
                    "source-sha": "b" * 40,
                    "release-id": 2,
                    "released-at": "2026-07-19T12:34:56Z",
                },
            },
        },
    )
    monkeypatch.setattr("skillpack_tools.publication.discover_packs", lambda _root: [pack])
    monkeypatch.setattr("skillpack_tools.publication._generated_output_drift", lambda _root: [])
    releases = [
        {
            "releaseId": 1,
            "tag": "history-pack-v1.0.0",
            "sourceSha": "a" * 40,
            "publishedAt": "2026-07-18T12:34:56Z",
            "immutable": False,
            "draft": False,
            "prerelease": False,
            "annotated": True,
            "tagVerified": True,
        }
    ]
    tags = [
        {
            "tag": "history-pack-v1.0.0",
            "sourceSha": "a" * 40,
            "annotated": True,
            "tagVerified": True,
        },
        {
            "tag": "history-pack-v1.0.1",
            "sourceSha": "c" * 40,
            "annotated": True,
            "tagVerified": True,
        },
        {"tag": "history-pack-v1.0", "sourceSha": "d" * 40},
        {"tag": "unknown-pack-v1.0.0", "sourceSha": "e" * 40},
    ]
    report = reconcile_publications(ROOT, releases, tags)
    kinds = {item["kind"] for item in report["drift"]}
    assert "release-not-publishable" in kinds
    assert "tag-release-missing" in kinds
    assert "invalid-pack-tag" in kinds
    assert "unknown-pack-tag" in kinds


def test_reconciliation_requires_release_tag_presence_and_exact_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pack = Pack(
        root=ROOT,
        path=ROOT / "packs/example/exact-tag",
        raw={
            "id": "exact-tag-pack",
            "version": "1.0.0",
            "publication": {
                "state": "published",
                "latest-release": {
                    "version": "1.0.0",
                    "source-sha": "a" * 40,
                    "release-id": 1,
                    "released-at": "2026-07-19T12:34:56Z",
                },
            },
        },
    )
    release = {
        "releaseId": 1,
        "tag": "exact-tag-pack-v1.0.0",
        "sourceSha": "a" * 40,
        "publishedAt": "2026-07-19T12:34:56Z",
        "immutable": True,
        "draft": False,
        "prerelease": False,
        "annotated": True,
        "tagVerified": True,
    }
    monkeypatch.setattr("skillpack_tools.publication.discover_packs", lambda _root: [pack])
    monkeypatch.setattr("skillpack_tools.publication._generated_output_drift", lambda _root: [])
    missing = reconcile_publications(ROOT, [release], [])
    assert any(item["kind"] == "release-tag-missing" for item in missing["drift"])
    mismatched = reconcile_publications(
        ROOT,
        [release],
        [
            {
                "tag": release["tag"],
                "sourceSha": "f" * 40,
                "annotated": True,
                "tagVerified": True,
            }
        ],
    )
    assert any(
        item["kind"] == "release-tag-mismatch" and item["field"] == "sourceSha"
        for item in mismatched["drift"]
    )


def _release(*, assets: list[dict[str, object]], draft: bool = True) -> dict[str, object]:
    return {
        "id": 42,
        "tag_name": "python-best-practices-v1.0.0",
        "html_url": (
            "https://github.com/genaptic/skillsets/releases/tag/python-best-practices-v1.0.0"
        ),
        "name": "Python Best Practices 1.0.0",
        "body": "release notes\n",
        "target_commitish": "main",
        "draft": draft,
        "prerelease": False,
        "immutable": False,
        "assets": assets,
    }


def _expected_recovery_assets(digest: str) -> list[dict[str, object]]:
    return [
        {"name": name, "size": 12, "digest": digest, "path": f"/{name}"}
        for name in expected_asset_names("python-best-practices-v1.0.0")
    ]


def _publishable_body(digest: str = "a" * 64) -> str:
    pack = get_pack(ROOT, "python-best-practices")
    changelog = (pack.path / "CHANGELOG.md").read_text(encoding="utf-8").strip()
    evidence = "\n".join(
        f"- `{client}`: report `{client}.json` (`{digest}`), envelope "
        f"`{client}.envelope.json` (`{digest}`), attestation bundle "
        f"`{client}.attestation.jsonl` (`{digest}`)"
        for client in ("claude-code", "codex", "opencode")
    )
    return f"""# {pack.display_name} {pack.version}

**Mode: PUBLISHABLE RELEASE**

- Pack: `{pack.id}`
- Tag: `{pack.tag}`
- Source SHA: `{"a" * 40}`
- Tag signer: ssh `SHA256:{"A" * 43}`
- License: `{pack.license}`
- Skills: {", ".join(f"`{skill}`" for skill in pack.skills)}
- Archive SHA-256: `{digest}`

## Compatibility evidence

{evidence}

## Pack changelog

{changelog}
"""


def test_recovery_initial_inspection_validates_the_publishable_body_contract() -> None:
    digest = "a" * 64
    release = _release(
        assets=[
            {
                "id": 1,
                "name": "python-best-practices-v1.0.0.zip",
                "size": 12,
                "state": "uploaded",
                "digest": f"sha256:{digest}",
                "uploader": {"login": "maintainer"},
            }
        ]
    )
    release["body"] = _publishable_body(digest)
    expected = expected_publishable_body(
        ROOT,
        "python-best-practices",
        release,
        source_sha="a" * 40,
        signature_kind="ssh",
        signer_fingerprint="SHA256:" + "A" * 43,
    )
    assert expected == release["body"]

    extra_newline = {**release, "body": str(release["body"]) + "\n"}
    with pytest.raises(SkillpackError, match="release body"):
        expected_publishable_body(
            ROOT,
            "python-best-practices",
            extra_newline,
            source_sha="a" * 40,
            signature_kind="ssh",
            signer_fingerprint="SHA256:" + "A" * 43,
        )

    arbitrary = {**release, "body": "arbitrary release notes\n"}
    with pytest.raises(SkillpackError, match="release body"):
        expected_publishable_body(
            ROOT,
            "python-best-practices",
            arbitrary,
            source_sha="a" * 40,
            signature_kind="ssh",
            signer_fingerprint="SHA256:" + "A" * 43,
        )
    mismatched = {**release, "assets": [{**release["assets"][0], "digest": "sha256:" + "b" * 64}]}
    with pytest.raises(SkillpackError, match="does not match the existing asset"):
        expected_publishable_body(
            ROOT,
            "python-best-practices",
            mismatched,
            source_sha="a" * 40,
            signature_kind="ssh",
            signer_fingerprint="SHA256:" + "A" * 43,
        )


def test_recovery_state_machine_uploads_only_missing_exact_assets() -> None:
    digest = "sha256:" + "a" * 64
    expected = _expected_recovery_assets(digest)
    inspection = inspect_release(
        _release(
            assets=[
                {
                    "id": index,
                    "name": item["name"],
                    "size": 12,
                    "state": "uploaded",
                    "digest": digest,
                    "uploader": {"login": "maintainer"},
                }
                for index, item in enumerate(expected[:-1], start=1)
            ]
        ),
        release_id=42,
        tag="python-best-practices-v1.0.0",
    )
    plan = plan_resume(inspection, expected)
    assert [item["name"] for item in plan["missing"]] == [expected[-1]["name"]]
    assert not plan["complete"]


def test_recovery_refuses_suspicious_or_destructive_state() -> None:
    digest = "sha256:" + "a" * 64
    expected = _expected_recovery_assets(digest)
    inspection = inspect_release(
        _release(
            assets=[
                {
                    "id": 1,
                    "name": "unexpected.exe",
                    "size": 1,
                    "state": "uploaded",
                    "digest": "sha256:" + "a" * 64,
                    "uploader": {"login": "maintainer"},
                }
            ]
        ),
        release_id=42,
        tag="python-best-practices-v1.0.0",
    )
    with pytest.raises(SkillpackError, match="unexpected assets"):
        plan_resume(inspection, expected)
    with pytest.raises(SkillpackError, match="asset-name set"):
        plan_resume(inspection, expected[:-1])
    duplicate_inspection = {**inspection, "assets": inspection["assets"] * 2}
    with pytest.raises(SkillpackError, match="duplicate asset names"):
        plan_resume(duplicate_inspection, expected)
    mismatched_name = str(expected[0]["name"])
    mismatched_inspection = inspect_release(
        _release(
            assets=[
                {
                    "id": 1,
                    "name": mismatched_name,
                    "size": 12,
                    "state": "uploaded",
                    "digest": digest,
                    "uploader": {"login": "maintainer"},
                }
            ]
        ),
        release_id=42,
        tag="python-best-practices-v1.0.0",
    )
    mismatched_expected = _expected_recovery_assets("sha256:" + "b" * 64)
    with pytest.raises(SkillpackError, match="mismatched assets"):
        plan_resume(mismatched_inspection, mismatched_expected)
    verified_inspection = inspect_release(
        _release(assets=[]),
        release_id=42,
        tag="python-best-practices-v1.0.0",
        policy_sha="c" * 40,
        tag_object_sha="b" * 40,
        source_sha="a" * 40,
        signature_kind="ssh",
        signer_fingerprint="SHA256:" + "A" * 43,
        github_tag_verified=True,
    )
    dossier, markdown = prepare_draft_removal_dossier(verified_inspection)
    assert dossier["operation"] == "manual-break-glass-only"
    assert dossier["policySha"] == "c" * 40
    assert "## Exact release assets" in markdown
    assert "does not provide a compare-and-delete" in markdown


def test_recovery_inspection_binds_release_and_verified_tag_identity() -> None:
    inspection = inspect_release(
        _release(assets=[]),
        release_id=42,
        tag="python-best-practices-v1.0.0",
        tag_object_sha="b" * 40,
        source_sha="a" * 40,
        signature_kind="ssh",
        signer_fingerprint="SHA256:" + "A" * 43,
        github_tag_verified=True,
        expected_title="Python Best Practices 1.0.0",
        expected_body="release notes\n",
        expected_target_commitish="main",
    )
    assert inspection["schemaVersion"] == 2
    assert inspection["title"] == "Python Best Practices 1.0.0"
    assert inspection["body"] == "release notes\n"
    assert inspection["targetCommitish"] == "main"
    assert inspection["tagObject"] == {
        "type": "tag",
        "objectSha": "b" * 40,
        "sourceSha": "a" * 40,
        "githubVerified": True,
        "signature": {"type": "ssh", "fingerprint": "SHA256:" + "A" * 43},
    }
    assert inspection["expectedAssetNames"] == expected_asset_names("python-best-practices-v1.0.0")


def test_recovery_removal_rebinds_the_complete_verified_inspection() -> None:
    release = _release(assets=[])
    trusted = inspect_release(
        release,
        release_id=42,
        tag="python-best-practices-v1.0.0",
        tag_object_sha="b" * 40,
        source_sha="a" * 40,
        signature_kind="ssh",
        signer_fingerprint="SHA256:" + "A" * 43,
        github_tag_verified=True,
        expected_title="Python Best Practices 1.0.0",
        expected_body="release notes\n",
        expected_target_commitish="main",
    )
    rebound = reinspect_bound_release(
        release,
        trusted,
        release_id=42,
        tag="python-best-practices-v1.0.0",
    )
    assert rebound == trusted

    mutations = {
        "title": {**release, "name": "Unexpected title"},
        "body": {**release, "body": "changed notes\n"},
        "target": {**release, "target_commitish": "other"},
        "state": {**release, "draft": False},
        "assets": {
            **release,
            "assets": [
                {
                    "id": 1,
                    "name": "unexpected.exe",
                    "size": 1,
                    "state": "uploaded",
                    "digest": "sha256:" + "c" * 64,
                    "uploader": {"login": "other"},
                }
            ],
        },
    }
    for _label, changed_release in mutations.items():
        with pytest.raises(SkillpackError, match=r"does not match|changed after"):
            reinspect_bound_release(
                changed_release,
                trusted,
                release_id=42,
                tag="python-best-practices-v1.0.0",
            )

    without_verified_tag = {**trusted, "tagObject": None}
    with pytest.raises(SkillpackError, match="verified annotated-tag"):
        reinspect_bound_release(
            release,
            without_verified_tag,
            release_id=42,
            tag="python-best-practices-v1.0.0",
        )


@pytest.mark.parametrize(
    (
        "failure_stage",
        "release_state",
        "asset_count",
        "resume_allowed",
        "removal_allowed",
        "next_action",
    ),
    [
        ("evidence-validation", "absent", 0, False, False, "rerun-normal"),
        ("zip-attestation", "absent", 0, False, False, "rerun-normal"),
        ("draft-creation", "absent", 0, False, False, "inspect-or-rerun-normal"),
        ("asset-free-draft", "draft", 0, True, True, "resume-or-remove"),
        ("partial-upload", "draft", 5, True, True, "resume-or-remove"),
        ("publish-request", "draft", 11, True, True, "resume-or-remove"),
        ("post-publish-immutability", "published", 11, False, False, "patch-incident"),
        ("post-publish-verification", "immutable", 11, False, False, "patch-incident"),
    ],
)
def test_recovery_failure_stage_state_machine(
    failure_stage: str,
    release_state: str,
    asset_count: int,
    resume_allowed: bool,
    removal_allowed: bool,
    next_action: str,
) -> None:
    """Every release failure stage has one fail-closed recovery transition."""

    tag = "python-best-practices-v1.0.0"
    if release_state == "absent":
        assert not resume_allowed and not removal_allowed
        assert next_action in {"rerun-normal", "inspect-or-rerun-normal"}
        return

    digest = "sha256:" + "a" * 64
    expected = _expected_recovery_assets(digest)
    release = _release(
        assets=[
            {
                "id": index,
                "name": item["name"],
                "size": item["size"],
                "state": "uploaded",
                "digest": item["digest"],
                "uploader": {"login": "maintainer"},
            }
            for index, item in enumerate(expected[:asset_count], start=1)
        ],
        draft=release_state == "draft",
    )
    release["immutable"] = release_state == "immutable"
    inspection = inspect_release(
        release,
        release_id=42,
        tag=tag,
        policy_sha="c" * 40,
        tag_object_sha="b" * 40,
        source_sha="a" * 40,
        signature_kind="ssh",
        signer_fingerprint="SHA256:" + "A" * 43,
        github_tag_verified=True,
    )

    if resume_allowed:
        plan = plan_resume(inspection, expected)
        assert plan["complete"] is (asset_count == len(expected))
    else:
        with pytest.raises(SkillpackError, match="mutable draft"):
            plan_resume(inspection, expected)
    if removal_allowed:
        prepare_draft_removal_dossier(inspection)
    else:
        with pytest.raises(SkillpackError, match="mutable draft"):
            prepare_draft_removal_dossier(inspection)
    assert inspection["tag"] == tag, f"{failure_stage} must preserve the tag"
    assert next_action in {"resume-or-remove", "patch-incident"}


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("expected_title", "wrong", "title"),
        ("expected_body", "wrong", "body"),
        ("expected_url", "https://github.com/genaptic/skillsets/releases/tag/wrong", "url"),
        ("expected_target_commitish", "wrong", "target_commitish"),
    ],
)
def test_recovery_inspection_refuses_wrong_release_details(
    field: str, value: str, message: str
) -> None:
    with pytest.raises(SkillpackError, match=message):
        inspect_release(
            _release(assets=[]),
            release_id=42,
            tag="python-best-practices-v1.0.0",
            **{field: value},
        )
    with pytest.raises(SkillpackError, match="has tag"):
        inspect_release(_release(assets=[]), release_id=42, tag="wrong-v1.0.0")
    with pytest.raises(SkillpackError, match="policy SHA"):
        inspect_release(
            _release(assets=[]),
            release_id=42,
            tag="python-best-practices-v1.0.0",
            policy_sha="short",
        )
    with pytest.raises(SkillpackError, match="complete verified annotated-tag identity"):
        inspect_release(
            _release(assets=[]),
            release_id=42,
            tag="python-best-practices-v1.0.0",
            source_sha="a" * 40,
        )
    with pytest.raises(SkillpackError, match="full lowercase Git SHAs"):
        inspect_release(
            _release(assets=[]),
            release_id=42,
            tag="python-best-practices-v1.0.0",
            tag_object_sha="short",
            source_sha="a" * 40,
            signature_kind="ssh",
            signer_fingerprint="SHA256:" + "A" * 43,
            github_tag_verified=True,
        )
    with pytest.raises(SkillpackError, match="signer type/fingerprint"):
        inspect_release(
            _release(assets=[]),
            release_id=42,
            tag="python-best-practices-v1.0.0",
            tag_object_sha="b" * 40,
            source_sha="a" * 40,
            signature_kind="ssh",
            signer_fingerprint="SHA256:short",
            github_tag_verified=True,
        )


def test_recovery_refuses_published_release() -> None:
    inspection = inspect_release(
        _release(assets=[], draft=False),
        release_id=42,
        tag="python-best-practices-v1.0.0",
    )
    with pytest.raises(SkillpackError, match="mutable draft"):
        plan_resume(inspection, [])
    with pytest.raises(SkillpackError, match="mutable draft"):
        prepare_draft_removal_dossier(inspection)
    immutable = _release(assets=[])
    immutable["immutable"] = True
    immutable_inspection = inspect_release(
        immutable,
        release_id=42,
        tag="python-best-practices-v1.0.0",
    )
    with pytest.raises(SkillpackError, match="mutable draft"):
        plan_resume(immutable_inspection, [])
    with pytest.raises(SkillpackError, match="mutable draft"):
        prepare_draft_removal_dossier(immutable_inspection)


def test_recovery_workflow_confines_mutation_and_never_replaces_assets() -> None:
    path = ROOT / ".github/workflows/release-recovery.yml"
    text = path.read_text(encoding="utf-8")
    workflow = yaml.safe_load(text)
    assert set(workflow["jobs"]) == {"inspect", "resume-build", "resume"}
    inspect = workflow["jobs"]["inspect"]
    resume_build = workflow["jobs"]["resume-build"]
    resume = workflow["jobs"]["resume"]

    assert workflow["permissions"] == {"actions": "read", "contents": "read"}
    assert "environment" not in inspect
    assert "permissions" not in inspect
    assert "environment" not in resume_build
    assert resume_build["permissions"] == {
        "actions": "read",
        "attestations": "read",
        "contents": "read",
    }
    assert resume["environment"] == "release"
    assert resume["permissions"] == {
        "actions": "read",
        "attestations": "read",
        "contents": "write",
    }
    assert "prepare-draft-removal" in text
    assert "remove-incomplete-draft" not in text
    assert "confirmation:" not in text
    assert "--method DELETE" not in text
    assert "gh release delete" not in text
    assert "git push" not in text
    assert "--clobber" not in text
    assert "issues: write" not in text

    inspect_names = [step["name"] for step in inspect["steps"]]
    assert "Prepare the read-only manual removal dossier" in inspect_names
    assert "Preserve manual removal guidance without mutation" in inspect_names
    inspect_script = "\n".join(str(step.get("run", "")) for step in inspect["steps"])
    assert "prepare-removal-dossier" in inspect_script
    assert "removal-dossier.json" in inspect_script
    assert "removal-dossier.md" in inspect_script
    assert "releases/$RELEASE_ID" in inspect_script
    assert text.count("python -m skillpack_tools.release_recovery inspect") == 5
    assert text.count('--policy-sha "$GITHUB_SHA"') == 6

    build_script = "\n".join(str(step.get("run", "")) for step in resume_build["steps"])
    assert "path: policy-source" in text
    assert "path: release-source" in text
    assert '--policy-root "$GITHUB_WORKSPACE/policy-source"' in build_script
    assert 'python -m pytest --no-cov -m "not rust_repository_contract"' in build_script
    assert "--deny-self-hosted-runners" in build_script
    assert "recovery-build-manifest.json" in build_script
    assert "release-inspection.json" in build_script
    assert "recovery-plan.json" in build_script

    resume_names = [step["name"] for step in resume["steps"]]
    seal_index = resume_names.index("Seal the exact recovered draft before publication")
    preserve_index = resume_names.index("Preserve the sealed recovery intent before publication")
    publish_index = resume_names.index(
        "Publish and verify the exact recovered release by numeric ID"
    )
    assert seal_index < preserve_index < publish_index
    resume_script = "\n".join(str(step.get("run", "")) for step in resume["steps"])
    assert "EXPECTED_ARTIFACT_ID" in resume_script
    assert "EXPECTED_ARTIFACT_NAME" in resume_script
    assert "EXPECTED_ARTIFACT_DIGEST" in resume_script
    assert "seal-intent" in resume_script
    assert "verify-published" in resume_script
    assert '--method PATCH "/repos/$GITHUB_REPOSITORY/releases/$RELEASE_ID"' in resume_script
    assert 'gh release verify "$RELEASE_TAG"' in resume_script
    assert "gh release verify-asset" in resume_script
    assert "gh attestation verify" in resume_script


def test_normal_release_failure_stages_leave_only_documented_recovery_states() -> None:
    workflow = (ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")
    stages = {
        "evidence": "Download and verify the three protected evidence artifacts",
        "attestation": "Verify the returned provenance bundle immediately",
        "draft": "Create an asset-free draft for the verified tag",
        "partial-upload": "Upload the immutable release asset set without replacement",
        "publish": "Publish the verified draft",
        "post-publish-immutability": "Verify the immutable release attestation",
    }
    positions = {stage: workflow.index(label) for stage, label in stages.items()}
    assert positions == dict(sorted(positions.items(), key=lambda item: item[1]))
    assert positions["evidence"] < positions["attestation"] < positions["draft"]
    assert positions["draft"] < positions["partial-upload"] < positions["publish"]
    assert positions["publish"] < positions["post-publish-immutability"]
    publication_segment = workflow[positions["draft"] :]
    assert "--clobber" not in publication_segment
    assert "gh release delete" not in publication_segment
    assert "git tag -d" not in workflow
    assert "git push --delete" not in workflow


def test_first_release_canary_has_an_explicit_pre_tag_stop_boundary() -> None:
    process = (ROOT / "docs/release-process.md").read_text(encoding="utf-8")
    canary = process.split("## First-release canary and approval checkpoint", 1)[1].split(
        "## Draft rehearsal", 1
    )[0]
    assert "`python-best-practices` is the sole first-release canary" in canary
    assert "go/no-go dossier" in canary
    assert "Stop immediately after the dossier, before creating or signing the tag" in canary
    assert "separate explicit approval" in canary
    assert "at least seven calendar days" in canary
    assert "one complete reconciliation cycle" in canary
    assert "Stop before preparing pack two" in canary
    assert "git tag" in canary


def test_reconciliation_workflow_is_read_only_and_preserves_drift_report() -> None:
    workflow = (ROOT / ".github/workflows/publication-reconcile.yml").read_text(encoding="utf-8")
    assert "  schedule:\n" in workflow
    assert "  workflow_dispatch:\n" in workflow
    assert "  release:\n" not in workflow
    handoff = (ROOT / ".github/workflows/publication-handoff.yml").read_text(encoding="utf-8")
    assert "  workflow_run:\n" in handoff
    assert "      - Release one skillpack\n" in handoff
    assert "      - Recover an interrupted skillpack release\n" in handoff
    assert "permissions:\n  contents: read\n" in workflow
    assert "contents: write" not in workflow
    assert "git push" not in workflow
    assert "gh issue" not in workflow
    assert "skillpack_tools.publication reconcile" in workflow
    assert '"refs/tags"' in workflow
    assert '"-v" in tag' in workflow
    assert "normalized-tags.json" in workflow
    assert '--tags "$RUNNER_TEMP/normalized-tags.json"' in workflow
    assert "tools/generate-all --check" not in workflow
    assert "generated public membership" not in workflow
    assert "actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a" in workflow


def test_release_fetches_candidates_from_typed_signers_and_hands_off_reconciliation() -> None:
    workflow = (ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")
    handoff = (ROOT / ".github/workflows/publication-handoff.yml").read_text(encoding="utf-8")
    candidate_step = workflow.split(
        "      - name: Fetch maintainer key candidates and enforce the repository fingerprint allowlist\n",
        1,
    )[1].split("      - name: Run immutable-source release gates\n", 1)[0]
    assert "trusted_signers if s.kind" in candidate_step
    assert "/users/$signer_login/ssh_signing_keys" in candidate_step
    assert "maintainer_github" not in candidate_step
    assert "publication-record.json" not in workflow
    assert "publication-plan.json" not in workflow
    assert "issues: write" not in workflow
    assert "publication-record.json" in handoff
    assert "publication-plan.json" in handoff
    assert "publication-update.patch" in handoff
    assert '"baseCommit": os.environ["BASE_COMMIT"]' not in workflow
    assert ".workflow.triggeringActor.githubId" in workflow
    assert "git push" not in workflow
    assert "git push" not in handoff
