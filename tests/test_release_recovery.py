from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest
import yaml

from skillpack_tools.models import get_pack
from skillpack_tools.release import render_release_notes
from skillpack_tools.release_recovery import (
    expected_asset_names,
    expected_assets,
    main,
    plan_resume,
    seal_release_intent,
    verify_published_release,
)
from skillpack_tools.signing import VerifiedTag
from skillpack_tools.util import SkillpackError

ROOT = Path(__file__).resolve().parents[1]
TAG = "python-best-practices-v1.0.0"
SOURCE_SHA = "a" * 40
TAG_OBJECT_SHA = "b" * 40
FINGERPRINT = "SHA256:" + "A" * 43


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def _release(*, assets: list[dict[str, object]] | None = None) -> dict[str, object]:
    return {
        "id": 42,
        "tag_name": TAG,
        "html_url": f"https://github.com/genaptic/skillsets/releases/tag/{TAG}",
        "name": "Python Best Practices 1.0.0",
        "body": "release notes\n",
        "target_commitish": "main",
        "draft": True,
        "prerelease": False,
        "immutable": False,
        "assets": assets or [],
    }


def _inspection(names: list[str]) -> dict[str, object]:
    return {
        "schemaVersion": 2,
        "releaseId": 42,
        "tag": TAG,
        "draft": True,
        "prerelease": False,
        "immutable": False,
        "expectedAssetNames": sorted(names),
        "assets": [],
    }


def _make_assets(root: Path) -> list[Path]:
    root.mkdir(parents=True)
    paths = [root / "alpha.bin", root / "beta.json"]
    paths[0].write_bytes(b"alpha\x00bytes")
    paths[1].write_text('{"beta":true}\n', encoding="utf-8")
    return paths


def test_expected_assets_and_resume_plans_are_runner_independent(tmp_path: Path) -> None:
    first_paths = _make_assets(tmp_path / "runner-a" / "work")
    second_paths = _make_assets(tmp_path / "runner-b" / "different" / "work")
    first = expected_assets(first_paths)
    second = expected_assets(second_paths)

    assert first == second
    assert all(set(item) == {"name", "size", "digest"} for item in first)
    assert str(tmp_path) not in json.dumps(first)

    # Even programmatic callers cannot smuggle machine-local fields into a sealed plan.
    supplied = [{**item, "path": f"/runner-specific/{item['name']}"} for item in first]
    plan = plan_resume(_inspection([str(item["name"]) for item in first]), supplied)
    assert plan["missing"] == first
    assert str(tmp_path) not in json.dumps(plan)
    assert "/runner-specific/" not in json.dumps(plan)

    inspection_path = tmp_path / "inspection.json"
    first_output = tmp_path / "first-plan.json"
    second_output = tmp_path / "second-plan.json"
    _write_json(inspection_path, _inspection([path.name for path in first_paths]))
    assert (
        main(
            [
                "plan-resume",
                "--inspection",
                str(inspection_path),
                "--expected",
                *(str(path) for path in first_paths),
                "--output",
                str(first_output),
            ]
        )
        == 0
    )
    assert (
        main(
            [
                "plan-resume",
                "--inspection",
                str(inspection_path),
                "--expected",
                *(str(path) for path in second_paths),
                "--output",
                str(second_output),
            ]
        )
        == 0
    )
    assert first_output.read_bytes() == second_output.read_bytes()
    assert str(tmp_path).encode() not in first_output.read_bytes()


def test_expected_assets_reject_ambiguous_or_unsafe_inputs(tmp_path: Path) -> None:
    first = tmp_path / "one" / "same.bin"
    second = tmp_path / "two" / "same.bin"
    first.parent.mkdir()
    second.parent.mkdir()
    first.write_bytes(b"one")
    second.write_bytes(b"two")
    with pytest.raises(SkillpackError, match="unique basenames"):
        expected_assets([first, second])

    link = tmp_path / "linked.bin"
    link.symlink_to(first)
    with pytest.raises(SkillpackError, match="regular file"):
        expected_assets([link])


