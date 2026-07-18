include!(concat!(
    env!("CARGO_MANIFEST_DIR"),
    "/../../packs/rust/best-practices/skills/rust-networking/assets/templates/sqlx_pool.rs"
));

#[cfg(test)]
mod tests {
    use std::num::NonZeroU32;

    use super::{PoolBudget, PoolConfigError};

    #[test]
    fn pool_budget_rejects_overcommitment_and_zero_per_replica() {
        let overcommitted = PoolBudget {
            database_limit: NonZeroU32::new(10).expect("non-zero"),
            reserved_connections: 8,
            other_application_connections: 3,
            maximum_replicas: NonZeroU32::new(2).expect("non-zero"),
        };
        assert!(matches!(
            overcommitted.per_replica(),
            Err(PoolConfigError::Overcommitted)
        ));

        let rounded_to_zero = PoolBudget {
            database_limit: NonZeroU32::new(2).expect("non-zero"),
            reserved_connections: 0,
            other_application_connections: 0,
            maximum_replicas: NonZeroU32::new(3).expect("non-zero"),
        };
        assert!(matches!(
            rounded_to_zero.per_replica(),
            Err(PoolConfigError::Overcommitted)
        ));
    }
}
