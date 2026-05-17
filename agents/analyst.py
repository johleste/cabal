"""
Analyst — synthesis, summaries, written reports.
Uses dolphin-llama3 for its strong instruction following and prose quality.
"""
from agents.base import BaseAgent

_SYSTEM = """\
You are a senior analyst. You synthesize findings from multiple sources into clear,
actionable reports. You write well. You cut noise. You lead with the most important finding.
"""


class AnalystAgent(BaseAgent):
    role = "analyst"
    system_prompt = _SYSTEM

    def run(self, task: str, context: str = "") -> str:
        return self.query(task, context=context)
