# table_peak — dev workflow wrapper.
# Single Bash matcher `Bash(make:*)` covers the whole dev surface under
# Claude Code; pdm is the underlying package/lockfile manager.
#
# Daily targets call `.venv/bin/<tool>` directly so they don't depend
# on `pdm run` at runtime. `make sync` is the only target that invokes
# pdm; run it after pulling or after dep changes.
#
# Run `make help` for the target list.

.PHONY: help sync lint format format-check typecheck test check clean

help: ## Show this help and the available targets
	@awk 'BEGIN {FS = ":.*?## "; printf "Targets:\n"} /^[a-zA-Z_-]+:.*?## / {printf "  %-15s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

sync: ## Install / sync dependencies from pdm.lock into .venv
	pdm install

lint: ## Run ruff lint over src/ and tests/
	.venv/bin/ruff check

format: ## Apply ruff formatting (mutates files)
	.venv/bin/ruff format

format-check: ## Check ruff formatting without mutating
	.venv/bin/ruff format --check

typecheck: ## Run mypy --strict (config in pyproject.toml)
	.venv/bin/mypy

test: ## Run pytest
	.venv/bin/pytest

check: lint format-check typecheck test ## Run the full local-CI suite

clean: ## Remove tool caches (.mypy_cache, .ruff_cache, .pytest_cache)
	@for d in .mypy_cache .ruff_cache .pytest_cache; do \
		if [ -e "$$d" ]; then trash "$$d"; fi; \
	done
