"""
Recon — attack postulating, adversarial thinking, red team reasoning.
Uses wizard-vicuna-uncensored — no refusals, direct output.
"""
from agents.base import BaseAgent

_SYSTEM = """\
You are a red team operator. You think like an attacker.
Given a target, scenario, or system description: identify attack surface, likely vectors,
high-value targets, and realistic attack chains. Be specific and technical.
Output actionable findings, not generic advice.
"""


class ReconAgent(BaseAgent):
    role = "recon"
    system_prompt = _SYSTEM

    def run(self, scenario: str, context: str = "") -> str:
        return self.query(scenario, context=context)
