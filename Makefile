BOOTSTRAP_PYTHON ?= python3
VENV ?= .venv
PYTHON ?= $(VENV)/bin/python
RUST_CARGO_HOME ?= $(VENV)/rust-cargo-home

.PHONY: bootstrap rust-bootstrap rust-check lock lock-check generate validate eval lint test check configure clean release

bootstrap:
	$(BOOTSTRAP_PYTHON) -m venv $(VENV)
	$(PYTHON) -m pip install --require-hashes -r requirements-dev.txt
	$(PYTHON) -m pip install --no-deps --no-build-isolation -e .
	$(PYTHON) -c "from pathlib import Path; import sys; sys.exit(0 if Path('$(VENV)/bin/skillpacks').is_file() else 'skillpacks entry point was not installed')"
	$(MAKE) rust-bootstrap

rust-bootstrap:
	$(PYTHON) tools/check-rust-assets --bootstrap --cargo-home "$(RUST_CARGO_HOME)"

rust-check:
	$(PYTHON) tools/check-rust-assets --cargo-home "$(RUST_CARGO_HOME)"

lock:
	CUSTOM_COMPILE_COMMAND="make lock" $(PYTHON) -m piptools compile --allow-unsafe --generate-hashes --quiet --strip-extras --resolver=backtracking --output-file=requirements-dev.txt requirements-dev.in

lock-check:
	$(PYTHON) tools/check-dependency-lock

generate:
	$(PYTHON) tools/generate-all

validate:
	$(PYTHON) tools/validate-repository --check-generated --strict-placeholders

eval:
	$(PYTHON) tools/run-evals

lint:
	$(PYTHON) -m ruff check .
	$(PYTHON) -m ruff format --check .
	$(PYTHON) tools/lint-portable

test:
	$(PYTHON) -m pytest

check: lock-check rust-check
	$(PYTHON) tools/generate-all --check
	$(MAKE) validate eval lint test

configure:
	@echo "Use: $(PYTHON) tools/configure-repository --help"

release:
	@echo "Use: $(PYTHON) tools/release-pack PACK_ID --draft for a local rehearsal"

clean:
	rm -rf .build .tmp .pytest_cache .ruff_cache .mypy_cache .coverage htmlcov dist/releases
	find . -type d -name '__pycache__' -prune -exec rm -rf {} +
	find . -type d -name '*.egg-info' -prune -exec rm -rf {} +
	find . -type f -name '*.py[co]' -delete
