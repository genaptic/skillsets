include!(concat!(
    env!("CARGO_MANIFEST_DIR"),
    "/../../packs/rust/best-practices/skills/rust-networking/assets/templates/typed_http_client.rs"
));

#[cfg(test)]
mod tests {
    use std::{
        io::{self, Read, Write},
        net::TcpListener,
        sync::mpsc,
        thread,
        time::{Duration, Instant},
    };

    use futures_util::stream;
    use reqwest::{Body, Response, StatusCode, Url};

    use super::{
        ClientError, OrderDto, OrdersClient, bounded_error_summary, classify_transport_error,
        decode_json, redirect_policy, validate_base_url,
    };

    #[test]
    fn base_url_rejects_ambiguous_or_credential_bearing_forms() {
        for invalid in [
            "http://example.com/api/",
            "http://127.0.0.1:9/api/",
            "ftp://example.com/api/",
            "https://user@example.com/api/",
            "https://user:password@example.com/api/",
            "https://example.com/api/?debug=true",
            "https://example.com/api/#fragment",
            "https://example.com/api",
            "data:text/plain,not-a-base-url",
            "file:///api/",
        ] {
            assert!(validate_base_url(&Url::parse(invalid).expect("valid URL syntax")).is_err());
        }
        assert!(
            validate_base_url(&Url::parse("https://example.com:8443/api/v1/").expect("valid URL"))
                .is_ok()
        );
    }

    #[tokio::test]
    async fn production_redirect_policy_does_not_follow_a_loopback_redirect() {
        let destination = TcpListener::bind(("127.0.0.1", 0)).expect("bind destination");
        destination
            .set_nonblocking(true)
            .expect("set destination nonblocking");
        let destination_url = format!(
            "http://{}/must-not-be-requested",
            destination.local_addr().expect("destination address")
        );
        let (destination_result, destination_observation) = mpsc::sync_channel(1);
        let destination_task = thread::spawn(move || {
            let deadline = Instant::now() + Duration::from_millis(250);
            loop {
                match destination.accept() {
                    Ok((mut connection, _)) => {
                        connection
                            .write_all(
                                b"HTTP/1.1 200 OK\r\nContent-Length: 0\r\nConnection: close\r\n\r\n",
                            )
                            .expect("write destination response");
                        destination_result
                            .send(true)
                            .expect("record destination request");
                        return;
                    }
                    Err(error)
                        if error.kind() == io::ErrorKind::WouldBlock
                            && Instant::now() < deadline =>
                    {
                        thread::sleep(Duration::from_millis(1));
                    }
                    Err(error) if error.kind() == io::ErrorKind::WouldBlock => {
                        destination_result
                            .send(false)
                            .expect("record absent destination request");
                        return;
                    }
                    Err(error) => panic!("destination accept failed: {error}"),
                }
            }
        });

        let redirector = TcpListener::bind(("127.0.0.1", 0)).expect("bind redirector");
        let redirector_url = format!(
            "http://{}/start",
            redirector.local_addr().expect("redirector address")
        );
        let redirector_task = thread::spawn(move || {
            let (mut connection, _) = redirector.accept().expect("accept redirect request");
            let mut request = [0_u8; 1024];
            let _ = connection
                .read(&mut request)
                .expect("read redirect request");
            let response = format!(
                "HTTP/1.1 302 Found\r\nLocation: {destination_url}\r\nContent-Length: 0\r\nConnection: close\r\n\r\n"
            );
            connection
                .write_all(response.as_bytes())
                .expect("write redirect response");
        });

        let client = reqwest::Client::builder()
            .redirect(redirect_policy())
            .timeout(Duration::from_secs(2))
            .build()
            .expect("build isolated client");
        let response = client
            .get(redirector_url)
            .send()
            .await
            .expect("receive redirect response");
        let destination_contacted = destination_observation
            .recv_timeout(Duration::from_secs(1))
            .expect("complete bounded destination observation");
        redirector_task.join().expect("redirector joins");
        destination_task.join().expect("destination joins");

        assert_eq!(response.status(), StatusCode::FOUND);
        assert!(!destination_contacted);
    }

    #[tokio::test]
    async fn error_body_is_bounded_and_redacted() {
        let response: Response = http::Response::builder()
            .status(500)
            .body(Body::from("secret-token-that-must-not-escape"))
            .expect("response")
            .into();
        let (summary, truncated) = bounded_error_summary(response, 8)
            .await
            .expect("body read succeeds");
        assert!(truncated);
        assert!(!summary.contains("secret"));
        assert_eq!(
            summary,
            "remote service returned a bounded diagnostic body (redacted)"
        );
    }

    #[tokio::test]
    async fn exact_limit_lookahead_propagates_a_body_stream_error() {
        let body = Body::wrap_stream(stream::iter([
            Ok::<&'static str, io::Error>("12345678"),
            Err(io::Error::other("body stream failed")),
        ]));
        let response: Response = http::Response::builder()
            .status(500)
            .body(body)
            .expect("response")
            .into();
        let error = bounded_error_summary(response, 8)
            .await
            .expect_err("lookahead stream error is propagated");
        match error {
            ClientError::Transport(error) => assert!(error.url().is_none()),
            other => panic!("expected transport error, got {other:?}"),
        }
    }

    #[tokio::test]
    async fn invalid_success_json_is_classified_as_decode_without_body_disclosure() {
        let response: Response = http::Response::builder()
            .status(200)
            .body(Body::from("secret-invalid-json"))
            .expect("response")
            .into();
        let error = decode_json::<OrderDto>(response)
            .await
            .expect_err("invalid JSON is rejected");
        assert!(matches!(error, ClientError::Decode(_)));
        assert!(!error.to_string().contains("secret-invalid-json"));
    }

    #[tokio::test]
    async fn valid_json_decodes_and_wrong_types_are_classified_without_a_url() {
        let valid: Response = http::Response::builder()
            .status(200)
            .body(Body::from(r#"{"id":7,"status":"ready"}"#))
            .expect("response")
            .into();
        let order = decode_json::<OrderDto>(valid)
            .await
            .expect("valid payload decodes");
        assert_eq!(order.id, 7);
        assert_eq!(order.status, "ready");

        let wrong_type: Response = http::Response::builder()
            .status(200)
            .body(Body::from(r#"{"id":"seven","status":"ready"}"#))
            .expect("response")
            .into();
        let error = decode_json::<OrderDto>(wrong_type)
            .await
            .expect_err("wrong field type is rejected");
        match error {
            ClientError::Decode(error) => assert!(error.url().is_none()),
            other => panic!("expected decode error, got {other:?}"),
        }
    }

    #[tokio::test]
    async fn https_only_rejects_http_without_retaining_the_request_url() {
        let client = OrdersClient::new(
            Url::parse("https://example.com/api/").expect("valid base URL"),
            "test-token",
        )
        .expect("client builds");
        let error = client
            .http
            .get("http://127.0.0.1:9/must-not-connect")
            .send()
            .await
            .expect_err("https-only policy rejects HTTP");
        let error = classify_transport_error(error);
        match error {
            ClientError::Transport(error) => assert!(error.url().is_none()),
            other => panic!("expected transport error, got {other:?}"),
        }
    }
}
