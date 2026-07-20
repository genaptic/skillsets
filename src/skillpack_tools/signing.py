from __future__ import annotations

import os
import re
import subprocess
import tempfile
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from .models import TrustedSigner
from .util import SkillpackError

_SSH_KEY_RE = re.compile(
    r"(?:^|\s)((?:sk-)?(?:ssh|ecdsa)-[A-Za-z0-9@._+-]+)\s+([A-Za-z0-9+/=]+)(?:\s|$)"
)
_SSH_FINGERPRINT_RE = re.compile(r"SHA256:[A-Za-z0-9+/]{43}")
_OPENPGP_FINGERPRINT_RE = re.compile(r"(?:[0-9A-F]{40}|[0-9A-F]{64})")
_REJECTED_OPENPGP_STATUSES = frozenset(
    {"BADSIG", "ERRSIG", "EXPKEYSIG", "EXPSIG", "KEYREVOKED", "REVKEYSIG"}
)


@dataclass(frozen=True)
class SigningKeyCandidate:
    kind: Literal["ssh", "openpgp"]
    material: str


@dataclass(frozen=True)
class VerifiedTag:
    source_sha: str
    kind: Literal["ssh", "openpgp"]
    fingerprint: str


def _run(
    command: list[str],
    *,
    env: dict[str, str] | None = None,
    input_text: str | None = None,
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            input=input_text,
            env=env,
        )
    except OSError as exc:
        raise SkillpackError(f"Required signing command is unavailable: {command[0]}") from exc


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return _run(["git", "-C", str(root), *args])


def _required_git(root: Path, *args: str) -> str:
    result = _git(root, *args)
    if result.returncode:
        detail = result.stderr.strip() or result.stdout.strip() or "git command failed"
        raise SkillpackError(f"Signed-tag verification failed: {detail}")
    return result.stdout.strip()


def _ssh_public_key(material: str) -> str:
    match = _SSH_KEY_RE.search(material.strip())
    if not match:
        raise SkillpackError("SSH signing candidate does not contain a supported public key.")
    return f"{match.group(1)} {match.group(2)}"


def ssh_key_fingerprint(material: str) -> str:
    """Return the full OpenSSH SHA-256 fingerprint for one public key candidate."""

    public_key = _ssh_public_key(material)
    with tempfile.TemporaryDirectory(prefix="skillpack-ssh-fingerprint-") as temporary:
        path = Path(temporary) / "candidate.pub"
        path.write_text(public_key + "\n", encoding="utf-8")
        result = _run(["ssh-keygen", "-lf", str(path), "-E", "sha256"])
    if result.returncode:
        detail = result.stderr.strip() or "ssh-keygen rejected the public key"
        raise SkillpackError(f"Could not fingerprint SSH signing candidate: {detail}")
    match = _SSH_FINGERPRINT_RE.search(result.stdout)
    if not match:
        raise SkillpackError("ssh-keygen did not return a full SHA-256 fingerprint.")
    return match.group(0)


def _read_ssh_candidates(root: Path) -> list[SigningKeyCandidate]:
    candidates: list[SigningKeyCandidate] = []
    signing_key = _git(root, "config", "--get", "user.signingkey")
    if signing_key.returncode == 0 and signing_key.stdout.strip():
        value = signing_key.stdout.strip()
        if value.startswith("key::"):
            value = value.removeprefix("key::")
        path = Path(os.path.expanduser(value))
        if path.is_file():
            try:
                value = path.read_text(encoding="utf-8")
            except OSError as exc:
                raise SkillpackError(
                    f"Could not read configured SSH signing key {path}: {exc}"
                ) from exc
        candidates.append(SigningKeyCandidate(kind="ssh", material=value))

    allowed = _git(root, "config", "--path", "--get", "gpg.ssh.allowedSignersFile")
    if allowed.returncode == 0 and allowed.stdout.strip():
        path = Path(os.path.expanduser(allowed.stdout.strip()))
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            raise SkillpackError(
                f"Could not read configured allowed-signers file {path}: {exc}"
            ) from exc
        for line in lines:
            if line.lstrip().startswith("#"):
                continue
            match = _SSH_KEY_RE.search(line)
            if match:
                candidates.append(
                    SigningKeyCandidate(
                        kind="ssh",
                        material=f"{match.group(1)} {match.group(2)}",
                    )
                )
    return candidates


def _read_openpgp_candidates(signers: Iterable[TrustedSigner]) -> list[SigningKeyCandidate]:
    candidates: list[SigningKeyCandidate] = []
    for signer in signers:
        if signer.kind != "openpgp":
            continue
        result = _run(["gpg", "--batch", "--armor", "--export", signer.fingerprint])
        if result.returncode == 0 and result.stdout.strip():
            candidates.append(SigningKeyCandidate(kind="openpgp", material=result.stdout))
    return candidates


def discover_signing_key_candidates(
    root: Path,
    trusted_signers: Iterable[TrustedSigner],
) -> tuple[SigningKeyCandidate, ...]:
    """Discover local public-key material only; this function never accesses the network."""

    signers = tuple(trusted_signers)
    candidates: list[SigningKeyCandidate] = []
    if any(signer.kind == "ssh" for signer in signers):
        candidates.extend(_read_ssh_candidates(root))
    candidates.extend(_read_openpgp_candidates(signers))
    return tuple(candidates)


