# Networking sources

Recheck version-sensitive APIs and client rules at execution time against the target lockfile,
enabled features, and current official documentation.

- [Agent Skills specification](https://agentskills.io/specification) — portable skill structure
  and progressive disclosure.
- [Codex skills](https://developers.openai.com/codex/build-skills) — current Codex discovery and
  authoring guidance.
- [Claude Code skills](https://code.claude.com/docs/en/skills) — current Claude Code skill format
  and behavior.
- [OpenCode skills](https://opencode.ai/docs/skills/) — current OpenCode skill discovery and
  frontmatter guidance.

- [Rust `Instant`](https://doc.rust-lang.org/std/time/struct.Instant.html) — monotonic elapsed-time
  accounting for total local deadlines.
- [reqwest `ClientBuilder`](https://docs.rs/reqwest/latest/reqwest/struct.ClientBuilder.html) —
  HTTPS-only clients, default headers, redirect policy, total request timeout, connect timeout,
  pooling, and platform caveats.
- [reqwest redirect `Policy`](https://docs.rs/reqwest/latest/reqwest/redirect/struct.Policy.html) —
  disabled redirects and the requirement for custom policies to enforce their own hop limit.
- [reqwest `Error`](https://docs.rs/reqwest/latest/reqwest/struct.Error.html) — decode
  classification and removal of potentially sensitive URL context.
- [reqwest `Url`](https://docs.rs/reqwest/latest/reqwest/struct.Url.html) — typed parsing and path
  joining through the re-exported URL type.
- [reqwest `Response`](https://docs.rs/reqwest/latest/reqwest/struct.Response.html) — streaming body
  access used to enforce diagnostic byte limits and JSON decode/schema error behavior.
- [tonic `Endpoint`](https://docs.rs/tonic/latest/tonic/transport/struct.Endpoint.html) — channel
  reuse and distinction between connection and local request timeouts.
- [tonic `Request::set_timeout`](https://docs.rs/tonic/latest/tonic/struct.Request.html#method.set_timeout)
  — `grpc-timeout` metadata visible to the server.
- [SQLx `PoolOptions`](https://docs.rs/sqlx/latest/sqlx/pool/struct.PoolOptions.html) — maximum
  connections and the need to account for database and peer-application limits.
- [Tokio time](https://docs.rs/tokio/latest/tokio/time/) — timeout cancellation behavior and
  deadline primitives.
- [HTTP Semantics: idempotent methods](https://www.rfc-editor.org/rfc/rfc9110.html#name-idempotent-methods)
  — protocol-level retry safety.
- [HTTP Semantics: Retry-After](https://www.rfc-editor.org/rfc/rfc9110.html#field.retry-after) —
  server retry guidance.
- [OAuth 2.0 Bearer Token Usage](https://www.rfc-editor.org/rfc/rfc6750.html#section-2) — TLS is
  mandatory for bearer-token use.
- [URL Standard](https://url.spec.whatwg.org/) — parsing, credentials, and hierarchical URL
  behavior.
