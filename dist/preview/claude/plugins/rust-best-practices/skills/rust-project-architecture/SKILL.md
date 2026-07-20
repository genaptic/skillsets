---
name: rust-project-architecture
description: >
  Design or review Rust package, crate, module, target, binary/library, workspace, ownership-seam, and test-placement boundaries. Use when creating or restructuring Cargo projects, deciding whether code belongs in an existing crate or a new package, keeping binaries thin, or reducing layout-driven coupling and clone-heavy data flow. Do not use for primarily internal type/API design, async behavior, test implementation, dependency selection, or adding one CLI command; prefer the corresponding specialized Rust skill.
license: Apache-2.0
metadata:
  skillpack: "rust-best-practices"
  version: "1.0.0"
  maturity: "release-candidate"
---

## Outcome

Produce a repository-aligned Rust architecture whose crate, module, target, and test boundaries
express real ownership, dependency, deployment, reuse, or release seams without needless packages.

## Compatibility

Portable across Claude Code, Codex, and OpenCode. Follow the target repository's Cargo layout,
toolchain, edition, MSRV, feature, lockfile, and CI policy. Edition 2024 templates require Rust 1.85
or newer. Optional research may use the network only when authorized; otherwise report freshness
gaps. Native-client compatibility remains unverified without a dated exact-SHA report.

## Inputs

- The requested architectural outcome and constraints.
- Workspace/package manifests, target trees, public APIs, dependency graph, CI, and test layout.
- Deployment units, ownership boundaries, reuse consumers, platform constraints, and release policy.
- Evidence about existing responsibilities, duplicated behavior, and data ownership seams.

## Safety

- Preserve public APIs, package names, feature semantics, paths, and release boundaries unless the
  request explicitly authorizes migration.
- Preview moves and manifest changes before applying them. Preserve unrelated edits and generated
  files managed by repository tooling.
- Do not add crates or dependencies merely to mirror conceptual layers.
- Do not install tools, publish packages, run remote Git operations, or execute live/integration
  infrastructure without explicit authorization.

## Procedure

1. **Inventory the current graph.** Read repository instructions, workspace/package manifests,
   targets, modules, public exports, feature edges, tests, CI, and deployment entrypoints. Identify
   consumers and actual ownership boundaries.
2. **Define responsibilities.** Give each proposed crate/module one cohesive job. Record which
   state and behavior it owns, which direction dependencies flow, and which APIs cross boundaries.
3. **Choose the smallest viable boundary.** Extend an existing crate when ownership, dependencies,
   release cadence, and deployment remain shared. Use `src/bin/` for small additional binaries
   sharing a domain. Add a package only for a real boundary such as independent reuse, dependency
   isolation, deployment, platform support, ownership, or release.
4. **Keep executable shells thin.** Put reusable parsing-independent behavior in a library; keep
   process setup, CLI parsing, logging setup, exit mapping, and shutdown wiring at executable edges.
5. **Organize modules by domain and behavior.** Prefer names that expose responsibility. Follow the
   repository's module-file convention; both `foo.rs` plus `foo/` and `foo/mod.rs` are valid Rust.
6. **Design ownership seams.** Borrow during validation and internal reads. Move or clone only where
   data becomes independently owned, such as persistence, queues, spawned tasks, or returned values.
7. **Place tests narrowly.** Keep private implementation tests beside code, public integration tests
   under `tests/`, reusable executable examples under `examples/`, and true multi-package/system
   journeys in an explicit end-to-end boundary.
8. **Preview and implement incrementally.** Update manifests and moves in reviewable stages. Avoid
   compatibility shims unless a documented migration requires them.
9. **Verify the graph.** Run repository-derived formatting, metadata, check, test, documentation,
   feature, and platform commands. Inspect dependency direction and final diff.

## Verification

- Every crate/module has a stated responsibility and evidence-backed boundary.
- Public paths, features, package selection, test discovery, and binary behavior remain intentional.
- No new cycle, accidental public API, duplicated binary logic, or unnecessary clone is introduced.
- Complete templates compile under their declared toolchain; snippets are labeled and adapted.
- Commands, unavailable checks, migration risks, and compatibility assumptions are reported exactly.

## Output contract

Return the current-state inventory, boundary decision record, proposed or applied layout, API and
migration effects, verification evidence, and unresolved risks.

## Resources

- Read [the guide](references/guide.md) for target layouts, boundary decisions, test placement,
  ownership seams, and worked examples.
- Use [the checklist](references/checklist.md) for design and final review.
- Consult [the primary sources](references/sources.md) for Cargo layout and workspace behavior.
- [The thin-lib-bin template](assets/templates/thin-lib-bin/) is a complete single-package
  library-plus-binary template.
- [The workspace-root template](assets/templates/workspace-root/) is a complete minimal virtual
  workspace template; rename its example packages and reconcile metadata, MSRV, and commands with
  the target repository.
