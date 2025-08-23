from __future__ import annotations
from typing import List, Dict, Any, Optional
import requests

from .base import BaseLLM, Message

class OllamaLLM(BaseLLM):
    def __init__(self, base_url: str = "http://localhost:11434", model: str = "mistral:latest", timeout: int = 120):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})

    def chat(self, messages: List[Message], **kwargs) -> str:
        # Ollama expects: {"model": "...", "messages": [{"role": "...", "content": "..."}], "stream": false}
        url = f"{self.base_url}/api/chat"
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": kwargs.get("temperature", 0.3),
            }
        }
        resp = self.session.post(url, json=payload, timeout=self.timeout)
        resp.raise_for_status()
        data = resp.json()
        return data.get("message", {}).get("content", "")