@pytest.mark.parametrize(
    ("record", "message"),
    [
        ("not-an-object", "must be objects"),
        ({"name": "../escape", "size": 1, "digest": "sha256:" + "a" * 64}, "basename"),
        ({"name": "bad\\name", "size": 1, "digest": "sha256:" + "a" * 64}, "basename"),
        ({"name": "asset", "size": True, "digest": "sha256:" + "a" * 64}, "size"),
        ({"name": "asset", "size": -1, "digest": "sha256:" + "a" * 64}, "size"),
        ({"name": "asset", "size": 1, "digest": "sha256:wrong"}, "digest"),
    ],
)
def test_resume_plan_rejects_nonportable_expected_records(record: object, message: str) -> None:
    with pytest.raises(SkillpackError, match=message):
        plan_resume(_inspection(["asset"]), [record])  # type: ignore[list-item]


@pytest.mark.parametrize(
    "assets",
    ["not-an-array", ["not-an-object"], [{"name": "bad/name"}], [{"name": "bad\nname"}]],
)
def test_resume_plan_rejects_malformed_inspected_assets(assets: object) -> None:
    inspection = {**_inspection([]), "assets": assets}
    with pytest.raises(SkillpackError, match=r"assets must be objects|safe basenames"):
        plan_resume(inspection, [])


def test_recovery_cli_round_trips_inspection_reinspection_and_authorization(
    tmp_path: Path,
) -> None:
    release_path = tmp_path / "release.json"
    inspection_path = tmp_path / "inspection.json"
    rebound_path = tmp_path / "rebound.json"
    dossier_path = tmp_path / "removal-dossier.json"
    dossier_markdown = tmp_path / "removal-dossier.md"
    _write_json(release_path, _release())

    inspect_args = [
        "inspect",
        "--release",
        str(release_path),
        "--release-id",
        "42",
        "--tag",
        TAG,
        "--policy-sha",
        "c" * 40,
        "--tag-object-sha",
        TAG_OBJECT_SHA,
        "--source-sha",
        SOURCE_SHA,
        "--signature-kind",
        "ssh",
        "--signer-fingerprint",
        FINGERPRINT,
        "--github-tag-verified",
        "--expected-title",
        "Python Best Practices 1.0.0",
        "--expected-target-commitish",
        "main",
        "--output",
        str(inspection_path),
    ]
    assert main(inspect_args) == 0
    assert (
        main(
            [
                "reinspect-bound",
                "--release",
                str(release_path),
                "--trusted-inspection",
                str(inspection_path),
                "--release-id",
                "42",
                "--tag",
                TAG,
                "--output",
                str(rebound_path),
            ]
        )
        == 0
    )
    assert rebound_path.read_bytes() == inspection_path.read_bytes()
    assert (
        main(
            [
                "prepare-removal-dossier",
                "--inspection",
                str(inspection_path),
                "--output",
                str(dossier_path),
                "--markdown-output",
                str(dossier_markdown),
            ]
        )
        == 0
    )
    assert json.loads(dossier_path.read_text(encoding="utf-8"))["operation"] == (
        "manual-break-glass-only"
    )
    dossier = json.loads(dossier_path.read_text(encoding="utf-8"))
    assert dossier["mutable"] is True
    assert dossier["policySha"] == "c" * 40
    assert dossier["url"].endswith(TAG)
    assert "## Exact release assets" in dossier_markdown.read_text(encoding="utf-8")
    assert "does not provide a compare-and-delete" in dossier_markdown.read_text(encoding="utf-8")


