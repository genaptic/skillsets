pub trait Render {
    fn render(&self, input: &str) -> Result<String, RenderError>;
}

pub struct PlainRenderer;

impl Render for PlainRenderer {
    fn render(&self, input: &str) -> Result<String, RenderError> {
        Ok(input.to_owned())
    }
}

pub struct UppercaseRenderer;

impl Render for UppercaseRenderer {
    fn render(&self, input: &str) -> Result<String, RenderError> {
        Ok(input.to_uppercase())
    }
}

pub enum Renderer {
    Plain(PlainRenderer),
    Uppercase(UppercaseRenderer),
}

impl Render for Renderer {
    fn render(&self, input: &str) -> Result<String, RenderError> {
        match self {
            Self::Plain(renderer) => renderer.render(input),
            Self::Uppercase(renderer) => renderer.render(input),
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct RenderError;

impl std::fmt::Display for RenderError {
    fn fmt(&self, formatter: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        formatter.write_str("rendering failed")
    }
}

impl std::error::Error for RenderError {}
