PYTHON ?= .venv/bin/python
UV ?= uv

.PHONY: install demo test lint serve docker web-install web-dev web-build web-check check

install:
	$(UV) venv .venv
	$(UV) pip install --python $(PYTHON) -e ".[dev]"
	$(MAKE) web-install

demo:
	$(PYTHON) -m erasureproof.cli demo

test:
	$(PYTHON) -m pytest

lint:
	$(PYTHON) -m ruff check .

web-install:
	cd web && npm ci

web-dev:
	cd web && npm run dev

web-build:
	cd web && npm run build

web-check:
	cd web && npm run typecheck && npm run build

check: lint test web-check

serve:
	$(PYTHON) -m erasureproof.cli serve --reload

docker:
	docker compose up --build
