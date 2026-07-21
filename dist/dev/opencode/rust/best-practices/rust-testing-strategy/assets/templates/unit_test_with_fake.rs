//! Adaptable unit-test snippet using an owned collaborator fake.

trait Clock {
    fn unix_seconds(&self) -> u64;
}

struct SessionService<C> {
    clock: C,
}

impl<C: Clock> SessionService<C> {
    fn new(clock: C) -> Self {
        Self { clock }
    }

    fn issue_expiry(&self, ttl_seconds: u64) -> Option<u64> {
        self.clock.unix_seconds().checked_add(ttl_seconds)
    }
}

#[cfg(test)]
mod tests {
    use super::{Clock, SessionService};

    #[derive(Clone, Copy)]
    struct FakeClock {
        now: u64,
    }

    impl Clock for FakeClock {
        fn unix_seconds(&self) -> u64 {
            self.now
        }
    }

    #[test]
    fn computes_expiry_from_injected_clock() {
        let service = SessionService::new(FakeClock { now: 1_700_000_000 });
        assert_eq!(service.issue_expiry(300), Some(1_700_000_300));
    }

    #[test]
    fn reports_overflow() {
        let service = SessionService::new(FakeClock { now: u64::MAX });
        assert_eq!(service.issue_expiry(1), None);
    }
}
