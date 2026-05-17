"""
BaseAgent — one Ollama model, one role.
LLM output is always logged to stderr unless CABAL_QUIET=1.
"""
import json
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

    def query(self, prompt: str, context: str = "") -> str:
        if context:
            full = f"{self.system_prompt}\n\nContext:\n{context}\n\nInput:\n{prompt}"
        else:
            full = f"{self.system_prompt}\n\nInput:\n{prompt}"

        llmlog.agent_call(self.role, self.model, prompt)
        t0 = time.monotonic()
        for attempt in range(3):
            try:
                resp = requests.post(
                    f"{OLLAMA_BASE_URL}/api/generate",
                    json={"model": self.model, "prompt": full, "stream": True},
                    stream=True,
                    timeout=(10, None),  # (connect, no read timeout — let it run)
                )
                resp.raise_for_status()
                raw = ""
                for line in resp.iter_lines():
                    if line:
                        chunk = json.loads(line)
                        token = chunk.get("response", "")
                        raw += token
                        llmlog.agent_token(token)
                        if chunk.get("done"):
                            break
                llmlog.agent_response_end(self.role, time.monotonic() - t0)
                return raw.strip()
            except requests.exceptions.RequestException as e:
                llmlog.error(self.role, f"attempt {attempt+1}/3: {e}")
                if attempt < 2:
                    time.sleep(3)
        return f"[{self.role} error: failed after 3 attempts]"
