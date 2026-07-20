use std::ffi::OsString;

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum RunError {
    MissingName,
}

impl std::fmt::Display for RunError {
    fn fmt(&self, formatter: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        formatter.write_str("a name argument is required")
    }
}

impl std::error::Error for RunError {}

pub fn run(arguments: impl IntoIterator<Item = OsString>) -> Result<String, RunError> {
    let mut arguments = arguments.into_iter();
    let name = arguments.next().ok_or(RunError::MissingName)?;
    Ok(format!("Hello, {}!", name.to_string_lossy()))
}

#[cfg(test)]
mod tests {
    use std::ffi::OsString;

    use super::{RunError, run};

    #[test]
    fn reports_a_missing_name() {
        assert_eq!(run(Vec::<OsString>::new()), Err(RunError::MissingName));
    }
}
