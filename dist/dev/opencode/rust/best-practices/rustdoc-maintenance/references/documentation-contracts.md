# Rustdoc documentation contracts

## First sentence

Write a concise, standalone sentence that tells users what the item does. Rustdoc reuses summaries in
search and module listings. Avoid repeating the complete signature or beginning with “This function.”

## Crate and module docs

- Explain the role and intended audience.
- Present the main concepts and supported path through the API.
- Link to important public types and functions.
- Describe feature or platform gates that affect discoverability.
- Keep implementation architecture out unless callers need it to use the API correctly.

## Contract sections

### Errors

Describe actionable classes of failure and how callers can distinguish or avoid them. Keep names
aligned with public error types. Do not promise an exhaustive set when underlying I/O or dependency
errors may grow.

### Panics

Document reachable, caller-relevant panic conditions. If a panic would indicate an internal defect,
prefer eliminating it or documenting the stronger invariant rather than normalizing panic behavior.

### Safety

For unsafe APIs, state every obligation the caller must uphold: validity, alignment, initialization,
aliasing, lifetime, concurrency, provenance, ownership, and cleanup as applicable. A vague “caller
must ensure safety” section is not a contract.

### Examples

Show a supported outcome, not a synthetic tour of every parameter. Hidden lines may provide imports,
setup, or a `Result`-returning wrapper. Keep visible code copyable and avoid `unwrap` when it distracts
from a fallible public contract.

## Fence selection

| Fence | Use | Do not use as |
|---|---|---|
| ordinary Rust | runnable, deterministic example | a live integration test |
| `no_run` | compile-checked example with a real execution boundary | a fix for runtime failure |
| `compile_fail` | intentional compiler rejection | an example with unstable diagnostics |
| `ignore` | exceptional case with explicit reason | a blanket escape from maintenance |
| `text` | non-Rust output or protocol excerpt | untested Rust code |

## Intra-doc links

Prefer item links that rustdoc resolves in context. Qualify ambiguous names and verify re-exports and
feature-gated targets. Do not link to private implementation paths when the public path is different.

## Evidence boundaries

A successful doc build proves rendering and resolution for the selected configuration. A successful
doctest proves example compilation/execution for the selected configuration. Neither alone proves all
features, platforms, external services, native clients, or the semantic accuracy of prose.
