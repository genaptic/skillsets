#![forbid(unsafe_code)]

/// Return a normalized greeting for a non-empty name.
pub fn greeting(name: &str) -> Result<String, GreetingError> {
    let name = name.trim();
    if name.is_empty() {
        return Err(GreetingError::EmptyName);
    }
    Ok(format!("Hello, {name}!"))
}

/// Failure returned when a greeting cannot be created.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum GreetingError {
    /// The supplied name contained no non-whitespace characters.
    EmptyName,
}

impl std::fmt::Display for GreetingError {
    fn fmt(&self, formatter: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        formatter.write_str("name must not be empty")
    }
}

impl std::error::Error for GreetingError {}

#[cfg(test)]
mod tests {
    use super::{GreetingError, greeting};

    #[test]
    fn trims_and_greets() {
        assert_eq!(greeting(" Ferris ").as_deref(), Ok("Hello, Ferris!"));
    }

    #[test]
    fn rejects_blank_name() {
        assert_eq!(greeting("  "), Err(GreetingError::EmptyName));
    }
}