def test_release_intent_detects_post_publish_asset_and_metadata_drift() -> None:
    assets = [
        {
            "id": index,
            "name": name,
            "size": index,
            "state": "uploaded",
            "digest": "sha256:" + f"{index:064x}",
            "uploader": {"login": "github-actions[bot]"},
        }
        for index, name in enumerate(expected_asset_names(TAG), start=1)
    ]
    draft = _release(assets=assets)
    intent = seal_release_intent(
        ROOT,
        draft,
        mode="sealed-draft",
        repository_slug="genaptic/skillsets",
        policy_sha="c" * 40,
        workflow_name="Release one skillpack",
        workflow_run_id=100,
        workflow_run_attempt=1,
        pack_id="python-best-practices",
        release_id=42,
        tag=TAG,
        tag_object_sha=TAG_OBJECT_SHA,
        source_sha=SOURCE_SHA,
        signature_kind="ssh",
        signer_fingerprint=FINGERPRINT,
        github_tag_verified=True,
        expected_title="Python Best Practices 1.0.0",
        expected_body="release notes\n",
        expected_target_commitish="main",
    )
    published = {
        **draft,
        "draft": False,
        "immutable": True,
        "published_at": "2026-07-20T12:00:00Z",
    }
    verified = verify_published_release(ROOT, published, intent)
    assert verified["releaseId"] == 42
    assert verified["policySha"] == "c" * 40
    assert verified["url"] == draft["html_url"]

    changed = json.loads(json.dumps(published))
    changed["assets"].append(
        {
            "id": 999,
            "name": "unexpected.bin",
            "size": 1,
            "state": "uploaded",
            "digest": "sha256:" + "f" * 64,
            "uploader": {"login": "intruder"},
        }
    )
    with pytest.raises(SkillpackError, match="asset inventory differs"):
        verify_published_release(ROOT, changed, intent)

    changed = {**published, "body": "changed after sealing"}
    with pytest.raises(SkillpackError, match="body does not match"):
        verify_published_release(ROOT, changed, intent)

    release_mutations = [
        ({**published, "id": 43}, "returned ID"),
        ({**published, "tag_name": "other-v1.0.0"}, "has tag"),
        (
            {
                **published,
                "html_url": "https://github.com/genaptic/skillsets/releases/tag/other",
            },
            "url does not match",
        ),
        ({**published, "name": "Changed title"}, "title does not match"),
        ({**published, "target_commitish": "other"}, "target_commitish does not match"),
        ({**published, "draft": True}, "non-prerelease publication"),
        ({**published, "prerelease": True}, "non-prerelease publication"),
        ({**published, "immutable": False}, "must be immutable"),
        ({**published, "published_at": None}, "publication time"),
    ]
    for mutation, message in release_mutations:
        with pytest.raises(SkillpackError, match=message):
            verify_published_release(ROOT, mutation, intent)

    for field, replacement in (
        ("id", 999),
        ("size", 999),
        ("state", "failed"),
        ("digest", "sha256:" + "f" * 64),
        ("uploader", {"login": "replacement"}),
    ):
        mutation = json.loads(json.dumps(published))
        mutation["assets"][0][field] = replacement
        with pytest.raises(SkillpackError, match="asset inventory differs"):
            verify_published_release(ROOT, mutation, intent)


def test_expected_body_cli_uses_the_canonical_release_renderer(tmp_path: Path) -> None:
    pack = get_pack(ROOT, "python-best-practices")
    digest = "c" * 64
    evidence = [
        {
            "client": client,
            "reportAsset": f"{client}.json",
            "reportSha256": digest,
            "provenanceAsset": f"{client}.envelope.json",
            "provenanceSha256": digest,
            "attestationBundleAsset": f"{client}.attestation.jsonl",
            "attestationBundleSha256": digest,
        }
        for client in ("claude-code", "codex", "opencode")
    ]
    body = render_release_notes(
        pack,
        draft=False,
        source_sha=SOURCE_SHA,
        signer=VerifiedTag(source_sha=SOURCE_SHA, kind="ssh", fingerprint=FINGERPRINT),
        archive_digest=digest,
        evidence_records=evidence,
        changelog=(pack.path / "CHANGELOG.md").read_text(encoding="utf-8"),
    ).decode("utf-8")
    release = _release()
    release["body"] = body
    release_path = tmp_path / "release.json"
    output = tmp_path / "notes.md"
    _write_json(release_path, release)

    assert (
        main(
            [
                "expected-body",
                "--root",
                str(ROOT),
                "--pack",
                pack.id,
                "--release",
                str(release_path),
                "--source-sha",
                SOURCE_SHA,
                "--signature-kind",
                "ssh",
                "--signer-fingerprint",
                FINGERPRINT,
                "--output",
                str(output),
            ]
        )
        == 0
    )
    assert output.read_text(encoding="utf-8") == body


