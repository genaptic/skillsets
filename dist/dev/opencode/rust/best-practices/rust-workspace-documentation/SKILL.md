---
name: rust-workspace-documentation
description: >
  Reconcile a Rust repository's Markdown and agent-facing documentation with its current code,
  manifests, commands, ownership, and validation workflow. Use when behavior or structure changes
  require coordinated updates to README, architecture, contributor, operational, or agent guidance.
  Do not use for a public-API rustdoc-only refresh, a narrow copyedit, or undocumented code changes.
license: Apache-2.0
metadata:
  skillpack: "rust-best-practices"
  version: "1.0.0"
  maturity: "release-candidate"
---

## Outcome

Produce a reviewed, evidence-backed documentation change that describes the repository as it
currently behaves, preserves clear ownership between documents, and leaves validation claims
traceable to commands that actually ran.

## Compatibility

Portable across Claude Code, Codex, and OpenCode. Work against the target repository's Rust
toolchain, MSRV, edition, workspace layout, lockfile policy, and documented commands; Edition 2024
examples require Rust 1.85 or newer. Network access is optional: use current primary sources when
allowed, otherwise identify which external guidance could not be refreshed. Native-client behavior
is unverified until a dated report records the client version and exact source commit.

## Use this skill when

- A Rust change alters commands, modules, crate ownership, workflows, configuration, examples,
  compatibility, or validation and several repository-owned Markdown surfaces may drift.
- The task is to audit or refresh README files, architecture documents, contributor guides,
  operational runbooks, agent instructions, or an explicit documentation inventory as one pass.
- A branch or worktree needs a no-op documentation audit whose result must be supported by source
  and diff evidence.

## Do not use this skill when

- The requested output is exclusively public API documentation, `//!`/`///` comments, or doctests;
  use `rustdoc-maintenance`.
- The user asks for a localized copyedit and does not need repository-wide reconciliation.
- The primary job is implementing Rust behavior. Update the owning code first, then use this skill
  for the resulting documentation contract.
- The task concerns generic documentation outside a Rust repository.

## Inputs

Inspect the user request, repository instructions, current worktree, relevant diff or change set,
Rust and Cargo manifests, command/help output, tests, workflows, and the complete in-scope Markdown
inventory. Determine the comparison base from repository evidence; never assume a branch name.
Record unavailable history, commands, or network access as limitations rather than inventing them.

## Safety

Begin read-only. Documentation edits are project writes and may describe security-sensitive
operations, so preserve unrelated changes and redact secrets, credentials, private URLs, and local
machine details. Do not install tools, mutate dependencies, switch branches, stage, commit, push,
publish, or change remote state implicitly. Preview the document-role and change matrix before a
large rewrite; obtain approval when the user's workflow requires it.

## Procedure

1. Read repository instructions and inventory manifests, source, workflows, tests, and Markdown.
2. Establish the requested scope and comparison source from local evidence. If history is absent,
   audit current behavior without fabricating a base.
3. Assign each fact to one canonical document role using
   [Document roles](references/document-roles.md); identify duplicates and stale consumers.
4. Trace every behavioral claim to implementation, manifest, test, generated help, or an explicitly
   cited primary source. Browse only when allowed and mark freshness gaps.
5. Present a compact matrix of affected documents, evidence, proposed edits, and excluded surfaces.
6. Update owning documents first, then summaries and links. Preserve local conventions, generated
   boundaries, and repository-specific terminology.
7. Validate relative links, commands, examples, document ownership, and repository-defined checks.
8. Inspect the final diff for accidental scope expansion, stale names, contradictions, and unrelated
   formatting churn.

Read [Guide](references/guide.md) for the complete reconciliation workflow and
[Examples](references/examples.md) for common evidence and boundary cases.

## Verification

- Prove that every changed claim matches current code, configuration, help, tests, or a cited source.
- Run the repository's own documentation, formatting, lint, and test commands that are relevant and
  safe; discover flags from manifests, configuration, and CI instead of prescribing a universal
  Cargo command.
- Check every changed local link and referenced path, including anchors when tooling supports them.
- Report commands exactly as run with their outcomes. Distinguish passed checks, unavailable checks,
  skipped checks, and manual review; never convert structural inspection into native/model evidence.

## Output contract

Return the scope and comparison source, document-role matrix, changes by owning document, source and
repository evidence, validation results, unresolved drift, and any freshness or access limitations.
For a no-op audit, report what was inspected and why no edit is necessary.

## Resources

- [Guide](references/guide.md) — evidence-led inventory and reconciliation sequence
- [Checklist](references/checklist.md) — completion and review gates
- [Sources](references/sources.md) — primary Rust, Cargo, and agent-documentation sources
- [Document roles](references/document-roles.md) — ownership and deduplication rules
- [Examples](references/examples.md) — representative refresh, no-op, and boundary cases
