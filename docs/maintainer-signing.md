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
