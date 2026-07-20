# Worked Rust type-model examples

These examples are adaptable. Reconcile naming, errors, serialization, and compatibility with the
target repository.

## Contents

- [Replace pseudo-variants](#replace-pseudo-variants)
- [Split a mixed-lifecycle struct](#split-a-mixed-lifecycle-struct)
- [Group repeated parameters](#group-repeated-parameters)
- [Choose methods and free functions](#choose-methods-and-free-functions)
- [Choose aliases and newtypes](#choose-aliases-and-newtypes)

## Replace pseudo-variants

This representation permits contradictory or incomplete combinations:

```rust
pub struct Message {
    pub kind: String,
    pub text: Option<String>,
    pub tool_name: Option<String>,
    pub arguments: Option<Vec<String>>,
    pub error: Option<String>,
}
```

If the set is controlled by the application, encode each case's required data:

```rust
pub enum Message {
    UserText(String),
    AssistantText(String),
    ToolCall {
        name: String,
        arguments: Vec<String>,
    },
    Failure {
        summary: String,
    },
}

impl Message {
    pub fn summary(&self) -> &str {
        match self {
            Self::UserText(text) | Self::AssistantText(text) => text,
            Self::ToolCall { name, .. } => name,
            Self::Failure { summary } => summary,
        }
    }
}
```

For an externally extensible protocol, retain an unknown/raw variant or use a separate wire type so
new server values can be preserved rather than rejected.

## Split a mixed-lifecycle struct

This type mixes immutable configuration, request input, and runtime state:

```rust
pub struct Runner {
    pub endpoint: String,
    pub retry_limit: u32,
    pub prompt: String,
    pub step_count: u32,
    pub last_error: Option<String>,
}
```

Separate values that have different owners and mutation rules:

```rust
pub struct RunnerConfig {
    endpoint: String,
    retry_limit: u32,
}

pub struct RunRequest {
    prompt: String,
}

pub struct RunState {
    step_count: u32,
    outcome: RunOutcome,
}

pub enum RunOutcome {
    Running,
    Complete { output: String },
    Failed { message: String },
}
```

This split is useful only if the lifecycles truly differ. If every field always moves and changes
together, one cohesive struct can be clearer.

## Group repeated parameters

Repeated positional primitives obscure meaning:

```rust
pub fn connect(host: &str, port: u16, tls: bool, timeout_ms: u64) {
    // Adapt to the target transport.
}
```

Name the configured concept and replace mode flags when there are meaningful cases:

```rust
pub enum TransportSecurity {
    Plaintext,
    Tls,
}

pub struct ConnectionOptions {
    pub host: String,
    pub port: u16,
    pub security: TransportSecurity,
    pub timeout: std::time::Duration,
}

impl ConnectionOptions {
    pub fn authority(&self) -> String {
        format!("{}:{}", self.host, self.port)
    }
}
```

Do not add an options type for one local call with obvious arguments unless it improves an actual
invariant, call-site clarity, or future-compatible public API.

## Choose methods and free functions

A receiver clearly owns this behavior:

```rust
pub struct TemperatureCelsius(f64);

impl TemperatureCelsius {
    pub fn is_freezing(&self) -> bool {
        self.0 <= 0.0
    }
}
```

A symmetric operation does not have one privileged receiver:

```rust
pub fn distance(left: Point, right: Point) -> f64 {
    let x = left.x - right.x;
    let y = left.y - right.y;
    x.hypot(y)
}

#[derive(Debug, Clone, Copy)]
pub struct Point {
    pub x: f64,
    pub y: f64,
}
```

Either shape can be valid for an algorithm depending on API discoverability and repository
conventions. Avoid creating a service object with no state only to eliminate a free function.

## Choose aliases and newtypes

A readable transparent collection alias:

```rust
pub type Labels = std::collections::BTreeMap<String, String>;
```

An identifier needs a distinct type and validation:

```rust
#[derive(Debug, Clone, PartialEq, Eq, Hash)]
pub struct AccountId(String);

impl std::str::FromStr for AccountId {
    type Err = AccountIdError;

    fn from_str(value: &str) -> Result<Self, Self::Err> {
        let value = value.trim();
        if value.is_empty() {
            return Err(AccountIdError::Empty);
        }
        Ok(Self(value.to_owned()))
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum AccountIdError {
    Empty,
}
```

The alias deliberately preserves assignability with its underlying map. The newtype deliberately
prevents arbitrary strings from silently becoming account identifiers.
