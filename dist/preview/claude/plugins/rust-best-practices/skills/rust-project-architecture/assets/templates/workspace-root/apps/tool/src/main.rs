use std::process::ExitCode;

fn main() -> ExitCode {
    let Some(name) = std::env::args().nth(1) else {
        eprintln!("usage: tool <name>");
        return ExitCode::FAILURE;
    };

    match app_core::greeting(&name) {
        Ok(message) => {
            println!("{message}");
            ExitCode::SUCCESS
        }
        Err(app_core::NameError::Empty) => {
            eprintln!("error: name must not be empty");
            ExitCode::FAILURE
        }
    }
}
