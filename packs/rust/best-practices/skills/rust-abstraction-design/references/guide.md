# Rust abstraction design guide

Use this reference to choose between concrete code, generics, traits, trait objects, enums,
lifetimes, errors, panic, and safe wrappers around unsafe operations.

## Contents

- [Require concrete pressure](#require-concrete-pressure)
- [Choose the mechanism](#choose-the-mechanism)
- [Design consumer-driven traits](#design-consumer-driven-traits)
- [Use enum dispatch for closed families](#use-enum-dispatch-for-closed-families)
- [Model lifetimes and ownership](#model-lifetimes-and-ownership)
- [Design typed errors](#design-typed-errors)
- [Handle numeric domains](#handle-numeric-domains)
- [Set panic boundaries](#set-panic-boundaries)
- [Wrap unsafe code safely](#wrap-unsafe-code-safely)
- [Review cost and compatibility](#review-cost-and-compatibility)

## Require concrete pressure

Start with concrete implementations. Abstract when evidence shows a stable shared contract:

- multiple implementations are already required;
- callers need substitution or test doubles;
- duplicated logic expresses the same invariant rather than coincidental syntax;
- a runtime-selected family has a common operation;
- a public API must support controlled extension;
- a generic algorithm benefits materially from accepting a capability rather than a concrete type.

Two similar functions are not automatically one abstraction. First normalize names and data flow,
then identify what truly varies. Delay extraction if the shared contract is still moving.

Do not create a trait for every struct, a generic parameter used once, a macro for a handful of
clear match arms, or a service object merely to avoid free functions. Each abstraction creates API,
compile-time, diagnostics, documentation, and maintenance cost.

## Choose the mechanism

| Need | Typical choice | Main tradeoff |
|---|---|---|
| one implementation, no substitution | concrete type/function | simplest and clearest |
| compile-time variation | generic parameter / `impl Trait` | monomorphization and bounds in API |
| shared behavior across implementations | trait | compatibility and coherence contract |
| open runtime-selected implementations | trait object | allocation/indirection/object safety |
| closed runtime-selected family | enum | explicit variants and exhaustive dispatch |
| repeated syntax with stable grammar | macro, cautiously | diagnostics and hidden control flow |

Generics are useful when the caller or compiler should select the implementation and static
dispatch matters. `impl Trait` can keep a signature focused when callers need capabilities but not
the concrete type. Avoid long bound lists that expose implementation detail.

Trait objects (`dyn Trait`) fit plugin-like or runtime-configured open sets. Confirm object safety,
lifetime, ownership, `Send`/`Sync`, and allocation requirements. Do not reach for `Box<dyn Trait>`
when a closed enum is clearer and exhaustive handling is valuable.

## Design consumer-driven traits

Define the smallest behavior the consumer actually needs, near that consumer when repository
architecture permits. A narrow trait is easier to implement, mock, evolve, and reason about.

```rust
pub trait Clock {
    fn now(&self) -> std::time::SystemTime;
}

pub fn is_expired(clock: &impl Clock, deadline: std::time::SystemTime) -> bool {
    clock.now() >= deadline
}
```

Avoid mirroring every inherent method, returning concrete implementation details, or requiring
unrelated capabilities. Decide deliberately whether callers implement the trait downstream. A
sealed trait can preserve evolution room, but sealing also prevents extension and must match the
public contract.

Associated types fit one related type per implementation. Generic method/type parameters fit when
the caller chooses among many inputs. Evaluate object safety if trait objects may be needed.

Default methods should express valid behavior for every implementation. Do not provide a default
that silently drops data or weakens safety.

## Use enum dispatch for closed families

An enum works well when the application owns all variants, configuration selects among them at
runtime, exhaustive handling is useful, and exposing an open plugin surface is unnecessary.

Keep dispatch explicit enough to review. Each variant payload can own its implementation and share
a private or public trait when that contract has independent value. Direct inherent-method dispatch
can also be appropriate when there is no need for substitution outside the enum.

Do not make one repository's preferred enum-dispatch shape a universal mandate. Receiver-method
syntax, UFCS, macros, and generated dispatch are language/tool choices; evaluate clarity,
maintainability, diagnostics, and repository policy. See [enum-dispatch.md](enum-dispatch.md) for a
complete adaptable pattern.

## Model lifetimes and ownership

Lifetime elision handles most functions:

```rust
pub fn first_line(input: &str) -> Option<&str> {
    input.lines().next()
}
```

Name lifetimes when the relationship is ambiguous or part of a type:

```rust
pub fn choose_longer<'a>(left: &'a str, right: &'a str) -> &'a str {
    if left.len() >= right.len() { left } else { right }
}
```

Explicit lifetimes do not extend data lifetime. They describe relationships the borrow checker must
enforce. Prefer owned data for independently long-lived services, caches, background tasks, and
spawned futures unless bounded borrowing is an intentional performance/design decision.

Borrowing views remain valuable for parsers, slices, and short transformations. Avoid converting
everything to `String` or `'static` merely to quiet errors; instead find the real owner and lifecycle.

## Design typed errors

Reusable library errors should expose categories callers can act on without forcing string parsing.
Keep variants stable enough for the public contract and preserve source errors where helpful.

```rust
#[derive(Debug)]
pub enum ParseCountError {
    Invalid(std::num::ParseIntError),
    Zero,
}

pub fn parse_count(input: &str) -> Result<std::num::NonZeroU32, ParseCountError> {
    let value = input.parse().map_err(ParseCountError::Invalid)?;
    std::num::NonZeroU32::new(value).ok_or(ParseCountError::Zero)
}
```

Application boundaries can add human context, choose presentation, and map errors to process/API
contracts. Avoid erasing typed categories too early. Do not leak secrets, tokens, full response
bodies, or sensitive paths through diagnostic context.

An error enum is not always required. A private focused function may return an existing standard
error; a public library may use a non-exhaustive struct to retain evolution flexibility. Follow the
repository's dependency and semver policy before introducing an error crate.

## Handle numeric domains

Floating-point parsing accepts `NaN` and infinity. If the domain requires an ordered finite value,
validate `is_finite()` explicitly. Reject values outside domain bounds after parsing.

Do not use `f32`/`f64` for money. Prefer an integer minor-unit newtype when currency/scale are fixed,
or a decimal representation selected by repository requirements. Define overflow, rounding, scale,
and serialization behavior.

Use standard constrained types such as `NonZeroU32` when they match the invariant, but do not force
them into public APIs when compatibility or ergonomics outweigh the benefit.

## Set panic boundaries

Use `Result` or `Option` for expected failure: invalid input, I/O, unavailable services, missing
configuration, parse failure, or resource exhaustion. Panic is appropriate for bugs and internal
invariants whose violation means the program cannot proceed correctly.

In tests, `unwrap` can keep the intended assertion clear. In production code, an `expect` should
state why failure is impossible, not merely repeat the operation. Libraries should document public
panic conditions and avoid panics controlled by untrusted input.

Do not call `process::exit` in reusable/domain code. Return errors to an executable boundary so
normal cleanup and testability are preserved.

## Wrap unsafe code safely

Use unsafe only when safe Rust cannot express the required operation and the value outweighs its
audit cost. A safe wrapper must establish every precondition before entering the unsafe operation
and prevent callers from violating invariants afterward.

Review:

- pointer validity, alignment, provenance, initialization, and aliasing;
- lengths, bounds, layout, and overflow;
- thread-safety and auto-trait implications;
- ownership transfer and destructor behavior;
- unwind behavior and FFI ABI;
- Edition 2024 unsafe-operation requirements.

Keep `unsafe` blocks small and pair each with a `SAFETY:` explanation tied to checked facts. An
`unsafe fn` does not make every operation inside automatically acceptable under modern policy.
Document a public unsafe function's caller contract under `# Safety`.

Global environment mutation may be unsafe in multithreaded programs on Edition 2024-era Rust.
Prefer immutable configuration or `Command::env` for child processes.

## Review cost and compatibility

Before accepting an abstraction, compare it with concrete code:

- readability and discoverability;
- compile time and monomorphized code size;
- runtime allocation and dynamic dispatch;
- diagnostics and debuggability;
- object safety and auto traits;
- public semver surface and downstream implementations;
- testability without over-mocking;
- migration cost and feature interactions.

Verify every concrete implementation/variant and failure category. Run repository-derived feature,
MSRV, lint, doctest, and platform checks. Report configurations not exercised.
