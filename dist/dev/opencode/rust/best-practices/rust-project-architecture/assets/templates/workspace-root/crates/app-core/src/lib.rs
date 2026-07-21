#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum NameError {
    Empty,
}

pub fn greeting(name: &str) -> Result<String, NameError> {
    let name = name.trim();
    if name.is_empty() {
        return Err(NameError::Empty);
    }
    Ok(format!("Hello, {name}!"))
}
