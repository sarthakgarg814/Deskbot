# Peekabot dev commands. Backend runs anywhere (mock hardware); the Pi installs
# the extra `.[pi]` deps and flips config/defaults.yaml -> hardware_backend: real.

BACKEND := backend
VENV := $(BACKEND)/.venv
PY := $(VENV)/bin/python

.PHONY: help setup backend test frontend-install frontend-dev frontend-build run clean

help:
	@echo "setup            create venv + install backend (mock hardware)"
	@echo "backend          run the API + dashboard (uvicorn, :8000)"
	@echo "test             run backend smoke tests"
	@echo "frontend-install install dashboard deps"
	@echo "frontend-dev     run the Vite dev server (:5173, proxies /api -> :8000)"
	@echo "frontend-build   build the dashboard -> frontend/dist (served by backend)"
	@echo "run              backend + built dashboard on http://localhost:8000"

setup:
	python3 -m venv $(VENV)
	$(PY) -m pip install -q --upgrade pip
	$(PY) -m pip install -e "$(BACKEND)[dev]"

backend:
	cd $(BACKEND) && .venv/bin/uvicorn core.main:app --reload --host 0.0.0.0 --port 8000

test:
	cd $(BACKEND) && .venv/bin/python -m pytest -q

frontend-install:
	cd frontend && npm install

frontend-dev:
	cd frontend && npm run dev

frontend-build:
	cd frontend && npm run build

run: frontend-build backend

clean:
	rm -f peekabot.db*
	rm -rf frontend/dist
