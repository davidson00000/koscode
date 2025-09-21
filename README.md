# koscode
Local sub-agent playground (CLI).

- Python 3.12 + venv
- pytest
- LLM via Ollama (planner: llama3.2:3b, coder: qwen2.5-coder:7b)

## Quickstart
~~~bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python agent.py plan
python agent.py loop --max-iters 3
~~~

## Prerequisites
- Python 3.12
- [Ollama](https://ollama.com/) 0.12+ （ローカルで `ollama serve` が動作）
- モデルを取得しておく:
~~~bash
ollama pull llama3.2:3b-instruct-q4_K_M
ollama pull qwen2.5-coder:7b-instruct-q4_K_M
~~~
