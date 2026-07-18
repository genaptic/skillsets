include!(concat!(
    env!("CARGO_MANIFEST_DIR"),
    "/../../packs/rust/best-practices/skills/rust-async-concurrency/assets/templates/bounded_fanout.rs"
));

#[cfg(test)]
mod tests {
    use std::{
        future::pending,
        num::NonZeroUsize,
        sync::{
            Arc,
            atomic::{AtomicUsize, Ordering},
        },
        time::Duration,
    };

    use tokio_util::sync::CancellationToken;

    use super::{Client, FetchError, Record, fetch_bounded_ordered, fetch_bounded_ordered_with};

    struct ActiveGuard(Arc<AtomicUsize>);

    impl Drop for ActiveGuard {
        fn drop(&mut self) {
            self.0.fetch_sub(1, Ordering::SeqCst);
        }
    }

    #[tokio::test]
    async fn bounded_fanout_preserves_input_order() {
        let records = fetch_bounded_ordered(
            Client,
            vec![9, 2, 7, 1],
            NonZeroUsize::new(2).expect("non-zero"),
            CancellationToken::new(),
        )
        .await
        .expect("fan-out succeeds");
        assert_eq!(
            records
                .into_iter()
                .map(|record| record.id)
                .collect::<Vec<_>>(),
            [9, 2, 7, 1]
        );
    }

    #[tokio::test(start_paused = true)]
    async fn inverse_completion_stays_ordered_and_never_exceeds_the_bound() {
        let active = Arc::new(AtomicUsize::new(0));
        let maximum = Arc::new(AtomicUsize::new(0));
        let fetch = {
            let active = active.clone();
            let maximum = maximum.clone();
            move |id: u64| {
                let active = active.clone();
                let maximum = maximum.clone();
                async move {
                    let current = active.fetch_add(1, Ordering::SeqCst) + 1;
                    maximum.fetch_max(current, Ordering::SeqCst);
                    let _guard = ActiveGuard(active);
                    tokio::time::sleep(Duration::from_millis((5 - id) * 10)).await;
                    Ok(Record { id })
                }
            }
        };
        let records = fetch_bounded_ordered_with(
            vec![1, 2, 3, 4],
            NonZeroUsize::new(2).expect("non-zero"),
            CancellationToken::new(),
            fetch,
        )
        .await
        .expect("fan-out succeeds");
        assert_eq!(
            records
                .into_iter()
                .map(|record| record.id)
                .collect::<Vec<_>>(),
            [1, 2, 3, 4]
        );
        assert_eq!(maximum.load(Ordering::SeqCst), 2);
        assert_eq!(active.load(Ordering::SeqCst), 0);
    }

    #[tokio::test]
    async fn cancellation_drops_every_in_flight_operation() {
        let active = Arc::new(AtomicUsize::new(0));
        let cancellation = CancellationToken::new();
        let fetch = {
            let active = active.clone();
            move |id: u64| {
                let active = active.clone();
                async move {
                    active.fetch_add(1, Ordering::SeqCst);
                    let _guard = ActiveGuard(active);
                    pending::<()>().await;
                    Ok(Record { id })
                }
            }
        };
        let task = tokio::spawn(fetch_bounded_ordered_with(
            vec![1, 2, 3],
            NonZeroUsize::new(2).expect("non-zero"),
            cancellation.clone(),
            fetch,
        ));
        while active.load(Ordering::SeqCst) != 2 {
            tokio::task::yield_now().await;
        }
        cancellation.cancel();
        assert!(matches!(
            task.await.expect("task joins"),
            Err(FetchError::Cancelled)
        ));
        assert_eq!(active.load(Ordering::SeqCst), 0);
    }

    #[tokio::test]
    async fn pre_cancelled_fanout_starts_no_operations() {
        let started = Arc::new(AtomicUsize::new(0));
        let cancellation = CancellationToken::new();
        cancellation.cancel();
        let fetch = {
            let started = started.clone();
            move |id: u64| {
                let started = started.clone();
                async move {
                    started.fetch_add(1, Ordering::SeqCst);
                    Ok(Record { id })
                }
            }
        };

        let result = fetch_bounded_ordered_with(
            vec![1, 2, 3],
            NonZeroUsize::new(2).expect("non-zero"),
            cancellation,
            fetch,
        )
        .await;

        assert!(matches!(result, Err(FetchError::Cancelled)));
        assert_eq!(started.load(Ordering::SeqCst), 0);
    }
}
