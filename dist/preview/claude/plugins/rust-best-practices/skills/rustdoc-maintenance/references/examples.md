# Rustdoc examples and boundaries

## Runnable fallible example

Prefer hidden setup that keeps the visible path honest. Adaptable documentation snippet:

```rust
/// Parses one identifier.
///
/// # Errors
///
/// Returns [`ParseError`] when `input` is not a supported identifier.
///
/// # Examples
///
/// ```
/// # fn main() -> Result<(), example_crate::ParseError> {
/// let id = example_crate::Identifier::parse("alpha-7")?;
/// assert_eq!(id.as_str(), "alpha-7");
/// # Ok(())
/// # }
/// ```
```

Adapt crate and item names to the target project. Do not add a fake dependency solely for an example.

## Compile-only environment boundary

`no_run` may be appropriate when the documented call requires credentials or a live service, but the
example should still construct inputs without embedding secrets. State the execution prerequisite in
prose and keep a separate authorized integration test for live behavior.

## Feature-gated example

When an item exists only under a feature, say so near the item and ensure the repository's selected
doctest command enables that feature. Do not assert that “all features pass” from a default-feature run.

## Panic contract

Bad:

> # Panics
> May panic.

Better:

> # Panics
> Panics when `index` is greater than the number of initialized entries.

Then verify that exact condition against implementation and tests. Prefer a fallible API if callers
can reasonably encounter the condition.

## Unsafe contract

Bad:

> # Safety
> The pointer must be valid.

Better: state the required allocation, alignment, initialized byte range, lifetime, aliasing,
thread-safety, ownership-transfer, and cleanup obligations that actually apply.

## Workspace Markdown boundary

If an API change also makes README or architecture prose stale, report that drift. Do not silently
expand a rustdoc-only task; use the workspace-documentation workflow when Markdown is authorized.
