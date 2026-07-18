#[cfg(feature = "blanket-all-features-trap")]
compile_error!("GENAPTIC_CARGO_POLICY_ALL_FEATURES_SENTINEL");

pub fn selected_by_default_policy() -> bool {
    true
}

#[cfg(test)]
mod tests {
    #[test]
    fn default_member_and_features_are_valid() {
        assert!(super::selected_by_default_policy());
    }
}
