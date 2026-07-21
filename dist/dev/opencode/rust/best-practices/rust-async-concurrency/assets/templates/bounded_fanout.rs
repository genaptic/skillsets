// Adaptable bounded fan-out snippet. It preserves input order after concurrent completion.

use std::{future::Future, num::NonZeroUsize};

use futures::{StreamExt, TryStreamExt, stream};
use tokio_util::sync::CancellationToken;

#[derive(Clone)]
struct Client;

#[derive(Debug)]
struct Record {
    id: u64,
}

#[derive(Debug)]
enum FetchError {
    Cancelled,
    Transport,
}

impl Client {
    async fn fetch(&self, id: u64) -> Result<Record, FetchError> {
        let _ = self;
        Ok(Record { id })
    }
}

async fn fetch_bounded_ordered(
    client: Client,
    ids: Vec<u64>,
    concurrency: NonZeroUsize,
    cancellation: CancellationToken,
) -> Result<Vec<Record>, FetchError> {
    fetch_bounded_ordered_with(ids, concurrency, cancellation, move |id| {
        let client = client.clone();
        async move { client.fetch(id).await }
    })
    .await
}

async fn fetch_bounded_ordered_with<F, Fut>(
    ids: Vec<u64>,
    concurrency: NonZeroUsize,
    cancellation: CancellationToken,
    fetch: F,
) -> Result<Vec<Record>, FetchError>
where
    F: Fn(u64) -> Fut + Clone,
    Fut: Future<Output = Result<Record, FetchError>>,
{
    let mut indexed = stream::iter(ids.into_iter().enumerate())
        .map(|(index, id)| {
            let cancellation = cancellation.clone();
            let fetch = fetch.clone();
            async move {
                tokio::select! {
                    biased;
                    _ = cancellation.cancelled() => Err(FetchError::Cancelled),
                    result = fetch(id) => result.map(|record| (index, record)),
                }
            }
        })
        .buffer_unordered(concurrency.get())
        .try_collect::<Vec<_>>()
        .await?;

    indexed.sort_unstable_by_key(|(index, _)| *index);
    Ok(indexed.into_iter().map(|(_, record)| record).collect())
}
