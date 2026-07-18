include!(concat!(
    env!("CARGO_MANIFEST_DIR"),
    "/../../packs/rust/best-practices/skills/rust-async-concurrency/assets/templates/sync_worker_bridge.rs"
));

#[cfg(test)]
mod tests {
    use std::{
        num::NonZeroUsize,
        sync::{
            Arc,
            atomic::{AtomicBool, Ordering},
            mpsc,
        },
        thread,
        time::Duration,
    };

    use super::{WorkerHandle, join_worker_thread};

    #[test]
    fn zero_capacity_is_rejected_by_the_input_type() {
        assert!(NonZeroUsize::new(0).is_none());
    }

    #[tokio::test]
    async fn worker_round_trip_and_shutdown_complete_without_blocking_the_runtime() {
        let worker = WorkerHandle::start(
            NonZeroUsize::new(2).expect("non-zero"),
            Duration::from_secs(1),
            Duration::from_secs(1),
        );
        worker
            .write("key".to_owned(), "value".to_owned())
            .await
            .expect("write succeeds");
        assert_eq!(
            worker.read("key".to_owned()).await.expect("read succeeds"),
            Some("value".to_owned())
        );
        tokio::time::timeout(Duration::from_secs(1), worker.shutdown())
            .await
            .expect("shutdown does not block the executor")
            .expect("shutdown succeeds");
    }

    #[tokio::test(flavor = "current_thread")]
    async fn delayed_thread_join_allows_a_tokio_heartbeat_to_progress() {
        let (heartbeat_sender, heartbeat_receiver) = mpsc::sync_channel(1);
        let heartbeat_received = Arc::new(AtomicBool::new(false));
        let worker_received = heartbeat_received.clone();
        let thread = thread::spawn(move || {
            if heartbeat_receiver
                .recv_timeout(Duration::from_millis(500))
                .is_ok()
            {
                worker_received.store(true, Ordering::SeqCst);
            }
        });

        let join = join_worker_thread(thread);
        let heartbeat = async move {
            tokio::time::sleep(Duration::from_millis(10)).await;
            heartbeat_sender.send(()).expect("send heartbeat");
        };
        let (join_result, ()) = tokio::join!(join, heartbeat);

        join_result.expect("worker joins");
        assert!(heartbeat_received.load(Ordering::SeqCst));
    }
}
