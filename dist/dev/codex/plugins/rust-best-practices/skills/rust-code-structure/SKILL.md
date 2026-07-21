---
name: rust-code-structure
description: >
  Structure or refactor Rust structs, enums, functions, methods, constructors, builders, state models, and repeated parameter groups so ownership and invariants are explicit. Use when Rust code contains primitive soup, boolean or stringly typed state, Option-heavy pseudo-variants, god structs, misplaced behavior, or unclear lifecycle data. Do not use for crate/module layout or for choosing traits, generics, trait objects, lifetimes, and public error abstractions as the primary outcome; prefer rust-project-architecture or rust-abstraction-design.
license: Apache-2.0
metadata:
  skillpack: "rust-best-practices"
  version: "1.0.0"
  maturity: "release-candidate"
---

## Outcome

Produce cohesive Rust types and functions whose shape makes valid states, ownership, invariants,
and behavior placement clear without imposing repository-specific bans on language features.

## Compatibility

Portable across Claude Code, Codex, and OpenCode. Follow the target repository's selected Rust
toolchain, edition, MSRV, lint policy, API stability, and serialization compatibility. Edition 2024
examples require Rust 1.85 or newer. Network access is optional and never needed for the core
workflow; report any unverified version-sensitive claim. Native-client compatibility remains
unverified without a dated exact-SHA report.

## Inputs

- The behavior to add, refactor, or review and its observable acceptance criteria.
- Existing domain types, call sites, state transitions, serialization/wire formats, and tests.
- Repository conventions for public API, naming, ownership, error handling, and compatibility.
- Constraints on allocation, borrowing, concurrency, persistence, and downstream callers.

## Safety

- Preserve serialized representations, public constructors, match exhaustiveness, and external API
  compatibility unless change is explicitly authorized and migrated.
- Do not mechanically replace every free function, type alias, `Option`, boolean, or clone. Treat
  each as a design choice whose correctness depends on semantics and repository policy.
- Avoid broad rewrites. Change one responsibility or invariant at a time and keep tests executable.
- Do not install dependencies, publish, or perform remote Git actions.

## Procedure

1. **Inventory the model.** Identify domain values, invariants, states, transitions, repeated
   parameter groups, ownership, existing `impl` blocks, free functions, aliases, and call sites.
2. **Choose structs versus enums.** Use a struct for values that exist together. Use a data-carrying
   enum for mutually exclusive cases. Avoid a tag plus unrelated optional fields when variants can
   encode required data directly.
3. **Split by invariant and lifecycle.** Separate configuration, request input, durable domain
   state, and runtime coordination when they have different validity or ownership rules. Do not
   split cohesive data merely to reduce field count.
4. **Place behavior at its natural owner.** Use methods when behavior reads, mutates, consumes, or
   constructs a type with a clear receiver. Keep free functions for stateless algorithms,
   symmetric operations, adapters, callbacks, or module-level behavior without a natural receiver.
5. **Name semantic distinctions.** Use a newtype when identity, validation, units, privacy, or trait
   behavior differs. Use a type alias when a transparent synonym improves readability and no new
   invariant or type distinction is intended. Associated types belong to trait contracts.
6. **Replace primitive soup deliberately.** Group arguments that travel together and share an
   invariant. Replace boolean mode flags or string tags with enums when the set is closed and the
   states have distinct behavior or data.
7. **Choose construction appropriate to validity.** Use literals for simple transparent data,
   inherent constructors for direct valid construction, `From` for infallible conversions,
   `TryFrom` for fallible conversions, and builders for many optional or staged inputs.
8. **Update callers and tests incrementally.** Preserve semantics at each step. Add compile-time or
   runtime tests for invalid states, transition boundaries, and compatibility-sensitive formats.
9. **Verify and review.** Run repository-derived format, lint, check, and test commands; inspect the
   final diff for needless churn, leaked representations, and unhandled variants.

## Verification

- Each type and function has one explainable responsibility and a deliberate ownership model.
- Invalid states are unrepresentable where practical, or validated at a named boundary.
- Methods have natural receivers; retained free functions and type aliases have stated rationale.
- Public/serialized compatibility changes are migrated and tested rather than assumed.
- Relevant success, failure, transition, and exhaustive-match paths are covered.

## Output contract

Return the model inventory, structural decisions and tradeoffs, changes or review findings,
compatibility effects, verification commands and results, and remaining risks.

## Resources

- Read [the guide](references/guide.md) for detailed examples and decision tables.
- Use [the checklist](references/checklist.md) before completing a structure change.
- Consult [the primary sources](references/sources.md) for Rust type, item, method, and API guidance.
- Read [worked type-model examples](references/type-model-examples.md) when refactoring primitive
  soup, pseudo-variants, god structs, or misplaced behavior.
