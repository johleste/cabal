"""
BaseAgent — one Ollama model, one role.
LLM output is always logged to stderr unless CABAL_QUIET=1.
"""
import time
import requests
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config import OLLAMA_BASE_URL, MODELS
from agents import llmlog


class BaseAgent:
    role: str = ""
    system_prompt: str = ""

    @property
    def model(self) -> str:
        return MODELS.get(self.role, "llama3.1:latest")

    def query(self, prompt: str, context: str = "", timeout: int = 300) -> str:
        if context:
            full = f"{self.system_prompt}\n\nContext:\n{context}\n\nInput:\n{prompt}"
        else:
            full = f"{self.system_prompt}\n\nInput:\n{prompt}"

        llmlog.agent_call(self.role, self.model, prompt)
        t0 = time.monotonic()
        try:
            resp = requests.post(
                f"{OLLAMA_BASE_URL}/api/generate",
                json={"model": self.model, "prompt": full, "stream": False},
                timeout=timeout,
            )
            resp.raise_for_status()
            raw = resp.json().get("response", "").strip()
            llmlog.agent_response(self.role, time.monotonic() - t0, raw)
            return raw
        except requests.exceptions.RequestException as e:
            llmlog.error(self.role, str(e))
            return f"[{self.role} error: {e}]"
