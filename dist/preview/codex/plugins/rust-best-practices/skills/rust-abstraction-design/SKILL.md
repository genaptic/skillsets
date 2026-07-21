---
name: rust-abstraction-design
description: >
  Design or review Rust concrete APIs, generics, traits, trait objects, closed enums, lifetimes, typed errors, panic boundaries, and safe wrappers around unsafe code. Use when deciding whether repeated behavior justifies abstraction or selecting static versus dynamic polymorphism and API failure contracts. Do not use when the primary task is crate/module layout or organizing fields, states, functions, and methods around one domain owner; prefer rust-project-architecture or rust-code-structure.
license: Apache-2.0
metadata:
  skillpack: "rust-best-practices"
  version: "1.0.0"
  maturity: "release-candidate"
---

## Outcome

Produce the least powerful Rust abstraction that satisfies demonstrated reuse, substitution,
extension, lifetime, and failure requirements while keeping behavior understandable and safe.

## Compatibility

Portable across Claude Code, Codex, and OpenCode. Honor the target repository's Rust toolchain,
edition, MSRV, dependency versions, public API policy, object-safety requirements, and unsafe-code
rules. Edition 2024 examples require Rust 1.85 or newer. Optional network research requires
authorization; without it, qualify version-sensitive claims. Native-client compatibility remains
unverified without a dated exact-SHA report.

## Inputs

- Concrete use cases, callers, implementations, extension expectations, and performance constraints.
- Existing types, traits, generic bounds, lifetimes, errors, panics, unsafe blocks, and tests.
- Public API and compatibility commitments plus repository lint and dependency policy.
- Whether implementation families are closed, open, compile-time selected, or runtime selected.

## Safety

- Keep code concrete until reuse or variation pressure is demonstrated; do not introduce traits,
  generics, macros, or code generation speculatively.
- Treat public traits, generic bounds, auto traits, error variants, and lifetimes as compatibility
  contracts. Avoid broad changes without migration evidence.
- Keep required `unsafe` operations minimal, document invariants and `# Safety`, and expose a safe
  API only when those invariants can be upheld.
- Never hide recoverable failures behind panic, erase useful errors without context, install hidden
  dependencies, publish, or perform remote Git actions.

## Procedure

1. **Collect concrete pressure.** Inventory duplicated behavior, implementations, callers,
   substitution needs, runtime selection, ownership relationships, and failure modes.
2. **Stay concrete first.** Prefer a concrete type or focused helper until at least two credible
   uses share a stable contract. Remove accidental duplication before abstracting essential
   variation.
3. **Select the mechanism.** Use generics for compile-time variation and monomorphization; a trait
   for behavior shared by multiple implementations; a trait object for open runtime-selected
   implementations; and an enum for a closed, exhaustively handled family.
4. **Place the abstraction at the use boundary.** Keep traits narrow and consumer-driven. Avoid
   leaking implementation details through associated types, generic bounds, or error shapes.
5. **Model ownership and lifetimes.** Rely on elision when relationships are obvious. Add named
   lifetimes only to express a real borrow relationship. Prefer owned data for independently
   long-lived services and spawned work unless borrowing is intentional and bounded.
6. **Design failure contracts.** Return typed errors from reusable libraries when callers can act
   on categories. Add context at application boundaries. Validate non-finite numeric input when the
   domain requires finite values; do not model money with binary floating point.
7. **Set panic and unsafe boundaries.** Reserve panic for bugs or documented impossible invariants.
   Keep unsafe blocks small, state preconditions, test the safe wrapper, and follow Edition 2024
   unsafe-operation rules selected by the repository.
8. **Review complexity and compatibility.** Compare the abstraction with the concrete alternative.
   Check object safety, `Send`/`Sync`, allocation and dispatch cost, semver exposure, and testability.
9. **Verify against repository policy.** Run repository-derived format, lint, check, test, doctest,
   feature, and MSRV commands; report skipped configurations honestly.

## Verification

- Every abstraction is justified by named callers or implementations and has a stable responsibility.
- The selected mechanism matches closed/open and compile-time/runtime variation requirements.
- Borrow relationships, error categories, panic conditions, and unsafe invariants are documented.
- Tests cover each implementation, dispatch path, recoverable failure, boundary value, and safe API.
- Retained free functions and type aliases are evaluated contextually, not rejected by blanket rule.

## Output contract

Return the concrete pressure observed, mechanism decision and rejected alternatives, API and
compatibility effects, implementation or findings, verification evidence, and remaining risks.

## Resources

- Read [the guide](references/guide.md) for generics, traits, trait objects, enums, lifetimes,
  typed errors, panic, unsafe, and decision examples.
- Use [the checklist](references/checklist.md) before accepting an abstraction.
- Consult [the primary sources](references/sources.md) for version-sensitive language behavior.
- Read [the enum-dispatch pattern](references/enum-dispatch.md) when modeling a closed runtime-
  selected family.
- Treat [`enum_dispatch.rs`](assets/templates/enum_dispatch.rs) and
  [`typed_error.rs`](assets/templates/typed_error.rs) as adaptable, rustfmt-clean snippets rather
  than standalone Cargo projects.
