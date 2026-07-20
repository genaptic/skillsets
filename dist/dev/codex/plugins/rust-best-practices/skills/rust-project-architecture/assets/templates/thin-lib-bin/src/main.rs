use std::process::ExitCode;

fn main() -> ExitCode {
    match thin_lib_bin::run(std::env::args_os().skip(1)) {
        Ok(message) => {
            println!("{message}");
            ExitCode::SUCCESS
        }
        Err(error) => {
            eprintln!("error: {error}");
            ExitCode::FAILURE
        }
    }
}
