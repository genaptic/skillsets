# gRPC and database boundaries

## Tonic deadlines

- `Endpoint::connect_timeout` bounds establishing a transport connection.
- `Endpoint::timeout` applies a local timeout to each request.
- `Request::set_timeout` encodes `grpc-timeout` so the server can observe the deadline.

Do not treat these as interchangeable. Derive all three from one operation budget where they are
needed. Reuse a channel and clone generated clients cheaply; do not reconnect per request.

Classify `tonic::Status` codes according to the specific RPC. A code that is retryable for a pure
lookup may be unsafe for a write. Streaming RPCs also need application-level message and buffer
limits.

## SQL/database pool budgets

Budget across the whole deployment, not one process. Reserve capacity for administration and
migrations, subtract other application consumers, divide by worst-case replicas, and account for
multiple pools per instance. Reject zero or overcommitted results.

Pool acquisition belongs inside the caller's total deadline. A pool timeout indicates local
contention, not a database query timeout. Configure query/statement timeouts through the database
and driver policy separately.

Do not run live queries or start a database merely to validate configuration. Unit-test arithmetic
and options offline; run integration tests only with explicit authorization, isolation, bounded
credentials, and cleanup.
