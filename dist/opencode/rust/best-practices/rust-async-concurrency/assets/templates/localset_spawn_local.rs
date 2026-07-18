//! Adaptable `LocalSet` snippet for intentionally non-`Send` state.

use std::{cell::RefCell, rc::Rc};

use tokio::task::LocalSet;

async fn run_local_tasks() -> Result<u64, tokio::task::JoinError> {
    let local = LocalSet::new();
    let total = Rc::new(RefCell::new(0_u64));

    local
        .run_until(async move {
            let total_for_task = Rc::clone(&total);
            let handle = tokio::task::spawn_local(async move {
                *total_for_task.borrow_mut() += 1;
            });
            handle.await?;
            Ok(*total.borrow())
        })
        .await
}
