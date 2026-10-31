.PHONY: docs check progress

docs:
	@if command -v tree >/dev/null 2>&1; then tree docs; else find docs -type f | sort; fi

check:
	python3 -m unittest discover -s scripts -p 'test_*.py'
	python3 scripts/check_docs.py
	python3 scripts/check_progress.py

progress:
	python3 scripts/check_progress.py

UV_CACHE_DIR ?= .cache/uv
export UV_CACHE_DIR

.PHONY: setup build run test evaluate
setup:
	uv sync --locked
	uv run python -m resourcing_assistant.setup
	npm --prefix frontend ci
	$(MAKE) build

build:
	npm --prefix frontend run build

run:
	uv run uvicorn resourcing_assistant.api:create_app --factory --host 127.0.0.1 --port 8000 --workers 1

test:
	uv run pytest -q

evaluate:
	uv run python -m resourcing_assistant.evaluation
