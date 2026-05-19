.PHONY: uv-setup status-display bluetooth-a2dp-setup format lint lint-fix typecheck check

uv-setup:
	uv venv --clear
	uv pip install -r requirements.txt

status-display:
	uv run python -m src.apps.status_display.main

bluetooth-a2dp-setup:
	./scripts/setup-bluetooth-a2dp-sink.sh

format:
	uv run ruff format src

lint:
	uv run ruff check src

lint-fix:
	uv run ruff check --fix src

typecheck:
	uv run pyrefly check

check: lint typecheck


start:
	pm2 start && pm2 save --force

stop:
	pm2 stop all && pm2 save --force
	pm2 flush

restart: stop start
