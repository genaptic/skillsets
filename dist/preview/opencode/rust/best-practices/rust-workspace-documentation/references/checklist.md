# Rust workspace documentation checklist

## Scope and evidence

- [ ] Read applicable repository instructions and the user-requested scope.
- [ ] Determine the comparison source from local evidence or record a current-tree-only audit.
- [ ] Inventory all in-scope Markdown, Cargo manifests, workflows, tests, help, and configuration.
- [ ] Assign each repeated fact to one canonical document owner.
- [ ] Trace every proposed factual change to implementation, configuration, tests, help, or a cited
      primary source.
- [ ] Record unavailable tools, history, network access, and freshness checks.

## Safety and editing

- [ ] Begin read-only and preview a multi-document change matrix before broad edits.
- [ ] Preserve unrelated work and repository-specific terminology.
- [ ] Avoid generated files, historical records, and vendored documentation unless explicitly in scope.
- [ ] Redact secrets, private URLs, local usernames, and machine-specific paths.
- [ ] Avoid staging, committing, pushing, publishing, installing tools, or changing dependencies.
- [ ] Update canonical owners before summaries and links.
- [ ] Keep product, architecture, contributor, operations, command, and agent roles distinct.

## Verification and reporting

- [ ] Check changed local links, anchors where supported, and referenced paths.
- [ ] Verify command and configuration claims against current executable or test evidence.
- [ ] Discover validation commands and Cargo flags from the repository rather than assuming them.
- [ ] Inspect the final diff for stale identifiers, contradictions, and formatting churn.
- [ ] Separate passed, failed, skipped, unavailable, and manual checks.
- [ ] Report current-source limitations and never claim native/model compatibility from structure alone.
- [ ] For a no-op audit, list inspected evidence and explain why no edit was required.