def _artifact_extraction_program() -> str:
    workflow = yaml.safe_load(
        (ROOT / ".github/workflows/release-recovery.yml").read_text(encoding="utf-8")
    )
    step = next(
        item
        for item in workflow["jobs"]["resume"]["steps"]
        if item["name"] == "Download and digest-verify the exact recovery-build artifact"
    )
    marker = "python - <<'PY'\n"
    script = str(step["run"])
    return script.split(marker, 1)[1].rsplit("\nPY", 1)[0]


def _handoff_names() -> set[str]:
    return {
        f"{TAG}.zip",
        f"{TAG}.zip.sha256",
        f"{TAG}-release-notes.md",
        "release-inspection.json",
        "recovery-plan.json",
        "recovery-build-manifest.json",
        *(
            f"{client}.{suffix}"
            for client in ("claude-code", "codex", "opencode")
            for suffix in ("json", "envelope.json", "attestation.jsonl")
        ),
    }


def _run_artifact_extractor(runner_temp: Path) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment.update({"RELEASE_TAG": TAG, "RUNNER_TEMP": str(runner_temp)})
    return subprocess.run(
        [sys.executable, "-c", _artifact_extraction_program()],
        cwd=ROOT,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )


def _regular_zip_info(name: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name)
    info.create_system = 3
    info.external_attr = (stat.S_IFREG | 0o644) << 16
    return info


def test_recovery_artifact_handoff_safely_extracts_exact_flat_inventory(tmp_path: Path) -> None:
    archive = tmp_path / "recovery-build.zip"
    destination = tmp_path / "recovery-build-bundle"
    destination.mkdir()
    payloads = {name: f"sealed:{name}\n".encode() for name in _handoff_names()}
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_STORED) as bundle:
        for name, payload in sorted(payloads.items()):
            bundle.writestr(_regular_zip_info(name), payload)

    completed = _run_artifact_extractor(tmp_path)
    assert completed.returncode == 0, completed.stderr
    assert {path.name for path in destination.iterdir()} == set(payloads)
    for name, payload in payloads.items():
        extracted = destination / name
        assert extracted.read_bytes() == payload
        assert stat.S_IMODE(extracted.stat().st_mode) == 0o644


def test_recovery_artifact_handoff_rejects_symlink_members(tmp_path: Path) -> None:
    archive = tmp_path / "recovery-build.zip"
    destination = tmp_path / "recovery-build-bundle"
    destination.mkdir()
    unsafe_name = "recovery-plan.json"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_STORED) as bundle:
        for name in sorted(_handoff_names()):
            if name == unsafe_name:
                info = zipfile.ZipInfo(name)
                info.create_system = 3
                info.external_attr = (stat.S_IFLNK | 0o777) << 16
                bundle.writestr(info, b"outside")
            else:
                bundle.writestr(_regular_zip_info(name), b"sealed\n")

    completed = _run_artifact_extractor(tmp_path)
    assert completed.returncode != 0
    assert f"unsafe recovery-build artifact member: {unsafe_name}" in completed.stderr
    assert not (destination / unsafe_name).exists()


def test_recovery_module_is_directly_executable() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "skillpack_tools.release_recovery", "--help"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0
    assert "Inspect and safely plan draft release recovery" in completed.stdout
