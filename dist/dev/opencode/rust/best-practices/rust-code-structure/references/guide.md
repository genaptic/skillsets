# Rust code structure guide

Use this guide to decide how structs, enums, functions, methods, constructors, builders, aliases,
and state transitions should express a domain.

## Contents

- [Start with invariants](#start-with-invariants)
- [Choose structs and enums](#choose-structs-and-enums)
- [Split by lifecycle and ownership](#split-by-lifecycle-and-ownership)
- [Place behavior deliberately](#place-behavior-deliberately)
- [Use aliases and newtypes intentionally](#use-aliases-and-newtypes-intentionally)
- [Replace primitive soup](#replace-primitive-soup)
- [Choose construction patterns](#choose-construction-patterns)
- [Preserve compatibility](#preserve-compatibility)
- [Review heuristics](#review-heuristics)

## Start with invariants

Do not begin by counting fields or functions. Write down:

- which values must exist together;
- which states are mutually exclusive;
- which transitions are allowed;
- who owns each value and for how long;
- which operations read, mutate, or consume it;
- which representations are public, serialized, or persisted;
- which invalid states currently require repeated runtime checks.

The best type shape is the smallest one that makes those facts legible. Repository policy and
compatibility commitments override generic taste.

## Choose structs and enums

Use a struct when fields form one valid value at the same time:

```rust
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct RetryPolicy {
    pub max_attempts: std::num::NonZeroU32,
    pub initial_delay: std::time::Duration,
}
```

Use a data-carrying enum for mutually exclusive cases with different required data:

```rust
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Delivery {
    Email { address: String },
    Webhook { url: String, secret_id: String },
    Disabled,
}
```

This is usually clearer than a `kind: String` plus several `Option` fields. The enum lets matching
code handle every declared case and prevents invalid cross-case combinations.

Do not force an enum when cases must be externally extensible or unknown values must round-trip.
For wire protocols, a raw representation plus validated domain conversion may preserve forward
compatibility better than a closed public enum.

## Split by lifecycle and ownership

A large struct is not automatically a god object. Split it when groups have different invariants,
owners, lifetimes, mutation patterns, security sensitivity, or persistence behavior.

Common lifecycle groups include:

- immutable startup configuration;
- validated request input;
- durable domain state;
- runtime coordination handles;
- transient output or diagnostics.

Avoid families such as `JobInput`, `JobPlan`, `JobRunning`, and `JobComplete` when they duplicate
identity and common fields without clarifying transitions. Often one owner plus a state enum is
cleaner:

```rust
pub struct Job {
    id: JobId,
    state: JobState,
}

pub enum JobState {
    Pending { request: Request },
    Running { started_at: std::time::Instant },
    Complete { output: Output },
    Failed { error: JobError },
}
```

But typestate structs can be appropriate when compile-time transition enforcement materially helps
and conversion cost/API complexity is acceptable. Evaluate the tradeoff rather than banning suffix
families by name.

## Place behavior deliberately

Use an inherent method when behavior has a natural receiver:

- `&self` observes the value;
- `&mut self` changes it while preserving its identity;
- `self` consumes it into a new state or output;
- `Type::new` or another associated function constructs the type.

Use a free function when no receiver is naturally privileged:

- a symmetric operation over peer values;
- a stateless algorithm over generic inputs;
- an adapter between two external/domain types;
- a callback or function pointer;
- module-level orchestration whose state is already explicit in parameters.

The Rust API Guidelines recommend methods when there is a clear receiver, but explicitly describe
the guidelines as recommendations rather than mandates. Do not invent a receiver merely to make a
function associated. Conversely, several free functions repeatedly accepting the same domain value
often signal missing owned behavior.

Keep functions focused regardless of placement. Parameter count alone is not a rule, but repeated
groups and ambiguous primitives are signals to name a request/options/domain type.

## Use aliases and newtypes intentionally

A type alias creates a synonym, not a distinct type:

```rust
pub type Headers = std::collections::BTreeMap<String, String>;
```

This can improve readability when transparency is desired. It does not enforce invariants, prevent
argument swaps, hide representation, or provide a separate constructor.

Use a newtype for semantic distinction:

```rust
#[derive(Debug, Clone, PartialEq, Eq, Hash)]
pub struct UserId(String);

impl UserId {
    pub fn parse(value: impl Into<String>) -> Result<Self, UserIdError> {
        let value = value.into();
        if value.trim().is_empty() {
            return Err(UserIdError::Empty);
        }
        Ok(Self(value))
    }
}
```

Associated types are part of a trait contract and serve a different purpose: they let each
implementation select a related type. Do not replace them mechanically with wrappers.

## Replace primitive soup

Primitive soup appears when several `String`, `bool`, integer, or duration parameters carry domain
meaning only by position or convention. Improve it selectively:

- use newtypes for values with units, validation, identity, or privacy;
- use an options/request struct for values configured and passed together;
- use an enum for a closed mode with distinct behavior;
- use `NonZero*`, bounded constructors, or validated collections when zero/empty is invalid;
- keep a primitive when its meaning is obvious, local, and unconstrained.

Boolean parameters are fine for literal binary facts (`is_visible`) but poor for behavior modes at
call sites (`run(true, false)`). A named enum such as `OutputMode::Json` communicates intent and can
grow deliberately.

## Choose construction patterns

| Need | Prefer |
|---|---|
| simple transparent data | struct literal when fields are intentionally public |
| direct valid construction | inherent `new`/domain-named constructor |
| infallible conversion | `From`/`Into` |
| fallible conversion | `TryFrom`/`FromStr` or a named parser |
| many optional values | builder or options struct |
| staged required inputs | typestate builder only when compile-time proof pays for complexity |

Do not make `new` return an invalid value that every caller must repair. Avoid builders for two
obvious required fields. If construction can fail, expose that fact in the return type.

## Preserve compatibility

Before reshaping a public or serialized type, check:

- downstream construction and pattern matching;
- Serde/default/rename/unknown-field behavior;
- stored data and wire compatibility;
- trait implementations and auto traits (`Send`, `Sync`, `Unpin`);
- exhaustive enum matching and `#[non_exhaustive]` policy;
- error variant matching and source chains;
- generated schema or bindings.

An internal cleanup may be a public breaking change. Use explicit conversion layers or staged
migration when needed, document the compatibility window, and test both representations if both are
promised.

## Review heuristics

Ask these questions rather than enforcing syntax bans:

- Does this type encode one coherent invariant?
- Can invalid cross-field/state combinations be constructed?
- Is behavior on the type with the clearest ownership, or is a free function more neutral?
- Does an alias intentionally preserve type identity, or should a newtype distinguish it?
- Are clones and allocations required by ownership, or hiding a poor interface?
- Are public fields and enum variants stable commitments?
- Is a builder earning its complexity?
- Do tests exercise transitions and invalid boundaries rather than implementation details?

See [worked examples](type-model-examples.md) for larger before/after models.
