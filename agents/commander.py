"""
Commander — the orchestrating brain. Runs on deepseek-r1:8b.

Receives a task from the operator and decides which agents to call,
in what order, and synthesizes their outputs into a final answer.
deepseek-r1's chain-of-thought reasoning drives dispatch decisions.

Dispatch protocol:
  DISPATCH: <AGENT> | <task or question>
  FINAL: <synthesized result>

Agents: RESEARCHER | CODER | RECON | ANALYST
"""
import re
import time
import requests
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config import OLLAMA_BASE_URL, MODELS
from agents import llmlog

_MAX_ROUNDS = 4

_SYSTEM = """\
You are the Commander — the orchestrating intelligence of Cabal, a local multi-agent AI system.
You coordinate specialist agents to complete research, coding, and adversarial analysis tasks.

Your agents:
  RESEARCHER — technical research, OSINT, structured analysis
  CODER      — code generation, review, debugging
  RECON      — attack postulating, adversarial thinking, red team scenarios
  ANALYST    — synthesis, report writing, summarization

Dispatch protocol:
  To call an agent: DISPATCH: <AGENT> | <task>
  You may dispatch multiple agents per round (one DISPATCH line each).
  When ready to deliver a final answer: FINAL: <your synthesized result>

Rules:
  - Think through the task before dispatching. You have chain-of-thought reasoning.
  - Pick only the agents you need. Don't dispatch all of them by default.
  - After receiving agent results, synthesize them — don't just concatenate.
  - Be decisive. Deliver a clear FINAL answer.
"""


class Commander:
    @property
    def model(self) -> str:
        return MODELS.get("commander", "deepseek-r1:8b")

    def run(self, task: str, agents: dict) -> dict:
        conversation = f"Task: {task}"
        accumulated = ""
        final_text = None

        for round_num in range(_MAX_ROUNDS):
            raw = self._query(f"{_SYSTEM}\n\n{conversation}")
            llmlog.commander_round(round_num, raw)
            cleaned = _strip_thinking(raw)

            final_match = re.search(r"FINAL:\s*(.+)", cleaned, re.IGNORECASE | re.DOTALL)
            if final_match:
                final_text = final_match.group(1).strip()
                llmlog.commander_final(final_text)
                return {"result": final_text, "rounds": round_num + 1, "context": accumulated}

            dispatches = re.findall(
                r"DISPATCH:\s*(RESEARCHER|CODER|RECON|ANALYST)\s*\|\s*(.+?)(?=DISPATCH:|FINAL:|$)",
                cleaned, re.IGNORECASE | re.DOTALL,
            )

            if not dispatches:
                conversation += (
                    f"\n\nRound {round_num+1} output:\n{cleaned}"
                    "\n\nYou must DISPATCH to an agent or output FINAL:."
                )
                continue

            agent_results = []
            for agent_name, agent_task in dispatches:
                agent_name = agent_name.upper().strip()
                agent_task = agent_task.strip()
                llmlog.commander_dispatch(agent_name, agent_task)
                agent = agents.get(agent_name)
                if agent:
                    result = agent.run(agent_task, context=accumulated[-1000:] if accumulated else "")
                    agent_results.append(f"{agent_name}:\n{result}")
                else:
                    agent_results.append(f"{agent_name}: [not available]")

            block = "\n\n".join(agent_results)
            accumulated += "\n\n" + block
            rounds_left = _MAX_ROUNDS - round_num - 1
            conversation = (
                conversation
                + f"\n\nRound {round_num+1} output:\n{cleaned}"
                + f"\n\nAgent results:\n{block}"
                + f"\n\nRounds remaining: {rounds_left}. "
                + ("Output FINAL: now." if rounds_left <= 1 else "Continue or output FINAL:.")
            )[-3000:]

        return {
            "result": f"Max rounds reached.\n{accumulated[-1000:]}",
            "rounds": _MAX_ROUNDS,
            "context": accumulated,
        }

    def ask(self, question: str) -> str:
        """Direct question — commander reasons without dispatching agents."""
        raw = self._query(f"{_SYSTEM}\n\nQuestion: {question}", timeout=600)
        llmlog.commander_round(0, raw)
        result = _strip_thinking(raw)
        result = re.sub(r"^FINAL:\s*", "", result, flags=re.IGNORECASE).strip()
        return result

    def _query(self, prompt: str, timeout: int = 300) -> str:
        try:
            resp = requests.post(
                f"{OLLAMA_BASE_URL}/api/generate",
                json={"model": self.model, "prompt": prompt, "stream": False},
                timeout=timeout,
            )
            resp.raise_for_status()
            return resp.json().get("response", "").strip()
        except requests.exceptions.RequestException as e:
            llmlog.error("commander", str(e))
            return f"[commander error: {e}]"


def _strip_thinking(text: str) -> str:
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
