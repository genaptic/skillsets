# Threat model

## Assets

The repository protects:

- User source code and local files.
- Credentials and environment configuration.
- Command and database execution authority.
- Marketplace and release integrity.
- Skill routing correctness.
- Contributor and maintainer identities.
- Trust in generated artifacts.

## Trust boundaries

### Installation

A user grants a client permission to fetch a marketplace and copy plugin content. Installers
therefore must not execute bundled helpers or lifecycle behavior. Release refs and SHAs
control which reviewed content is fetched.

### Skill activation

A description can route a model into instructions the user did not intend. Names and
descriptions are security-relevant metadata, not cosmetic text. Negative evals and reviewed
four-outcome routing-boundary matrices reduce broad activation.

### Tool execution

A skill can lead an agent to read, write, execute, or use the network. Every skill must state
its default posture and approval boundary. Deterministic helpers receive untrusted paths and
input; they must validate them.

### Contribution and CI

Pull-request content is untrusted. PR workflows use read-only permissions, no repository
secrets, GitHub-hosted runners, and no `pull_request_target` checkout of contributed code.
Sensitive workflows and installers require CODEOWNERS review. Third-party Actions are pinned
to full SHAs.

### Release

A maintainer account, workflow token, mutable tag, or generated-file mismatch can compromise
all downstream installs. Unpublished catalogs therefore use repository-local sources only.
Publishable releases require protected, signed tags whose actual full key fingerprint is in the
repository trust allowlist, minimal workflow permissions, reproducible allowlisted archives,
checksums, exact-SHA compatibility evidence, and full-SHA
marketplace pins.

## Threats and controls

| Threat | Primary controls |
|---|---|
| Hidden command or network execution | Human review, explicit safety sections, script scanner, no install hooks |
| Credential exposure | Unicode-normalized, case-insensitive secret filtering; no CLI-secret patterns; redaction rules; private reports |
| Path traversal or overwrite | Lexical containment, no-follow component inspection and reads, whole-operation preflight, special-node rejection, and identity rechecks before mutation |
| Unsafe recursive deletion | Exact-target authorization, root/home/worktree refusal, containment and ownership checks, explicit symlink policy, preview, confirmation, and adversarial tests |
| Unsafe copy-paste examples | Clear snippet/project classification, repository-derived commands, bounded inputs, and execution prerequisites |
| Bearer-token disclosure in Rust HTTP examples | Authenticated templates require HTTPS and refuse redirect forwarding of bearer credentials |
| Optional `gh skill` adapter side effects | Capability preflight plus invocation-scoped telemetry, prompt, and update-notifier disabling |
| Destructive DB advice | Environment classification, approval boundary, rollback and recovery requirements |
| Prompt over-triggering | Globally unique names, routing contracts, negative evals, and reviewed routing-boundary matrices |
| Generated artifact tampering | Deterministic generation, no-follow source and destination walks, target-aware stale cleanup, and CI diff check |
| Mutable dependency or action | Hashed Python locks, full-SHA GitHub Actions, pack tags and required published source SHA |
| Malicious pull request | Read-only tokens, no secrets, ephemeral hosted runners, sensitive CODEOWNERS |
| False verification claim | Separate structural, native-client, and model-backed evidence with schema-valid exact-SHA reports, authenticated reviewer identity, provenance envelopes, and Sigstore attestations |
| Stale or replayed compatibility evidence | Canonical tested timestamps, bounded age/skew policy, source/evidence/main ancestry proofs, raw-byte hashes, and release-time revalidation |
| Profile key substitution | Treat hosted and local public keys only as candidates; accept tags only when the actual SSH/OpenPGP signing fingerprint is pinned in `repository.yaml` |
| Outdated vendor, PostgreSQL, Rust, or dependency behavior | Versioned sources, target-repository inspection, compatibility reports, freshness limits, and release-time review |

## Residual risk

Natural-language behavior is probabilistic. Static validation cannot guarantee routing,
correct reasoning, or safe tool use. Portable no-follow checks detect repository links and
many namespace races, but cannot make an entire multi-path operation atomic against a
concurrently hostile filesystem on every supported platform. Client vendors may change format
or execution semantics. Operators must review high-impact commands, maintain independent
backups, use least privilege, and test in disposable environments.

## Adding a new capability

A proposal that introduces network access, authentication, external writes, lifecycle hooks,
MCP servers, or elevated database privileges must update this threat model and identify:

- Assets accessed.
- Required permissions.
- Data sent or stored.
- Failure and abuse modes.
- Consent and confirmation flow.
- Logging and redaction.
- Rollback and incident response.
