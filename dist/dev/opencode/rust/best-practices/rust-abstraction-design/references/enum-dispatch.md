# Closed-family enum dispatch

Use this pattern when the application owns a small closed implementation family and selects one at
runtime. Adapt visibility, sync/async behavior, errors, and construction to the target repository.

## Contents

- [Decision checklist](#decision-checklist)
- [Direct enum dispatch](#direct-enum-dispatch)
- [Trait-backed enum dispatch](#trait-backed-enum-dispatch)
- [Async considerations](#async-considerations)
- [Anti-patterns](#anti-patterns)
- [Review checklist](#review-checklist)

## Decision checklist

Enum dispatch is a strong fit when:

- supported implementations are intentionally closed;
- exhaustive matching should reveal missing integration work;
- configuration selects a variant at runtime;
- variants can be represented without exposing an open plugin API;
- variant-specific dependencies can remain within their implementation modules.

Prefer a trait object when downstream or dynamically loaded implementations must be open. Prefer a
generic parameter when selection is compile-time and callers benefit from static dispatch. Stay
concrete when there is only one credible implementation.

## Direct enum dispatch

When variants share only a few operations, direct inherent methods can be enough:

```rust
pub struct LocalStore;
pub struct RemoteStore;

impl LocalStore {
    fn load(&self, key: &str) -> Result<Vec<u8>, LoadError> {
        Ok(format!("local:{key}").into_bytes())
    }
}

impl RemoteStore {
    fn load(&self, key: &str) -> Result<Vec<u8>, LoadError> {
        Ok(format!("remote:{key}").into_bytes())
    }
}

pub enum Store {
    Local(LocalStore),
    Remote(RemoteStore),
}

impl Store {
    pub fn load(&self, key: &str) -> Result<Vec<u8>, LoadError> {
        match self {
            Self::Local(store) => store.load(key),
            Self::Remote(store) => store.load(key),
        }
    }
}

#[derive(Debug)]
pub struct LoadError;
```

Exhaustive arms make a new variant fail to compile until dispatch is handled. Do not add `_` when
that would hide missing family integration.

## Trait-backed enum dispatch

A trait is useful when the shared contract is independently valuable for tests, consumers, or
implementation consistency:

```rust
pub trait Render {
    fn render(&self, input: &str) -> Result<String, RenderError>;
}

pub struct Plain;
pub struct Html;

impl Render for Plain {
    fn render(&self, input: &str) -> Result<String, RenderError> {
        Ok(input.to_owned())
    }
}

impl Render for Html {
    fn render(&self, input: &str) -> Result<String, RenderError> {
        Ok(format!("<p>{}</p>", escape_html(input)))
    }
}

pub enum Renderer {
    Plain(Plain),
    Html(Html),
}

impl Render for Renderer {
    fn render(&self, input: &str) -> Result<String, RenderError> {
        match self {
            Self::Plain(renderer) => renderer.render(input),
            Self::Html(renderer) => renderer.render(input),
        }
    }
}

fn escape_html(input: &str) -> String {
    input.replace('&', "&amp;").replace('<', "&lt;")
}

#[derive(Debug)]
pub struct RenderError;
```

The free `escape_html` helper is appropriate here because it is a stateless algorithm without a
natural domain receiver. In production use a complete, reviewed escaping implementation; this
minimal snippet is not a security-grade HTML renderer.

Whether the trait is public, crate-private, or omitted depends on its consumers. Do not require a
private trait solely because one repository used that convention.

## Async considerations

On toolchains supporting async functions in traits for the required use, native async methods may
fit internal/static-dispatch contracts. Public traits and trait objects require careful examination
of dyn compatibility, allocation, `Send`, and semver. Follow the repository's locked dependency and
MSRV policy rather than adding an async-trait helper implicitly.

For a closed enum, direct async dispatch avoids object safety:

```rust
pub enum Fetcher {
    Cached(CachedFetcher),
    Live(LiveFetcher),
}

impl Fetcher {
    pub async fn fetch(&self, key: &str) -> Result<Vec<u8>, FetchError> {
        match self {
            Self::Cached(fetcher) => fetcher.fetch(key).await,
            Self::Live(fetcher) => fetcher.fetch(key).await,
        }
    }
}
#
# pub struct CachedFetcher;
# pub struct LiveFetcher;
# pub struct FetchError;
# impl CachedFetcher { async fn fetch(&self, key: &str) -> Result<Vec<u8>, FetchError> { Ok(key.as_bytes().to_vec()) } }
# impl LiveFetcher { async fn fetch(&self, key: &str) -> Result<Vec<u8>, FetchError> { Ok(key.as_bytes().to_vec()) } }
```

Keep timeouts, cancellation, concurrency, and shutdown policy in the owning async workflow; enum
dispatch alone does not solve those concerns.

## Anti-patterns

- A catch-all arm that silently maps a new implementation to old behavior.
- A shared enum that accumulates unrelated provider details and creates dependency cycles.
- A public trait with many methods added only to make every implementation look identical.
- Reusing configuration/discriminant enums as a dumping ground for secrets, diagnostics, or
  protocol-specific capability checks.
- Macros/code generation that obscure a small, reviewable dispatch table without measurable value.
- Duplicate inherent and trait methods whose same names create recursion or ambiguous delegation.
- Treating receiver syntax or UFCS as universally invalid; use the clearest form that avoids
  recursion and follows repository policy.

## Review checklist

- [ ] The implementation family is intentionally closed.
- [ ] Each variant owns its implementation-specific data and dependencies.
- [ ] Dispatch covers every variant explicitly where exhaustiveness is required.
- [ ] The trait exists only if it serves callers, tests, or a stable shared contract.
- [ ] Errors preserve actionable categories without leaking implementation secrets.
- [ ] Sync/async, `Send`/`Sync`, lifetime, allocation, and cancellation behavior are explicit.
- [ ] Tests exercise every variant and prove a newly added variant cannot be silently ignored.
