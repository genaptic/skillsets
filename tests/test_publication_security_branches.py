from __future__ import annotations

import datetime as dt
import json
import shutil
import subprocess
import tempfile
from copy import deepcopy
from pathlib import Path

import pytest

import skillpack_tools.evidence as evidence
import skillpack_tools.publication as publication
import skillpack_tools.signing as signing
from skillpack_tools.evidence import EvidenceAsset
from skillpack_tools.models import Pack, TrustedSigner, get_pack, load_repository
from skillpack_tools.signing import SigningKeyCandidate
from skillpack_tools.util import SkillpackError, sha256_bytes

ROOT = Path(__file__).resolve().parents[1]


def _publication_record(**changes: object) -> dict[str, object]:
    pack = get_pack(ROOT, "python-best-practices")
    repository = load_repository(ROOT)
    record: dict[str, object] = {
        "schemaVersion": 1,
        "repository": repository.slug,
        "packId": pack.id,
        "version": pack.version,
        "releaseId": 123,
        "tag": pack.tag,
        "url": f"{repository.web_url}/releases/tag/{pack.tag}",
        "sourceSha": "a" * 40,
        "baseCommit": "b" * 40,
        "publishedAt": "2026-07-19T12:34:56Z",
        "immutable": True,
        "draft": False,
        "prerelease": False,
    }
    record.update(changes)
    return record


@pytest.mark.parametrize(
    ("content", "message"),
    [
        (b'{"value":1,"value":2}', "duplicate object key"),
        (b'{"value":NaN}', "non-finite number"),
        (b'{"value":1e999}', "non-finite number"),
        (b"\xff", "invalid strict JSON"),
    ],
)
def test_publication_json_parser_rejects_ambiguous_values(content: bytes, message: str) -> None:
    with pytest.raises(SkillpackError, match=message):
        publication.strict_json_bytes(content, label="release-record")
    assert publication.strict_json_bytes(b'{"value":1.25}', label="valid") == {"value": 1.25}


def test_publication_record_loader_requires_an_object_and_valid_schema(tmp_path: Path) -> None:
    record = tmp_path / "record.json"
    record.write_text("[]\n", encoding="utf-8")
    with pytest.raises(SkillpackError, match="must be a JSON object"):
        publication.load_publication_record(ROOT, record)

    record.write_text('{"schemaVersion":1}\n', encoding="utf-8")
    with pytest.raises(SkillpackError, match="validation failed"):
        publication.load_publication_record(ROOT, record)


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"packId": "unknown-pack"}, "Unknown pack"),
        ({"repository": "somebody/else"}, "does not match"),
        ({"tag": "wrong-v1.0.0"}, "tag must be"),
        ({"url": "https://github.com/genaptic/skillsets/releases/tag/wrong"}, "URL must be"),
        (
            {
                "version": "2.0.0",
                "tag": "python-best-practices-v2.0.0",
                "url": (
                    "https://github.com/genaptic/skillsets/releases/tag/"
                    "python-best-practices-v2.0.0"
                ),
            },
            "newer than canonical",
        ),
    ],
)
def test_publication_record_identity_checks_fail_closed(
    changes: dict[str, object], message: str
) -> None:
    with pytest.raises(SkillpackError, match=message):
        publication.validate_publication_record(ROOT, _publication_record(**changes))


