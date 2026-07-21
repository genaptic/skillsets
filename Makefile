BOOTSTRAP_PYTHON ?= python3

.PHONY: bootstrap rust-bootstrap rust-check lock lock-check generate validate eval lint test check check-pack configure clean release

bootstrap:
	$(BOOTSTRAP_PYTHON) tools/bootstrap

rust-bootstrap:
	.venv/bin/python tools/check-rust-assets --bootstrap --cargo-home ".venv/rust-cargo-home"

rust-check:
	.venv/bin/python tools/check-rust-assets --cargo-home ".venv/rust-cargo-home"

lock:
	.venv/bin/python -m skillpack_tools lock

lock-check:
	.venv/bin/python -m skillpack_tools lock --check

generate:
	.venv/bin/python -m skillpack_tools generate

validate:
	.venv/bin/python -m skillpack_tools validate --check-generated --strict-placeholders

eval:
	.venv/bin/python -m skillpack_tools eval

lint:
	.venv/bin/python -m skillpack_tools lint

test:
	.venv/bin/python -m skillpack_tools test

check:
	.venv/bin/python -m skillpack_tools check

check-pack:
	.venv/bin/python -m skillpack_tools check-pack $(PACK)

configure:
	@echo "Use: .venv/bin/python tools/configure-repository --help"

release:
	@echo "Use: .venv/bin/python tools/release-pack PACK_ID --draft for a local rehearsal"

clean:
	rm -rf .build .tmp .pytest_cache .ruff_cache .mypy_cache .coverage htmlcov dist/releases
	find . -type d -name '__pycache__' -prune -exec rm -rf {} +
	find . -type d -name '*.egg-info' -prune -exec rm -rf {} +
	find . -type f -name '*.py[co]' -delete
