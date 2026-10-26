PYTHON ?= .venv/bin/python
UV ?= uv

.PHONY: install demo test lint serve docker

install:
	$(UV) venv .venv
	$(UV) pip install --python $(PYTHON) -e ".[dev]"

demo:
	$(PYTHON) -m erasureproof.cli demo

test:
	$(PYTHON) -m pytest

lint:
	$(PYTHON) -m ruff check .

serve:
	$(PYTHON) -m erasureproof.cli serve --reload

docker:
	docker compose up --build
