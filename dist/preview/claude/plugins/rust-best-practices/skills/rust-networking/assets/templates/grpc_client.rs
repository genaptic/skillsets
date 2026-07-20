//! Adaptable tonic client showing distinct connection and request deadline layers.

use std::time::Duration;

use tonic::{Request, Status, transport::Channel};

#[derive(Clone)]
struct PaymentsClient {
    channel: Channel,
    request_timeout: Duration,
}

impl PaymentsClient {
    fn new(endpoint: tonic::transport::Endpoint, request_timeout: Duration) -> Self {
        let channel = endpoint
            .connect_timeout(Duration::from_secs(3))
            .timeout(request_timeout)
            .connect_lazy();
        Self {
            channel,
            request_timeout,
        }
    }

    async fn capture(&self, message: CaptureRequest) -> Result<CaptureResponse, Status> {
        let mut request = Request::new(message);
        // This sends grpc-timeout metadata; Endpoint::timeout only enforces a local timeout.
        request.set_timeout(self.request_timeout);

        let mut generated = GeneratedPaymentsClient::new(self.channel.clone());
        generated.capture(request).await
    }
}

struct CaptureRequest;
struct CaptureResponse;

struct GeneratedPaymentsClient {
    channel: Channel,
}

impl GeneratedPaymentsClient {
    fn new(channel: Channel) -> Self {
        Self { channel }
    }

    async fn capture(
        &mut self,
        _request: Request<CaptureRequest>,
    ) -> Result<CaptureResponse, Status> {
        let _ = &self.channel;
        Ok(CaptureResponse)
    }
}
