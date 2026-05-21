# table_peak — dev workflow wrapper.
# Single Bash matcher `Bash(make:*)` covers the whole dev surface under
# Claude Code; uv remains the underlying tool.
#
# Run `make help` for the target list.

.PHONY: help sync lint format format-check typecheck test check clean

help: ## Show this help and the available targets
	@awk 'BEGIN {FS = ":.*?## "; printf "Targets:\n"} /^[a-zA-Z_-]+:.*?## / {printf "  %-15s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

sync: ## Install / sync dependencies from uv.lock into .venv
	uv sync

lint: ## Run ruff lint over src/ and tests/
	uv run ruff check

format: ## Apply ruff formatting (mutates files)
	uv run ruff format

format-check: ## Check ruff formatting without mutating
	uv run ruff format --check

typecheck: ## Run mypy --strict (config in pyproject.toml)
	uv run mypy

test: ## Run pytest
	uv run pytest

check: lint format-check typecheck test ## Run the full local-CI suite

clean: ## Remove tool caches (.mypy_cache, .ruff_cache, .pytest_cache)
	@for d in .mypy_cache .ruff_cache .pytest_cache; do \
		if [ -e "$$d" ]; then trash "$$d"; fi; \
	done
