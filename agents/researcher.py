"""
Researcher — structured analysis, OSINT, threat research.
Uses deepseek-coder-v2 for its strong structured reasoning.
"""
from agents.base import BaseAgent

_SYSTEM = """\
You are a technical researcher. You produce structured, accurate, well-cited analysis.
When asked about a topic, cover: what it is, how it works, relevant technical detail,
and implications. Be concise and precise. No filler.
"""


class ResearcherAgent(BaseAgent):
    role = "researcher"
    system_prompt = _SYSTEM

    def run(self, question: str, context: str = "") -> str:
        return self.query(question, context=context)
