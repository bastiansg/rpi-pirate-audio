.PHONY: uv-setup rainbow buttons

uv-setup:
	uv venv --clear
	uv pip install -r requirements.txt

rainbow:
	uv run python scripts/rainbow.py

buttons:
	uv run python scripts/buttons.py
