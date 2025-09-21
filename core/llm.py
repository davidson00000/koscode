# core/llm.py
import requests
from typing import List, Dict

def ollama_chat(
    model: str,
    messages: List[Dict],
    temperature: float = 0.2,
    num_ctx: int = 2048,
    num_predict: int = 256,
    timeout: int = 180
) -> str:
    """
    Ollama /api/chat を非ストリーミングで叩く。戻りの揺れに耐性あり。
    """
    payload = {
        "model": model,
        "messages": messages,
        "options": {
            "temperature": temperature,
            "num_ctx": num_ctx,
            "num_predict": num_predict
        },
        "stream": False
    }
    r = requests.post("http://localhost:11434/api/chat", json=payload, timeout=timeout)
    r.raise_for_status()
    data = r.json()

    if isinstance(data, dict):
        if "message" in data and isinstance(data["message"], dict):
            return data["message"].get("content", "")
        if "messages" in data and isinstance(data["messages"], list) and data["messages"]:
            last = data["messages"][-1]
            if isinstance(last, dict):
                return last.get("content", "")
        return data.get("response", "")
    if isinstance(data, str):
        return data
    return ""
