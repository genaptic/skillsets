// Adaptable finite, bounded floating-point parser for non-monetary configuration.
//
// Validate finiteness before applying domain bounds. Money should use integer minor units or a
// repository-approved checked decimal type instead of this helper.

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum BoundedNumberError {
    InvalidBounds,
    InvalidNumber,
    NonFinite,
    OutOfRange,
}

fn parse_finite_bounded(
    input: &str,
    inclusive_minimum: f64,
    inclusive_maximum: f64,
) -> Result<f64, BoundedNumberError> {
    if !inclusive_minimum.is_finite()
        || !inclusive_maximum.is_finite()
        || inclusive_minimum > inclusive_maximum
    {
        return Err(BoundedNumberError::InvalidBounds);
    }

    let value = input
        .parse::<f64>()
        .map_err(|_| BoundedNumberError::InvalidNumber)?;
    if !value.is_finite() {
        return Err(BoundedNumberError::NonFinite);
    }
    if !(inclusive_minimum..=inclusive_maximum).contains(&value) {
        return Err(BoundedNumberError::OutOfRange);
    }

    Ok(value)
}
