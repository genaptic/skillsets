# Rust abstraction checklist

## Pressure and selection

- [ ] Name the concrete callers, implementations, duplication, or extension pressure.
- [ ] Compare the abstraction with retaining concrete code.
- [ ] Use generics for compile-time variation, traits for shared behavior, trait objects for open runtime sets, and enums for closed sets.
- [ ] Keep consumer-driven traits narrow and defaults valid for every implementation.
- [ ] Check object safety, ownership, lifetimes, `Send`/`Sync`, allocation, and dispatch cost.

## Failures and safety

- [ ] Use explicit lifetimes only for real borrow relationships; choose owned data for independent lifecycles.
- [ ] Preserve actionable typed error categories and source context without leaking sensitive data.
- [ ] Reject non-finite numeric input where the domain requires finite values; avoid floating-point money.
- [ ] Reserve panic for bugs or documented impossible invariants.
- [ ] Keep unsafe blocks minimal, validate preconditions, document invariants/`# Safety`, and test the safe wrapper.

## Compatibility and verification

- [ ] Review public traits, implementors, bounds, associated types, errors, auto traits, and semver impact.
- [ ] Test each implementation/variant, dispatch path, failure category, and boundary value.
- [ ] Run repository-derived format, lint, check, test, doctest, feature, MSRV, and platform commands.
- [ ] Report skipped configurations and version-sensitive assumptions.
- [ ] Keep free functions and type aliases when context justifies them; do not apply repository-external bans.
