include!(concat!(
    env!("CARGO_MANIFEST_DIR"),
    "/../../../packs/rust/cli-apps/skills/rust-cli-application-design/assets/templates/finite_bounded_number.rs"
));

#[cfg(test)]
mod tests {
    use super::{BoundedNumberError, parse_finite_bounded};

    #[test]
    fn non_finite_values_and_bounds_are_rejected() {
        for input in ["NaN", "inf", "-inf"] {
            assert_eq!(
                parse_finite_bounded(input, -1.0, 1.0),
                Err(BoundedNumberError::NonFinite)
            );
        }
        assert_eq!(
            parse_finite_bounded("0", f64::NEG_INFINITY, 1.0),
            Err(BoundedNumberError::InvalidBounds)
        );
        assert_eq!(
            parse_finite_bounded("2", -1.0, 1.0),
            Err(BoundedNumberError::OutOfRange)
        );
        assert_eq!(parse_finite_bounded("0.5", -1.0, 1.0), Ok(0.5));
    }
}
