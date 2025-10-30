PYTHON ?= python
PYTEST_ARGS ?=
ARGS ?=

.PHONY: lint type test-fast test-net map docs build

lint:
	$(PYTHON) -m ruff check .
	$(PYTHON) -m black --check .

type:
	$(PYTHON) -m mypy

test-fast:
	$(PYTHON) -m pytest -m "not network" $(PYTEST_ARGS)

test-net:
	$(PYTHON) -m pytest -m "network" --network $(PYTEST_ARGS)

map:
	$(PYTHON) -m fair3.cli.main map $(ARGS)

docs:
	$(PYTHON) -m sphinx -b html docs docs/_build/html

build:
	$(PYTHON) -m build
