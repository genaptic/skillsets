// Adaptable graceful-shutdown snippet: detect, stop producers, signal, close, and wait.

use std::time::Duration;

use tokio_util::{sync::CancellationToken, task::TaskTracker};

#[derive(Debug)]
enum ShutdownError {
    TrackerOpen,
    DeadlineExceeded { remaining_tasks: usize },
}

async fn run_service(shutdown_deadline: Duration) -> Result<(), ShutdownError> {
    let cancellation = CancellationToken::new();
    let tracker = TaskTracker::new();

    for worker_id in 0..4 {
        tracker.spawn(run_worker(worker_id, cancellation.child_token()));
    }

    // Registration has ended in this finite example. `TaskTracker::close` does not reject later
    // spawns; it only allows a future `wait` to complete once the tracker is empty.
    tracker.close();

    wait_for_shutdown_request().await;

    // A dynamic service instead stops and awaits every listener, producer, or supervisor that can
    // call `tracker.spawn`, then closes the tracker before it waits.
    cancel_and_wait_for_tasks(&tracker, &cancellation, shutdown_deadline).await
}

async fn cancel_and_wait_for_tasks(
    tracker: &TaskTracker,
    cancellation: &CancellationToken,
    shutdown_deadline: Duration,
) -> Result<(), ShutdownError> {
    if !tracker.is_closed() {
        return Err(ShutdownError::TrackerOpen);
    }

    cancellation.cancel();
    if tokio::time::timeout(shutdown_deadline, tracker.wait())
        .await
        .is_err()
    {
        // The timeout drops only the wait future. It does not abort tracked tasks. The process
        // owner must now apply its documented escalation policy and report unresolved cleanup.
        return Err(ShutdownError::DeadlineExceeded {
            remaining_tasks: tracker.len(),
        });
    }
    Ok(())
}

async fn wait_for_shutdown_request() {
    // Replace with the repository-authorized signal or service shutdown source.
}

async fn run_worker(_worker_id: usize, cancellation: CancellationToken) {
    cancellation.cancelled().await;
    // Perform bounded cleanup here.
}