def test_publication_record_rejects_withdrawn_and_conflicting_release(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    canonical = get_pack(ROOT, "python-best-practices")
    raw = deepcopy(canonical.raw)
    raw["publication"] = {
        "state": "withdrawn",
        "latest-release": {
            "version": "1.0.0",
            "source-sha": "a" * 40,
            "release-id": 123,
            "released-at": "2026-07-19T12:34:56Z",
        },
    }
    withdrawn = Pack(root=canonical.root, path=canonical.path, raw=raw)
    monkeypatch.setattr(publication, "get_pack", lambda *_args: withdrawn)
    with pytest.raises(SkillpackError, match="withdrawn"):
        publication.validate_publication_record(ROOT, _publication_record())

    raw["publication"]["state"] = "published"
    published = Pack(root=canonical.root, path=canonical.path, raw=raw)
    monkeypatch.setattr(publication, "get_pack", lambda *_args: published)
    conflict = _publication_record(releaseId=999)
    with pytest.raises(SkillpackError, match="conflicts with the existing release"):
        publication.validate_publication_record(ROOT, conflict)


def test_publication_git_preconditions_reject_nongit_and_dirty_worktrees(tmp_path: Path) -> None:
    assert publication._git_command("status") == [
        "git",
        "-c",
        "core.longpaths=true",
        "status",
    ]
    with pytest.raises(SkillpackError, match="Git worktree"):
        publication._git_head(tmp_path)

    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "Fixture"], check=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "config", "user.email", "fixture@example.com"],
        check=True,
    )
    tracked = tmp_path / "tracked.txt"
    tracked.write_text("tracked\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "tracked.txt"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-q", "-m", "fixture"], check=True)
    assert len(publication._git_head(tmp_path)) == 40
    (tmp_path / "untracked.txt").write_text("dirty\n", encoding="utf-8")
    with pytest.raises(SkillpackError, match="clean worktree"):
        publication._require_clean(tmp_path)


def test_publication_snapshot_and_rollback_restore_content_modes_and_absence(
    tmp_path: Path,
) -> None:
    existing = tmp_path / "existing.txt"
    existing.write_bytes(b"before\n")
    existing.chmod(0o600)
    expected_mode = existing.stat().st_mode & 0o777
    changed_files = [
        {
            "path": "existing.txt",
            "beforeSha256": sha256_bytes(b"before\n"),
            "beforeMode": f"{expected_mode:04o}",
        },
        {
            "path": "generated/nested/new.txt",
            "beforeSha256": None,
            "beforeMode": None,
        },
    ]
    snapshot = publication._snapshot_changed_files(tmp_path, changed_files)
    existing.write_bytes(b"after\n")
    new = tmp_path / "generated/nested/new.txt"
    new.parent.mkdir(parents=True)
    new.write_bytes(b"generated\n")

    publication._rollback_changed_files(tmp_path, snapshot)

    assert existing.read_bytes() == b"before\n"
    assert existing.stat().st_mode & 0o777 == expected_mode
    assert not new.exists()
    assert not (tmp_path / "generated").exists()

    changed_files[0]["beforeSha256"] = "0" * 64
    with pytest.raises(SkillpackError, match=r"existing\.txt changed"):
        publication._snapshot_changed_files(tmp_path, changed_files)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("outputs", "Generated outputs"),
        ("digest", "output-set digest"),
        ("patch", "full-index patch"),
        ("paths", "changed-file set"),
        ("file", "Applied file"),
    ],
)
def test_applied_publication_plan_detects_every_review_boundary(
    monkeypatch: pytest.MonkeyPatch, mutation: str, message: str
) -> None:
    outputs = [{"path": "catalog.json", "sha256": "a" * 64, "mode": "0644"}]
    digest = sha256_bytes(
        json.dumps(outputs, sort_keys=True, separators=(",", ":")).encode("utf-8")
    )
    plan = {
        "generatedOutputs": outputs,
        "generatedOutputSetSha256": digest,
        "unifiedPatch": "patch",
        "changedFiles": [
            {
                "path": "catalog.json",
                "afterSha256": "a" * 64,
                "afterMode": "0644",
            }
        ],
    }
    actual_outputs = [] if mutation == "outputs" else outputs
    monkeypatch.setattr(publication, "_generated_output_records", lambda _root: actual_outputs)
    if mutation == "digest":
        plan["generatedOutputSetSha256"] = "b" * 64
    patch = "different" if mutation == "patch" else "patch"
    paths = [] if mutation == "paths" else ["catalog.json"]
    monkeypatch.setattr(publication, "_git_patch_and_paths", lambda *_args: (patch, paths))
    after = ("b" * 64, "0644") if mutation == "file" else ("a" * 64, "0644")
    monkeypatch.setattr(publication, "_path_record", lambda *_args: after)

    with pytest.raises(SkillpackError, match=message):
        publication._verify_applied_plan(ROOT, plan)


