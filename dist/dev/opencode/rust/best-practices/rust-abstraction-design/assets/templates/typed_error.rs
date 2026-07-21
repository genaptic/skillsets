#[derive(Debug)]
pub enum ParseCountError {
    Invalid(std::num::ParseIntError),
    Zero,
}

impl std::fmt::Display for ParseCountError {
    fn fmt(&self, formatter: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::Invalid(_) => formatter.write_str("count must be an unsigned integer"),
            Self::Zero => formatter.write_str("count must be greater than zero"),
        }
    }
}

impl std::error::Error for ParseCountError {
    fn source(&self) -> Option<&(dyn std::error::Error + 'static)> {
        match self {
            Self::Invalid(error) => Some(error),
            Self::Zero => None,
        }
    }
}

pub fn parse_count(input: &str) -> Result<std::num::NonZeroU32, ParseCountError> {
    let value = input.parse().map_err(ParseCountError::Invalid)?;
    std::num::NonZeroU32::new(value).ok_or(ParseCountError::Zero)
}
