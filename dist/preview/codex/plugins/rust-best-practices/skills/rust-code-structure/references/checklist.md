# Rust code structure checklist

## Model

- [ ] Inventory invariants, states, transitions, ownership, lifetimes, call sites, and representations.
- [ ] Use structs for values that coexist and data-carrying enums for mutually exclusive cases.
- [ ] Split types only across real invariant, lifecycle, ownership, or responsibility boundaries.
- [ ] Make invalid states unrepresentable where practical, or validate them once at a named boundary.

## Behavior and names

- [ ] Put behavior on a method when a natural receiver exists.
- [ ] Keep free functions when the operation is stateless, symmetric, adapter-like, or receiver-neutral.
- [ ] Use a type alias only when transparent identity is intended.
- [ ] Use a newtype for units, validation, identity, privacy, or distinct trait behavior.
- [ ] Replace ambiguous primitive groups and mode flags with named domain inputs where justified.
- [ ] Choose literals, constructors, conversions, or builders proportional to construction complexity.

## Compatibility and evidence

- [ ] Check public API, exhaustive matching, serialization, persistence, generated schema, and auto traits.
- [ ] Update callers and tests incrementally; include invalid and transition boundaries.
- [ ] Run repository-derived format, lint, check, and test commands.
- [ ] Review the final diff for needless churn, leaked representations, and unrelated edits.
- [ ] Report retained free functions/aliases and their rationale instead of applying blanket bans.
