include!(concat!(
    env!("CARGO_MANIFEST_DIR"),
    "/../../packs/rust/best-practices/skills/rust-async-concurrency/assets/templates/graceful_shutdown.rs"
));

#[cfg(test)]
mod tests {
    use std::{future::pending, time::Duration};

    use tokio_util::{sync::CancellationToken, task::TaskTracker};

    use super::{ShutdownError, cancel_and_wait_for_tasks, run_service};

    #[tokio::test(start_paused = true)]
    async fn cooperative_workers_finish_before_the_deadline() {
        run_service(Duration::from_secs(1))
            .await
            .expect("cooperative shutdown succeeds");
    }

    #[tokio::test]
    async fn an_open_tracker_is_rejected_before_cancellation() {
        let tracker = TaskTracker::new();
        let cancellation = CancellationToken::new();
        assert!(matches!(
            cancel_and_wait_for_tasks(&tracker, &cancellation, Duration::from_millis(1)).await,
            Err(ShutdownError::TrackerOpen)
        ));
        assert!(!cancellation.is_cancelled());
    }

    #[tokio::test(start_paused = true)]
    async fn a_post_close_spawn_is_tracked_and_reported_at_timeout() {
        let tracker = TaskTracker::new();
        tracker.close();
        let task = tracker.spawn(pending::<()>());
        let cancellation = CancellationToken::new();
        let error = cancel_and_wait_for_tasks(&tracker, &cancellation, Duration::from_secs(1))
            .await
            .expect_err("stuck task exceeds deadline");
        assert!(matches!(
            error,
            ShutdownError::DeadlineExceeded { remaining_tasks: 1 }
        ));
        assert!(cancellation.is_cancelled());
        task.abort();
        tracker.wait().await;
    }
}
