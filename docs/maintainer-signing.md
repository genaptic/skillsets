# Maintainer signing

Cryptographic SSH signatures and Developer Certificate of Origin signoffs are separate controls.
A signature proves control of a registered key; a terminal `Signed-off-by` trailer records the
contributor's DCO certification. Maintainer commits require both, while GitHub squash merges use
GitHub's verified server signature and a controlled DCO-compliant pull-request body.

## Repository-specific key

Use the dedicated passphrase-protected Ed25519 key
`~/.ssh/id_ed25519_genaptic_skillsets_signing`. Keep its private half and passphrase outside the
repository. Add only the `.pub` file to GitHub as a signing key; this operation may require the
narrow `admin:ssh_signing_key` GitHub CLI scope. Load the private key through the macOS SSH agent
and Keychain without recording its passphrase in a shell command, file, secret, or workflow.

```bash
gh auth refresh -h github.com -s admin:ssh_signing_key
gh ssh-key add ~/.ssh/id_ed25519_genaptic_skillsets_signing.pub \
  --type signing \
  --title "Genaptic Skillsets signing"
ssh-add --apple-use-keychain ~/.ssh/id_ed25519_genaptic_skillsets_signing
```

The final command prompts securely when the key is not already available to the agent. Do not
paste the passphrase into a command or automation log.

Configure only this repository:

```bash
git config --local gpg.format ssh
git config --local user.signingkey ~/.ssh/id_ed25519_genaptic_skillsets_signing.pub
git config --local commit.gpgsign true
git config --local tag.gpgSign true
git config --local gpg.ssh.allowedSignersFile ~/.ssh/allowed_signers_genaptic_skillsets
```

The allowed-signers file remains outside the repository and maps the verified GitHub noreply
identity to the public signing key. Before using the key here, create an isolated temporary Git
repository, make a signed and signed-off commit, create a signed annotated tag, and require
`git verify-commit` and `git verify-tag` to pass. Remove the temporary repository afterward.

`repository.yaml` is the release trust root. A cryptographically valid pack tag is accepted only
when the actual full signing-key fingerprint also appears in `release.trusted-signers`. The
current dedicated SSH signing key is pinned as:

```text
SHA256:RXn4sQSc9mwJb13oQVvUUkQvPw+B5N+WrRWH4elMJHg
```

GitHub profile signing keys from each trusted signer's configured `github` login and local
allowed-signers files are candidate-discovery surfaces, not trust stores. Release tooling
fingerprints every SSH candidate, discards candidates outside
the repository allowlist, and verifies the tag against each remaining key independently.
OpenPGP verification likewise uses full v4/v6 fingerprints and the `VALIDSIG` signing-key
fingerprint; short key IDs are never accepted. A machine-readable revoked, expired, bad, or error
signature status rejects the candidate even if the same command output also contains `VALIDSIG`.

Protected release and recovery workflows resolve this policy from their exact default-branch
dispatch SHA, not from the tag being authenticated. The tagged source must also pass the local
release build, but it cannot broaden the current protected signer allowlist.

Create repository commits with:

```bash
git commit --signoff -S
```

Create pack release tags only after exact-SHA compatibility evidence passes:

```bash
git tag -s PACK_ID-vX.Y.Z -m "PACK_ID vX.Y.Z"
```

Never store a private key, passphrase, copied client credential, PAT, deploy key, or signing
material in repository or environment secrets. If the signing key is lost or compromised,
remove it from GitHub, stop publication, preserve existing immutable evidence, and rotate to a
new dedicated key before preparing another release.

Rotate without a trust gap: add the new full fingerprint through a protected pull request,
verify that the matching public signing key is registered on GitHub, sign a later release tag
with the new key, and remove the old fingerprint in a second protected pull request. Removing a
compromised fingerprint intentionally prevents resuming any mutable draft signed by that key;
generate the read-only removal dossier and use a separately authorized, immediately re-inspected
manual break-glass process before restarting with a trusted tag. No recovery workflow deletes the
draft. Git tag signing and GitHub Actions Sigstore attestations are independent controls: the
former uses the pinned long-lived maintainer fingerprint, while the latter trusts the repository
workflow's OIDC identity.
