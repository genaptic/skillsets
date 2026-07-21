# Async concurrency sources

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

- [Tokio graceful shutdown](https://tokio.rs/tokio/topics/shutdown) — cancellation tokens and
  waiting for tracked tasks.
- [Tokio task module](https://docs.rs/tokio/latest/tokio/task/) — spawning, blocking boundaries,
  abort behavior, and local tasks.
- [Tokio `JoinSet`](https://docs.rs/tokio/latest/tokio/task/struct.JoinSet.html) — dynamically
  owned task sets and join behavior.
- [Tokio `select!`](https://docs.rs/tokio/latest/tokio/macro.select.html) — branch lifecycle and
  cancellation-safety requirements.
- [Tokio time pause](https://docs.rs/tokio/latest/tokio/time/fn.pause.html) — current-thread
  requirement, `start_paused`, and auto-advance behavior.
- [Tokio mutex](https://docs.rs/tokio/latest/tokio/sync/struct.Mutex.html) — async mutex tradeoffs
  and the recommendation to use a standard mutex for simple data when appropriate.
- [Tokio `spawn_blocking`](https://docs.rs/tokio/latest/tokio/task/fn.spawn_blocking.html) — finite
  blocking work, cancellation limitations, and runtime shutdown behavior.
- [Tokio-util `CancellationToken`](https://docs.rs/tokio-util/latest/tokio_util/sync/struct.CancellationToken.html)
  — cooperative cancellation semantics.
- [Tokio-util `TaskTracker`](https://docs.rs/tokio-util/latest/tokio_util/task/struct.TaskTracker.html)
  — `close`/`wait` semantics, continued spawning after close, and task tracking behind the
  `tokio-util` `rt` feature.
- [Futures `StreamExt`](https://docs.rs/futures/latest/futures/stream/trait.StreamExt.html) — bounded
  unordered buffering.
- [Async Book](https://rust-lang.github.io/async-book/) — language-level async model.
- [Rust Reference: dyn compatibility](https://doc.rust-lang.org/reference/items/traits.html#dyn-compatibility)
  — trait-object constraints for async methods.
