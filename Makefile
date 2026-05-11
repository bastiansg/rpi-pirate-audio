.PHONY: uv-setup rainbow buttons app format lint lint-fix typecheck check

uv-setup:
	uv venv --clear
	uv pip install -r requirements.txt

rainbow:
	uv run python src/scripts/rainbow.py

buttons:
	uv run python src/scripts/buttons.py

app:
	uv run python src/app/app.py

format:
	uv run ruff format src

lint:
	uv run ruff check src

lint-fix:
	uv run ruff check --fix src

typecheck:
	uv run pyrefly check

check: lint typecheck
