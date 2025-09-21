.ONESHELL:
VENV=.venv
PY=$(VENV)/bin/python
PIP=$(VENV)/bin/pip

venv:
	python3 -m venv $(VENV)
	$(PIP) install -U pip
	$(PIP) install -r requirements.txt

models:
	ollama pull llama3.2:3b-instruct-q4_K_M || true
	ollama pull qwen2.5-coder:7b-instruct-q4_K_M || true

plan:
	$(PY) agent.py plan

loop:
	$(PY) agent.py loop --max-iters 3

test:
	PYTHONPATH=workspace $(VENV)/bin/pytest -q -s
