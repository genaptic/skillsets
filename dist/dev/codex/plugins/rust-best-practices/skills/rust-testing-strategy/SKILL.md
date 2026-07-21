---
name: rust-testing-strategy
description: >
  Plan and review reliable Rust unit, integration, doctest, binary-smoke, live-dependency, and end-to-end tests, including placement, fixtures, determinism, authorization, and evidence. Use when choosing the smallest test boundary or designing coverage across crates and processes. Do not use when public API documentation and doctest prose are the primary deliverable; use rustdoc-maintenance instead.
license: Apache-2.0
metadata:
  skillpack: "rust-best-practices"
  version: "1.0.0"
  maturity: "release-candidate"
---

## Outcome

Produce a repository-aligned Rust test plan or implementation in which each behavior is proven at
the narrowest trustworthy boundary, asynchronous behavior is deterministic, live dependencies are
explicitly authorized and isolated, and reported evidence distinguishes executed checks from
proposed coverage.

## Compatibility

Portable across Claude Code, Codex, and OpenCode. Follow the target repository's Rust toolchain,
edition, MSRV, workspace, features, lockfile policy, test runner, CI, and fixture conventions;
Edition 2024 examples require Rust 1.85 or newer. Templates are adaptable snippets and do not
authorize new dev-dependencies. Network/container tests are optional and require explicit
authority, available infrastructure, isolated credentials, and cleanup. Native-client
compatibility remains unverified until a validated report records the client version and exact
source SHA.

## Use this skill when

- Deciding whether a behavior needs a unit, integration, doctest, binary-smoke, or end-to-end test.
- Moving tests to the correct crate/process boundary or removing production-only test shims.
- Making async, timer, filesystem, environment, concurrency, or failure tests deterministic.
- Designing authorized tests against databases, brokers, containers, or external services.

## Do not use this skill when

- The primary output is public API prose, intra-doc links, examples, or rustdoc lints; use
  `rustdoc-maintenance`.
- General task ownership, cancellation, or shutdown implementation dominates; use
  `rust-async-concurrency`.
- The request primarily designs crate/workspace boundaries rather than test proof; use
  `rust-project-architecture`.
- The task only asks for a general Rust implementation review; use `rust-core-best-practices`.

## Inputs

Inspect workspace manifests and default members, package targets, public API, binary names,
feature/lockfile policy, CI jobs, repository test commands, existing fixtures, coverage policy,
external dependencies, permissions, credential sources, platform matrix, and the failure being
prevented. Identify which tests already prove the behavior and which claim remains unobserved.

## Safety

- Default to offline, hermetic tests. Do not access networks, start containers/services, install
  tools, download images, or use credentials without explicit authority.
- Never point a test at production. Use isolated namespaces, least-privilege disposable
  credentials, bounded timeouts, and cleanup that cannot delete outside its owned fixture.
- Avoid process-global environment mutation in parallel tests. Pass immutable config directly or
  set environment only on a child `Command`.
- Preserve unrelated worktree changes; do not commit, push, publish, or mutate remote state.
- Never convert an unavailable runtime or skipped test into a passing result.

## Procedure

1. **Establish repository truth.** Read manifests, CI, toolchain pins, test helpers, feature
   policy, and existing commands. Determine package/default-member selection and whether the
   lockfile is authoritative before choosing Cargo flags.
2. **State the contract.** Define the externally observable behavior, invariants, failure modes,
   platforms/features, and regression being prevented. Remove assertions that merely mirror the
   implementation.
3. **Choose the narrowest effective level.** Use unit tests for local behavior and owned fakes;
   integration tests for public crate APIs; doctests for executable API examples; binary tests for
   process contracts; and end-to-end tests only for cross-process/system behavior.
4. **Design seams without test-only production shape.** Inject owned dependencies through normal
   interfaces. Keep test helpers in `#[cfg(test)] mod tests`, crate `tests/`, or dedicated support
   crates; do not add production-scope test-only fields, constructors, trait impls, or imports.
5. **Control nondeterminism.** Use temporary directories, ephemeral ports, readiness signals,
   injected clocks, paused Tokio time, deterministic seeds, per-test namespaces, and bounded waits.
   Test non-finite and boundary numeric inputs where configuration accepts numbers.
6. **Authorize live dependencies.** Require an explicit opt-in, verify the target is isolated,
   prevent credential logging, set total deadlines, register ownership/cleanup, and fail as
   unavailable when prerequisites do not exist.
7. **Implement and verify incrementally.** Run the smallest affected test first, then the
   repository's broader required checks. Avoid assuming every repository supports
   `--workspace --all-targets --all-features --locked` together.
8. **Review evidence.** Confirm the test failed for the intended pre-fix behavior when practical,
   passes after the change, does not rely on hidden order or infrastructure, and leaves no residue.

## Verification

- Run repository-authoritative format, compile, lint, unit/integration, doctest, binary, and e2e
  commands that apply; list skipped commands and why.
- Test success, validation/error, boundary, cancellation/timeout, and cleanup paths proportional to
  risk. Include `NaN` and infinities for floating configuration parsers.
- For Tokio timer tests, use `#[tokio::test(start_paused = true)]` on the current-thread runtime or
  an injected clock. Do not use arbitrary sleeps for readiness.
- For live tests, record explicit authorization, endpoint/container identity, isolation,
  permissions, network/filesystem effects, cleanup result, and observed version—without secrets.

## Output contract

Return the repository test policy and assumptions, behavior-to-test-level matrix, fixtures and
side-effect boundaries, files changed, commands actually run and results, authorized live evidence
or unavailable prerequisites, residual coverage gaps, and remaining risks. Do not present a mock,
schema parse, or compile-only check as a native/live pass.

## Resources

- [Decision guide](references/guide.md) — levels, placement, seams, determinism, and evidence.
- [Async and live tests](references/async-live-tests.md) — paused time, readiness, authorization,
  isolation, and cleanup.
- [Checklist](references/checklist.md) — implementation and review gate.
- [Sources](references/sources.md) — primary documentation and decisions.
- [`unit_test_with_fake.rs`](assets/templates/unit_test_with_fake.rs),
  [`bin_smoke_test.rs`](assets/templates/bin_smoke_test.rs), and
  [`doctest_examples.rs`](assets/templates/doctest_examples.rs) are adaptable snippets, not
  standalone projects.
