// Adaptable bridge for one long-lived synchronous resource.
//
// Admission is bounded. Reads may time out while waiting for a reply. Writes wait for a
// definitive result because a timeout after admission could misrepresent a committed effect.

use std::{
    num::NonZeroUsize,
    thread::{self, JoinHandle},
    time::Duration,
};

use tokio::{sync::mpsc, task, time};

struct WorkerHandle {
    sender: mpsc::Sender<Command>,
    thread: Option<JoinHandle<()>>,
    admission_timeout: Duration,
    read_timeout: Duration,
}

enum Command {
    Read {
        key: String,
        reply: std::sync::mpsc::SyncSender<Result<Option<String>, WorkerError>>,
    },
    Write {
        key: String,
        value: String,
        reply: std::sync::mpsc::SyncSender<Result<(), WorkerError>>,
    },
    Shutdown,
}

#[derive(Debug)]
enum WorkerError {
    AdmissionTimeout,
    ReadTimeout,
    WorkerExited,
    WorkerPanicked,
}

impl WorkerHandle {
    fn start(capacity: NonZeroUsize, admission_timeout: Duration, read_timeout: Duration) -> Self {
        let (sender, mut receiver) = mpsc::channel(capacity.get());
        let thread = thread::spawn(move || {
            let mut engine = std::collections::HashMap::<String, String>::new();
            while let Some(command) = receiver.blocking_recv() {
                match command {
                    Command::Read { key, reply } => {
                        let _ = reply.send(Ok(engine.get(&key).cloned()));
                    }
                    Command::Write { key, value, reply } => {
                        engine.insert(key, value);
                        let _ = reply.send(Ok(()));
                    }
                    Command::Shutdown => break,
                }
            }
        });

        Self {
            sender,
            thread: Some(thread),
            admission_timeout,
            read_timeout,
        }
    }

    async fn read(&self, key: String) -> Result<Option<String>, WorkerError> {
        let (reply, response) = std::sync::mpsc::sync_channel(1);
        self.admit(Command::Read { key, reply }).await?;
        let read_timeout = self.read_timeout;

        task::spawn_blocking(move || response.recv_timeout(read_timeout))
            .await
            .map_err(|_| WorkerError::WorkerPanicked)?
            .map_err(|error| match error {
                std::sync::mpsc::RecvTimeoutError::Timeout => WorkerError::ReadTimeout,
                std::sync::mpsc::RecvTimeoutError::Disconnected => WorkerError::WorkerExited,
            })?
    }

    async fn write(&self, key: String, value: String) -> Result<(), WorkerError> {
        let (reply, response) = std::sync::mpsc::sync_channel(1);
        self.admit(Command::Write { key, value, reply }).await?;

        task::spawn_blocking(move || response.recv())
            .await
            .map_err(|_| WorkerError::WorkerPanicked)?
            .map_err(|_| WorkerError::WorkerExited)?
    }

    async fn admit(&self, command: Command) -> Result<(), WorkerError> {
        let permit = time::timeout(self.admission_timeout, self.sender.reserve())
            .await
            .map_err(|_| WorkerError::AdmissionTimeout)?
            .map_err(|_| WorkerError::WorkerExited)?;
        permit.send(command);
        Ok(())
    }

    async fn shutdown(mut self) -> Result<(), WorkerError> {
        let shutdown_request = self.admit(Command::Shutdown).await;
        drop(self.sender);
        let thread = self.thread.take().ok_or(WorkerError::WorkerExited)?;
        let thread_result = join_worker_thread(thread).await;
        shutdown_request?;
        thread_result
    }
}

async fn join_worker_thread(thread: JoinHandle<()>) -> Result<(), WorkerError> {
    task::spawn_blocking(move || thread.join())
        .await
        .map_err(|_| WorkerError::WorkerPanicked)?
        .map_err(|_| WorkerError::WorkerPanicked)
}