def _published_pack(*, state: str = "published", latest_version: str = "1.0.0") -> Pack:
    canonical = get_pack(ROOT, "python-best-practices")
    raw = deepcopy(canonical.raw)
    raw["publication"] = {
        "state": state,
        "latest-release": {
            "version": latest_version,
            "source-sha": "a" * 40,
            "release-id": 123,
            "released-at": "2026-07-19T12:34:56Z",
        },
    }
    return Pack(root=canonical.root, path=canonical.path, raw=raw)


def _release(tag: str = "python-best-practices-v1.0.0", **changes: object) -> dict[str, object]:
    release: dict[str, object] = {
        "tag": tag,
        "sourceSha": "a" * 40,
        "releaseId": 123,
        "publishedAt": "2026-07-19T12:34:56Z",
        "draft": False,
        "prerelease": False,
        "immutable": True,
        "annotated": True,
        "tagVerified": True,
    }
    release.update(changes)
    return release


def test_reconciliation_reports_release_and_repository_tag_truth_table(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pack = _published_pack(latest_version="1.0.0+canonical")
    monkeypatch.setattr(publication, "discover_packs", lambda _root: [pack])
    monkeypatch.setattr(publication, "_generated_output_drift", lambda _root: [])
    releases = [
        _release("python-best-practices-vbad"),
        _release("unknown-pack-v1.0.0"),
        _release("python-best-practices-v0.9.0"),
        _release("python-best-practices-v1.0.0+other"),
        _release("python-best-practices-v1.0.0+other"),
        _release("python-best-practices-v2.0.0", immutable=False),
    ]
    tags = [
        {"tag": "python-best-practices-vbad"},
        {"tag": "unknown-pack-v1.0.0"},
        {"tag": "python-best-practices-v9.0.0"},
        {"tag": "python-best-practices-v9.0.0"},
        {
            "tag": "python-best-practices-v2.0.0",
            "sourceSha": "b" * 40,
            "annotated": False,
            "tagVerified": False,
        },
    ]
    result = publication.reconcile_publications(ROOT, releases, tags)
    kinds = {item["kind"] for item in result["drift"]}
    assert {
        "invalid-pack-release-tag",
        "unknown-pack-release",
        "release-version-conflict",
        "duplicate-release-tag",
        "release-not-publishable",
        "invalid-pack-tag",
        "unknown-pack-tag",
        "tag-release-missing",
        "duplicate-repository-tag",
        "release-tag-mismatch",
        "release-tag-missing",
        "manifest-release-missing",
    } <= kinds


def test_reconciliation_treats_withdrawal_as_historical_not_publication_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pack = _published_pack(state="withdrawn")
    monkeypatch.setattr(publication, "discover_packs", lambda _root: [pack])
    monkeypatch.setattr(publication, "_generated_output_drift", lambda _root: [])
    result = publication.reconcile_publications(ROOT, [_release()])
    assert result == {"schemaVersion": 1, "ok": True, "drift": []}


def test_publication_cli_prepare_and_reconcile_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "nested/plan.json"
    monkeypatch.setattr(publication, "load_publication_record", lambda *_args: {"record": True})
    monkeypatch.setattr(
        publication,
        "prepare_publication_update",
        lambda *_args, **kwargs: {"schemaVersion": 2, "applied": kwargs["apply"]},
    )
    assert (
        publication.main(
            [
                "prepare",
                "--root",
                str(ROOT),
                "--record",
                str(tmp_path / "record.json"),
                "--output",
                str(output),
                "--apply",
                "--plan-digest",
                "a" * 64,
            ]
        )
        == 0
    )
    assert json.loads(output.read_text(encoding="utf-8"))["applied"] is True

    releases = tmp_path / "releases.json"
    tags = tmp_path / "tags.json"
    releases.write_text("[]\n", encoding="utf-8")
    tags.write_text("[]\n", encoding="utf-8")
    monkeypatch.setattr(
        publication,
        "reconcile_publications",
        lambda _root, loaded_releases, loaded_tags: {
            "schemaVersion": 1,
            "ok": loaded_releases == [] and loaded_tags == [],
            "drift": [],
        },
    )
    assert (
        publication.main(
            [
                "reconcile",
                "--root",
                str(ROOT),
                "--releases",
                str(releases),
                "--tags",
                str(tags),
                "--output",
                str(output),
            ]
        )
        == 0
    )


@pytest.mark.parametrize(
    ("releases_text", "tags_text", "message"),
    [
        ("{}\n", None, "release input must be an array"),
        ("[]\n", "{}\n", "tag input must be an array"),
        ("not-json\n", None, "invalid strict JSON"),
    ],
)
def test_publication_cli_writes_fail_closed_reconciliation_report(
    tmp_path: Path, releases_text: str, tags_text: str | None, message: str
) -> None:
    releases = tmp_path / "releases.json"
    releases.write_text(releases_text, encoding="utf-8")
    output = tmp_path / "report.json"
    arguments = [
        "reconcile",
        "--root",
        str(ROOT),
        "--releases",
        str(releases),
        "--output",
        str(output),
    ]
    if tags_text is not None:
        tags = tmp_path / "tags.json"
        tags.write_text(tags_text, encoding="utf-8")
        arguments.extend(["--tags", str(tags)])
    with pytest.raises(SystemExit) as raised:
        publication.main(arguments)
    assert raised.value.code == 1
    report = json.loads(output.read_text(encoding="utf-8"))
    assert not report["ok"]
    assert message in report["drift"][0]["detail"]


def _completed(
    command: object, returncode: int = 0, stdout: str = "", stderr: str = ""
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(command, returncode, stdout, stderr)


def test_signing_command_and_git_failures_are_actionable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def unavailable(*_args: object, **_kwargs: object) -> None:
        raise OSError("missing")

    monkeypatch.setattr(subprocess, "run", unavailable)
    with pytest.raises(SkillpackError, match="command is unavailable"):
        signing._run(["missing-tool"])

    monkeypatch.setattr(signing, "_git", lambda *_args: _completed([], 1, "", "bad tag"))
    with pytest.raises(SkillpackError, match="bad tag"):
        signing._required_git(tmp_path, "verify-tag", "v1")


def test_ssh_key_parsing_and_fingerprint_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(SkillpackError, match="supported public key"):
        signing._ssh_public_key("not a public key")
    assert signing._ssh_public_key("user ssh-ed25519 AAAA comment") == "ssh-ed25519 AAAA"

    monkeypatch.setattr(signing, "_run", lambda *_args, **_kwargs: _completed([], 1, "", "bad"))
    with pytest.raises(SkillpackError, match="Could not fingerprint"):
        signing.ssh_key_fingerprint("ssh-ed25519 AAAA")
    monkeypatch.setattr(signing, "_run", lambda *_args, **_kwargs: _completed([], 0, "no hash"))
    with pytest.raises(SkillpackError, match="did not return"):
        signing.ssh_key_fingerprint("ssh-ed25519 AAAA")


def test_local_signing_candidate_discovery_reads_only_configured_material(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    key = tmp_path / "signing-key.pub"
    key.write_text("ssh-ed25519 AAAA configured\n", encoding="utf-8")
    allowed = tmp_path / "allowed_signers"
    allowed.write_text(
        "# comment\nmaintainer ssh-ed25519 BBBB first\ninvalid\n",
        encoding="utf-8",
    )

    def git_result(_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
        if "user.signingkey" in args:
            return _completed(args, stdout=f"key::{key}\n")
        return _completed(args, stdout=f"{allowed}\n")

    monkeypatch.setattr(signing, "_git", git_result)
    assert signing._read_ssh_candidates(tmp_path) == [
        SigningKeyCandidate(kind="ssh", material="ssh-ed25519 AAAA configured\n"),
        SigningKeyCandidate(kind="ssh", material="ssh-ed25519 BBBB"),
    ]

    openpgp = TrustedSigner(kind="openpgp", github="fixture", fingerprint="A" * 40)
    ssh = TrustedSigner(kind="ssh", github="fixture", fingerprint="SHA256:" + "B" * 43)
    monkeypatch.setattr(
        signing,
        "_run",
        lambda command, **_kwargs: _completed(
            command,
            0 if command[-1] == "A" * 40 else 1,
            "PUBLIC KEY" if command[-1] == "A" * 40 else "",
        ),
    )
    assert signing._read_openpgp_candidates([ssh, openpgp]) == [
        SigningKeyCandidate(kind="openpgp", material="PUBLIC KEY")
    ]

    monkeypatch.setattr(signing, "_read_ssh_candidates", lambda _root: ["ssh-candidate"])
    monkeypatch.setattr(signing, "_read_openpgp_candidates", lambda _signers: ["pgp-candidate"])
    assert signing.discover_signing_key_candidates(tmp_path, [ssh, openpgp]) == (
        "ssh-candidate",
        "pgp-candidate",
    )


@pytest.mark.parametrize(
    ("tag_type", "payload", "expected", "message"),
    [
        ("commit", "", None, "annotated tag"),
        ("tag", "-----BEGIN SSH SIGNATURE-----", "ssh", None),
        ("tag", "-----BEGIN PGP SIGNATURE-----", "openpgp", None),
        ("tag", "unsigned", None, "no supported"),
    ],
)
def test_tag_signature_kind_requires_annotated_supported_signature(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    tag_type: str,
    payload: str,
    expected: str | None,
    message: str | None,
) -> None:
    monkeypatch.setattr(
        signing,
        "_required_git",
        lambda _root, *args: tag_type if args[:2] == ("cat-file", "-t") else payload,
    )
    if message is not None:
        with pytest.raises(SkillpackError, match=message):
            signing._tag_signature_kind(tmp_path, "fixture-v1.0.0")
    else:
        assert signing._tag_signature_kind(tmp_path, "fixture-v1.0.0") == expected


def test_openpgp_fingerprint_inventory_filters_invalid_and_failed_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(signing, "_run", lambda *_args, **_kwargs: _completed([], 1))
    assert signing._openpgp_candidate_fingerprints(tmp_path) == set()
    fingerprint = "A" * 40
    listing = f"fpr:::::::::{fingerprint}:\nfpr:::::::::SHORT:\npub:::::::::{fingerprint}:\n"
    monkeypatch.setattr(signing, "_run", lambda *_args, **_kwargs: _completed([], 0, listing))
    assert signing._openpgp_candidate_fingerprints(tmp_path) == {fingerprint}


def test_openpgp_verification_binds_git_and_shuts_down_the_ephemeral_home(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fingerprint = "A" * 40
    executables = {
        "gpg": str((tmp_path / "tools" / "gpg").resolve()),
        "gpgconf": str((tmp_path / "tools" / "gpgconf").resolve()),
    }
    monkeypatch.setattr(signing.shutil, "which", lambda name: executables[name])
    monkeypatch.setattr(signing, "_openpgp_candidate_fingerprints", lambda _home: {fingerprint})
    commands: list[list[str]] = []

    def run(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        commands.append(command)
        if command[0] == "git":
            return _completed(
                command,
                stdout="",
                stderr=f"[GNUPG:] VALIDSIG {fingerprint} 0 0 0 0 0 0 0 0\n",
            )
        return _completed(command)

    monkeypatch.setattr(signing, "_run", run)
    assert (
        signing._verify_openpgp_tag(
            tmp_path,
            "fixture-v1.0.0",
            {fingerprint},
            [SigningKeyCandidate(kind="openpgp", material="public key")],
        )
        == fingerprint
    )

    assert commands[0][0] == executables["gpg"]
    assert f"gpg.openpgp.program={executables['gpg']}" in commands[1]
    assert commands[-1][0] == executables["gpgconf"]
    assert commands[-1][1:3] == ["--homedir", commands[0][3]]
    assert commands[-1][-2:] == ["--kill", "all"]


def test_openpgp_shutdown_failure_does_not_mask_verification_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    executables = {
        "gpg": str((tmp_path / "tools" / "gpg").resolve()),
        "gpgconf": str((tmp_path / "tools" / "gpgconf").resolve()),
    }
    monkeypatch.setattr(signing.shutil, "which", lambda name: executables[name])
    commands: list[list[str]] = []

    def run(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        commands.append(command)
        if command[0] == executables["gpgconf"]:
            raise SkillpackError("shutdown failed")
        raise SkillpackError("verification failed")

    monkeypatch.setattr(signing, "_run", run)
    with pytest.raises(SkillpackError, match="verification failed"):
        signing._verify_openpgp_tag(
            tmp_path,
            "fixture-v1.0.0",
            {"A" * 40},
            [SigningKeyCandidate(kind="openpgp", material="public key")],
        )
    assert commands[-1][0] == executables["gpgconf"]


def test_openpgp_home_cleanup_does_not_mask_the_original_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    temporary_root = tmp_path / "temporary"
    temporary_root.mkdir()

    class FailingTemporaryDirectory:
        name = str(temporary_root)

        def cleanup(self) -> None:
            raise OSError("cleanup failed")

    monkeypatch.setattr(
        signing.tempfile,
        "TemporaryDirectory",
        lambda **_kwargs: FailingTemporaryDirectory(),
    )
    monkeypatch.setattr(signing, "_shutdown_gnupg_home", lambda _home: None)

    with (
        pytest.raises(SkillpackError, match="verification failed"),
        signing._ephemeral_gnupg_home(),
    ):
        raise SkillpackError("verification failed")


def test_verify_tag_enforces_signer_kind_discovery_and_commit_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ssh = TrustedSigner(kind="ssh", github="fixture", fingerprint="SHA256:" + "A" * 43)
    with pytest.raises(SkillpackError, match="at least one trusted signer"):
        signing.verify_tag(tmp_path, "fixture-v1.0.0", [])

    monkeypatch.setattr(signing, "_tag_signature_kind", lambda *_args: "openpgp")
    with pytest.raises(SkillpackError, match="No trusted openpgp"):
        signing.verify_tag(tmp_path, "fixture-v1.0.0", [ssh])

    monkeypatch.setattr(signing, "_tag_signature_kind", lambda *_args: "ssh")
    monkeypatch.setattr(
        signing,
        "discover_signing_key_candidates",
        lambda *_args: (SigningKeyCandidate(kind="ssh", material="candidate"),),
    )
    monkeypatch.setattr(signing, "_verify_ssh_tag", lambda *_args: ssh.fingerprint)
    monkeypatch.setattr(signing, "_required_git", lambda *_args: "not-a-sha")
    with pytest.raises(SkillpackError, match="full commit SHA"):
        signing.verify_tag(tmp_path, "fixture-v1.0.0", [ssh])

    monkeypatch.setattr(signing, "_required_git", lambda *_args: "c" * 40)
    verified = signing.verify_tag(tmp_path, "fixture-v1.0.0", [ssh])
    assert verified.source_sha == "c" * 40
    assert verified.fingerprint == ssh.fingerprint


@pytest.mark.skipif(
    shutil.which("gpg") is None or shutil.which("gpgconf") is None or shutil.which("git") is None,
    reason="GnuPG, gpgconf, and Git are required for the isolated OpenPGP integration test",
)
def test_real_openpgp_tag_verification_uses_an_isolated_full_fingerprint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    gpg_program = shutil.which("gpg")
    gpgconf_program = shutil.which("gpgconf")
    assert gpg_program is not None
    assert gpgconf_program is not None
    short_temp_root = Path("/tmp")
    if not short_temp_root.is_dir():
        short_temp_root = Path(tempfile.gettempdir())
    temporary_home = tempfile.TemporaryDirectory(prefix="skillpacks-gpg-", dir=short_temp_root)
    home = Path(temporary_home.name)
    monkeypatch.setenv("GNUPGHOME", str(home))
    original_failure: BaseException | None = None
    try:
        identity = "Release Fixture <release-fixture@example.com>"
        subprocess.run(
            [
                gpg_program,
                "--batch",
                "--homedir",
                str(home),
                "--pinentry-mode",
                "loopback",
                "--passphrase",
                "",
                "--quick-generate-key",
                identity,
                "ed25519",
                "sign",
                "1d",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        inventory = subprocess.run(
            [
                gpg_program,
                "--batch",
                "--homedir",
                str(home),
                "--with-colons",
                "--fingerprint",
                "--list-secret-keys",
                identity,
            ],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        fingerprint = next(
            fields[9]
            for line in inventory.splitlines()
            if (fields := line.split(":"))[0] == "fpr" and len(fields) > 9
        )
        public_key = subprocess.run(
            [
                gpg_program,
                "--batch",
                "--homedir",
                str(home),
                "--armor",
                "--export",
                fingerprint,
            ],
            check=True,
            capture_output=True,
            text=True,
        ).stdout

        repository = tmp_path / "repository"
        repository.mkdir()

        def git(*arguments: str) -> str:
            return subprocess.run(
                ["git", "-C", str(repository), *arguments],
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()

        git("init", "-q")
        git("config", "user.name", "Release Fixture")
        git("config", "user.email", "release-fixture@example.com")
        git("config", "commit.gpgsign", "false")
        git("config", "gpg.format", "openpgp")
        git("config", "gpg.openpgp.program", gpg_program)
        git("config", "user.signingkey", fingerprint)
        (repository / "release.txt").write_text("release\n", encoding="utf-8")
        git("add", "release.txt")
        git("commit", "-q", "--no-gpg-sign", "-m", "release")
        git("tag", "-s", "fixture-v1.0.0", "-m", "fixture v1.0.0")

        verified = signing.verify_tag(
            repository,
            "fixture-v1.0.0",
            [TrustedSigner(kind="openpgp", github="fixture", fingerprint=fingerprint)],
            candidate_keys=[SigningKeyCandidate(kind="openpgp", material=public_key)],
        )
        assert verified.kind == "openpgp"
        assert verified.fingerprint == fingerprint
        assert verified.source_sha == git("rev-parse", "HEAD")
    except BaseException as exc:
        original_failure = exc
        raise
    finally:
        try:
            subprocess.run(
                [gpgconf_program, "--homedir", str(home), "--kill", "all"],
                check=False,
                capture_output=True,
                text=True,
            )
        except BaseException:
            if original_failure is None:
                raise
        try:
            temporary_home.cleanup()
        except BaseException:
            if original_failure is None:
                raise


@pytest.mark.parametrize("name", ["codex.envelope.json", "codex.txt", ".json"])
def test_evidence_asset_names_fail_closed(name: str, tmp_path: Path) -> None:
    with pytest.raises(SkillpackError):
        EvidenceAsset.from_report(tmp_path / name)


def test_evidence_json_bounds_encoding_shape_and_recursion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    report = tmp_path / "report.json"
    report.write_bytes(b"\xff")
    with pytest.raises(SkillpackError, match="not valid UTF-8"):
        evidence.strict_load_json(report)

    report.write_text("[]\n", encoding="utf-8")
    with pytest.raises(SkillpackError, match="one JSON object"):
        evidence.strict_load_json(report)

    report.write_text('{"a":{"b":{"c":1}}}\n', encoding="utf-8")
    monkeypatch.setattr(evidence, "MAX_EVIDENCE_JSON_NESTING", 2)
    with pytest.raises(SkillpackError, match="container levels"):
        evidence.strict_load_json(report)

    monkeypatch.setattr(evidence, "MAX_EVIDENCE_JSON_BYTES", 4)
    with pytest.raises(SkillpackError, match="byte limit"):
        evidence.strict_load_json(report)

    monkeypatch.setattr(evidence, "MAX_EVIDENCE_JSON_BYTES", 1024 * 1024)
    monkeypatch.setattr(
        evidence.json, "loads", lambda *_args, **_kwargs: (_ for _ in ()).throw(RecursionError())
    )
    with pytest.raises(SkillpackError, match="container levels"):
        evidence.strict_load_json(report)


def test_evidence_time_and_reviewer_input_validation() -> None:
    policy = load_repository(ROOT).compatibility_evidence
    with pytest.raises(ValueError, match="canonical UTC"):
        evidence.parse_tested_at("2026-07-19T12:00:00+00:00")
    with pytest.raises(ValueError, match="not a real RFC 3339"):
        evidence.parse_tested_at("2026-02-30T12:00:00Z")
    errors = evidence.evidence_freshness_errors("not-a-time", policy, label="fixture")
    assert errors and errors[0].startswith("fixture:")
    with pytest.raises(ValueError, match="timezone-aware"):
        evidence.evidence_freshness_errors(
            "2026-07-19T12:00:00Z",
            policy,
            now=dt.datetime(2026, 7, 19, 12, 0),
        )
    errors = evidence.reviewer_authorization_errors(
        {"github": "intruder", "githubId": object()}, policy
    )
    assert "GitHub ID 0 is not authorized" in errors[0]


def _evidence_envelope(report: Path) -> dict[str, object]:
    return evidence.build_evidence_envelope(
        repository_id=123,
        repository_slug="genaptic/skillsets",
        run_id=456,
        run_attempt=1,
        workflow_ref="genaptic/skillsets/.github/workflows/native.yml@refs/heads/main",
        workflow_sha="c" * 40,
        event="workflow_dispatch",
        actor="jecsand838",
        actor_id=170039284,
        triggering_actor="jecsand838",
        source_sha="a" * 40,
        evidence_sha="b" * 40,
        report_repository_path="compatibility/reports/codex.json",
        report_sha256=evidence.sha256_file(report),
        client="codex",
        pack_id="python-best-practices",
        tested_at="2026-07-19T12:00:00Z",
    )


def test_evidence_envelope_reports_all_binding_and_report_identity_mismatches(
    tmp_path: Path,
) -> None:
    report = tmp_path / "codex.json"
    report.write_text(
        json.dumps(
            {
                "testedAt": "2026-07-18T12:00:00Z",
                "client": {"name": "opencode"},
                "pack": {"id": "other-pack", "sourceSha": "d" * 40},
                "reviewer": {"github": "other", "githubId": 1},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    data = _evidence_envelope(report)
    data["workflow"]["triggeringActor"] = {"github": "other", "githubId": 1}  # type: ignore[index]
    envelope_path = tmp_path / "codex.envelope.json"
    envelope_path.write_text(json.dumps(data) + "\n", encoding="utf-8")
    errors, loaded = evidence.validate_evidence_envelope(
        ROOT,
        envelope_path,
        report_path=report,
        source_sha="e" * 40,
        evidence_sha="f" * 40,
        report_repository_path="compatibility/reports/other.json",
        client="claude-code",
        pack_id="expected-pack",
        repository_slug="owner/repository",
        workflow_run_id=999,
    )
    assert loaded == data
    joined = "\n".join(errors)
    for field in (
        "source.sha",
        "evidence.commitSha",
        "evidence.reportPath",
        "client",
        "packId",
        "repository.slug",
        "workflow.runId",
        "testedAt",
        "reviewer.github",
        "triggeringActor",
    ):
        assert field in joined

    report.write_text("not-json\n", encoding="utf-8")
    errors, _ = evidence.validate_evidence_envelope(ROOT, envelope_path, report_path=report)
    assert "Invalid evidence JSON" in "\n".join(errors)


def test_evidence_envelope_and_asset_surface_read_and_schema_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    missing = tmp_path / "missing.envelope.json"
    errors, loaded = evidence.validate_evidence_envelope(ROOT, missing)
    assert loaded is None and "Could not read" in errors[0]

    envelope_path = tmp_path / "codex.envelope.json"
    envelope_path.write_text("{}\n", encoding="utf-8")
    monkeypatch.setattr(
        evidence,
        "load_json_schema",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("bad schema")),
    )
    errors, loaded = evidence.validate_evidence_envelope(ROOT, envelope_path)
    assert loaded == {} and errors == ["bad schema"]

    report = tmp_path / "codex.json"
    report.write_text("{}\n", encoding="utf-8")
    bundle = tmp_path / "codex.attestation.jsonl"
    bundle.write_text("{}\n", encoding="utf-8")
    errors, validated = evidence.validate_evidence_asset(ROOT, report)
    assert validated is None and errors == ["bad schema"]
