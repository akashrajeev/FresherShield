# Common tasks. Run `make help` for the list.

PY ?= python3
VENV ?= .venv
BIN := $(VENV)/bin

.PHONY: help install dev test eval run offline docker-build docker-run clean

help:  ## show this list
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F ':.*## ' '{printf "  %-13s %s\n", $$1, $$2}'

$(BIN)/python:
	$(PY) -m venv $(VENV)

install: $(BIN)/python  ## create .venv and install app dependencies
	$(BIN)/pip install -q -r requirements.txt

dev: $(BIN)/python  ## install app + test dependencies
	$(BIN)/pip install -q -r requirements-dev.txt

test: dev  ## run the test suite (no key, no network, no credits)
	FS_OFFLINE=1 $(BIN)/pytest -q

eval: dev  ## score the detector on the labelled offer set (eval/dataset.jsonl)
	$(BIN)/python eval/run_eval.py

run: install  ## start the app on http://127.0.0.1:8000 (reads SERPAPI_API_KEY from .env)
	$(BIN)/python -m app.main

offline: install  ## start the app from the local cache only; spends no credits
	FS_OFFLINE=1 $(BIN)/python -m app.main

docker-build:  ## build the Docker image
	docker build -t freshershield .

docker-run: docker-build  ## run the image on port 8000 with .env and a persistent cache volume
	docker run --rm -p 8000:8000 $$( [ -f .env ] && echo --env-file .env ) -v fs-cache:/app/.cache freshershield

clean:  ## remove caches (keeps the SerpApi response cache in .cache/)
	rm -rf .pytest_cache; find . -name __pycache__ -type d -prune -exec rm -rf {} +