def _tag_signature_kind(root: Path, tag: str) -> Literal["ssh", "openpgp"]:
    tag_type = _required_git(root, "cat-file", "-t", f"refs/tags/{tag}")
    if tag_type != "tag":
        raise SkillpackError(f"Release tag {tag!r} must be an annotated tag.")
    payload = _required_git(root, "cat-file", "tag", tag)
    if "-----BEGIN SSH SIGNATURE-----" in payload:
        return "ssh"
    if "-----BEGIN PGP SIGNATURE-----" in payload:
        return "openpgp"
    raise SkillpackError(f"Release tag {tag!r} has no supported SSH or OpenPGP signature.")


def _verify_ssh_tag(
    root: Path,
    tag: str,
    trusted: set[str],
    candidates: Iterable[SigningKeyCandidate],
) -> str:
    filtered: dict[str, str] = {}
    for candidate in candidates:
        if candidate.kind != "ssh":
            continue
        try:
            public_key = _ssh_public_key(candidate.material)
            fingerprint = ssh_key_fingerprint(public_key)
        except SkillpackError:
            continue
        if fingerprint in trusted:
            filtered[fingerprint] = public_key

    successful: set[str] = set()
    for fingerprint, public_key in filtered.items():
        with tempfile.TemporaryDirectory(prefix="skillpack-allowed-signer-") as temporary:
            allowed = Path(temporary) / "allowed_signers"
            allowed.write_text(f"maintainer {public_key}\n", encoding="utf-8")
            result = _git(
                root,
                "-c",
                "gpg.format=ssh",
                "-c",
                f"gpg.ssh.allowedSignersFile={allowed}",
                "verify-tag",
                "--raw",
                tag,
            )
        if result.returncode == 0:
            successful.add(fingerprint)
    if len(successful) != 1:
        raise SkillpackError(
            f"SSH tag signature matched {len(successful)} trusted fingerprints; "
            "expected exactly one."
        )
    return successful.pop()


def _openpgp_candidate_fingerprints(home: Path) -> set[str]:
    result = _run(
        [
            "gpg",
            "--batch",
            "--homedir",
            str(home),
            "--with-colons",
            "--with-subkey-fingerprint",
            "--fingerprint",
            "--list-keys",
        ]
    )
    if result.returncode:
        return set()
    return {
        fields[9]
        for line in result.stdout.splitlines()
        if (fields := line.split(":"))[0] == "fpr"
        and len(fields) > 9
        and _OPENPGP_FINGERPRINT_RE.fullmatch(fields[9])
    }


def _verify_openpgp_tag(
    root: Path,
    tag: str,
    trusted: set[str],
    candidates: Iterable[SigningKeyCandidate],
) -> str:
    successful: set[str] = set()
    for candidate in candidates:
        if candidate.kind != "openpgp":
            continue
        with tempfile.TemporaryDirectory(prefix="skillpack-openpgp-") as temporary:
            home = Path(temporary) / "gnupg"
            home.mkdir(mode=0o700)
            import_result = _run(
                ["gpg", "--batch", "--homedir", str(home), "--import"],
                input_text=candidate.material,
            )
            if import_result.returncode or not (_openpgp_candidate_fingerprints(home) & trusted):
                continue
            environment = dict(os.environ)
            environment["GNUPGHOME"] = str(home)
            result = _run(
                [
                    "git",
                    "-C",
                    str(root),
                    "-c",
                    "gpg.format=openpgp",
                    "verify-tag",
                    "--raw",
                    tag,
                ],
                env=environment,
            )
        if result.returncode:
            continue
        status = f"{result.stdout}\n{result.stderr}"
        status_lines = [
            match.groups()
            for line in status.splitlines()
            if (match := re.match(r"^\[GNUPG:\]\s+([A-Z_]+)(?:\s+(.*))?$", line))
        ]
        if any(name in _REJECTED_OPENPGP_STATUSES for name, _detail in status_lines):
            continue
        for name, detail in status_lines:
            if name != "VALIDSIG" or not detail:
                continue
            fingerprint = detail.split(maxsplit=1)[0]
            if _OPENPGP_FINGERPRINT_RE.fullmatch(fingerprint) and fingerprint in trusted:
                successful.add(fingerprint)
    if len(successful) != 1:
        raise SkillpackError(
            "OpenPGP tag signature matched "
            f"{len(successful)} trusted signing fingerprints; expected exactly one."
        )
    return successful.pop()


def verify_tag(
    root: Path,
    tag: str,
    trusted_signers: Iterable[TrustedSigner],
    *,
    candidate_keys: Iterable[SigningKeyCandidate] | None = None,
) -> VerifiedTag:
    """Verify an annotated tag against the repository's exact full-fingerprint allowlist."""

    root = Path(os.path.abspath(os.fspath(root)))
    signers = tuple(trusted_signers)
    if not signers:
        raise SkillpackError("Signed-tag verification requires at least one trusted signer.")
    kind = _tag_signature_kind(root, tag)
    trusted = {signer.fingerprint for signer in signers if signer.kind == kind}
    if not trusted:
        raise SkillpackError(f"No trusted {kind} fingerprint is configured for tag {tag!r}.")
    candidates = (
        tuple(candidate_keys)
        if candidate_keys is not None
        else discover_signing_key_candidates(root, signers)
    )
    fingerprint = (
        _verify_ssh_tag(root, tag, trusted, candidates)
        if kind == "ssh"
        else _verify_openpgp_tag(root, tag, trusted, candidates)
    )
    source_sha = _required_git(root, "rev-list", "-n", "1", tag)
    if not re.fullmatch(r"[0-9a-f]{40}", source_sha):
        raise SkillpackError(f"Release tag {tag!r} did not resolve to a full commit SHA.")
    return VerifiedTag(source_sha=source_sha, kind=kind, fingerprint=fingerprint)
