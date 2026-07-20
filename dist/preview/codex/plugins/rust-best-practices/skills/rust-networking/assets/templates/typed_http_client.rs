// Adaptable bearer-authenticated HTTPS client with typed and bounded error handling.

use std::{fmt, time::Duration};

use futures_util::StreamExt;
use reqwest::{Client, Response, StatusCode, Url, header, redirect};

const MAX_ERROR_BYTES: usize = 4 * 1024;

#[derive(Clone)]
struct OrdersClient {
    base_url: Url,
    http: Client,
}

#[derive(Debug, serde::Deserialize)]
struct OrderDto {
    id: u64,
    status: String,
}

#[derive(Debug)]
enum ClientError {
    InvalidBaseUrl,
    InvalidAuthorizationHeader,
    Build(reqwest::Error),
    Transport(reqwest::Error),
    Decode(reqwest::Error),
    HttpStatus {
        status: StatusCode,
        summary: String,
        truncated: bool,
    },
}

impl OrdersClient {
    fn new(base_url: Url, bearer_token: &str) -> Result<Self, ClientError> {
        validate_base_url(&base_url)?;

        let mut authorization = header::HeaderValue::from_str(&format!("Bearer {bearer_token}"))
            .map_err(|_| ClientError::InvalidAuthorizationHeader)?;
        authorization.set_sensitive(true);
        let mut headers = header::HeaderMap::new();
        headers.insert(header::AUTHORIZATION, authorization);

        let http = Client::builder()
            .default_headers(headers)
            .https_only(true)
            .redirect(redirect_policy())
            .connect_timeout(Duration::from_secs(3))
            .timeout(Duration::from_secs(10))
            .build()
            .map_err(|error| ClientError::Build(error.without_url()))?;

        Ok(Self { base_url, http })
    }

    async fn get_order(&self, id: u64) -> Result<OrderDto, ClientError> {
        let url = self
            .base_url
            .join(&format!("orders/{id}"))
            .map_err(|_| ClientError::InvalidBaseUrl)?;
        let response = self
            .http
            .get(url)
            .send()
            .await
            .map_err(classify_transport_error)?;

        if response.status().is_success() {
            decode_json(response).await
        } else {
            let status = response.status();
            let (summary, truncated) = bounded_error_summary(response, MAX_ERROR_BYTES).await?;
            Err(ClientError::HttpStatus {
                status,
                summary,
                truncated,
            })
        }
    }
}

fn redirect_policy() -> redirect::Policy {
    redirect::Policy::none()
}

fn validate_base_url(url: &Url) -> Result<(), ClientError> {
    let valid = url.scheme() == "https"
        && url.has_host()
        && url.username().is_empty()
        && url.password().is_none()
        && url.query().is_none()
        && url.fragment().is_none()
        && !url.cannot_be_a_base()
        && url.path().ends_with('/');
    valid.then_some(()).ok_or(ClientError::InvalidBaseUrl)
}

fn classify_transport_error(error: reqwest::Error) -> ClientError {
    ClientError::Transport(error.without_url())
}

fn classify_response_error(error: reqwest::Error) -> ClientError {
    let is_decode = error.is_decode();
    let error = error.without_url();
    if is_decode {
        ClientError::Decode(error)
    } else {
        ClientError::Transport(error)
    }
}

async fn decode_json<T>(response: Response) -> Result<T, ClientError>
where
    T: serde::de::DeserializeOwned,
{
    response.json().await.map_err(classify_response_error)
}

async fn bounded_error_summary(
    response: Response,
    limit: usize,
) -> Result<(String, bool), ClientError> {
    let mut bytes = Vec::with_capacity(limit.min(1024));
    let mut stream = response.bytes_stream();
    let mut truncated = false;

    while let Some(chunk) = stream.next().await {
        let chunk = chunk.map_err(classify_transport_error)?;
        let remaining = limit.saturating_sub(bytes.len());
        if chunk.len() > remaining {
            bytes.extend_from_slice(&chunk[..remaining]);
            truncated = true;
            break;
        }
        bytes.extend_from_slice(&chunk);
        if bytes.len() == limit {
            truncated = match stream.next().await {
                Some(Ok(_)) => true,
                Some(Err(error)) => return Err(classify_transport_error(error)),
                None => false,
            };
            break;
        }
    }

    let text = String::from_utf8_lossy(&bytes);
    Ok((redact_diagnostic(&text), truncated))
}

fn redact_diagnostic(text: &str) -> String {
    // Replace with the repository's structured redaction policy. This safe default does not
    // expose an untrusted body.
    if text.is_empty() {
        "remote service returned no diagnostic text".to_owned()
    } else {
        "remote service returned a bounded diagnostic body (redacted)".to_owned()
    }
}

impl fmt::Display for ClientError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::InvalidBaseUrl => write!(formatter, "invalid HTTPS API base URL"),
            Self::InvalidAuthorizationHeader => write!(formatter, "invalid authorization header"),
            Self::Build(error) => write!(formatter, "failed to build HTTP client: {error}"),
            Self::Transport(error) => write!(formatter, "HTTP transport failed: {error}"),
            Self::Decode(error) => write!(formatter, "HTTP response decoding failed: {error}"),
            Self::HttpStatus {
                status,
                summary,
                truncated,
            } => write!(
                formatter,
                "HTTP status {status}: {summary}; diagnostic_truncated={truncated}"
            ),
        }
    }
}

impl std::error::Error for ClientError {
    fn source(&self) -> Option<&(dyn std::error::Error + 'static)> {
        match self {
            Self::Build(error) | Self::Transport(error) | Self::Decode(error) => Some(error),
            Self::InvalidBaseUrl | Self::InvalidAuthorizationHeader | Self::HttpStatus { .. } => {
                None
            }
        }
    }
}
