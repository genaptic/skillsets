//! Adaptable rustdoc examples. Replace `my_crate` with the actual crate name.

/// Parse a user identifier.
///
/// # Examples
///
/// ```
/// # use my_crate::parse_user_id;
/// assert_eq!(parse_user_id("42"), Ok(42));
/// ```
///
/// External I/O examples should compile without running by default:
///
/// ```no_run
/// # async fn example() -> Result<(), Box<dyn std::error::Error>> {
/// let response = reqwest::get("https://example.test/").await?;
/// assert!(response.status().is_success());
/// # Ok(())
/// # }
/// ```
pub fn parse_user_id(input: &str) -> Result<u64, std::num::ParseIntError> {
    input.parse()
}
