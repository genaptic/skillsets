// Adaptable SQLx pool budget calculation for a replicated deployment.

use std::{num::NonZeroU32, time::Duration};

use sqlx::{PgPool, postgres::PgPoolOptions};

#[derive(Clone, Copy)]
struct PoolBudget {
    database_limit: NonZeroU32,
    reserved_connections: u32,
    other_application_connections: u32,
    maximum_replicas: NonZeroU32,
}

#[derive(Debug)]
enum PoolConfigError {
    Overcommitted,
    Connect(sqlx::Error),
}

impl PoolBudget {
    fn per_replica(self) -> Result<NonZeroU32, PoolConfigError> {
        let available = self
            .database_limit
            .get()
            .checked_sub(self.reserved_connections)
            .and_then(|value| value.checked_sub(self.other_application_connections))
            .ok_or(PoolConfigError::Overcommitted)?;
        NonZeroU32::new(available / self.maximum_replicas.get())
            .ok_or(PoolConfigError::Overcommitted)
    }
}

async fn connect_pool(database_url: &str, budget: PoolBudget) -> Result<PgPool, PoolConfigError> {
    PgPoolOptions::new()
        .max_connections(budget.per_replica()?.get())
        .acquire_timeout(Duration::from_secs(3))
        .connect(database_url)
        .await
        .map_err(PoolConfigError::Connect)
}
