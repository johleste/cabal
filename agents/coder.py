"""
Coder — code generation, review, and debugging.
Uses deepseek-coder-v2 for its strong code understanding.
"""
from agents.base import BaseAgent

_SYSTEM = """\
You are an expert software engineer. You write clean, correct, idiomatic code.
When given a task: implement it directly. When given code to review: identify real issues only.
Output code in fenced blocks with the language specified. No unnecessary commentary.
"""


class CoderAgent(BaseAgent):
    role = "coder"
    system_prompt = _SYSTEM

    def run(self, task: str, context: str = "") -> str:
        return self.query(task, context=context)
