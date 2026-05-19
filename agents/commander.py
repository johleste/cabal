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
import json
import re
import time
import requests
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config import OLLAMA_BASE_URL, MODELS, MAX_ROUNDS as _DEFAULT_MAX_ROUNDS
from agents import llmlog

_SYSTEM = """\
You are the Commander — the orchestrating intelligence of Cabal, a local multi-agent AI system.
You coordinate specialist agents to complete research, coding, and adversarial analysis tasks.

Your agents:
  RESEARCHER — technical research, OSINT, structured analysis
  CODER      — code generation, review, debugging
  RECON      — attack postulating, adversarial thinking, red team scenarios
  ANALYST    — synthesis, report writing, summarization
  EXECUTOR   — runs a script and returns exit_code, stdout, and stderr

Dispatch protocol:
  To call an agent: DISPATCH: <AGENT> | <task>
  You may dispatch multiple agents per round (one DISPATCH line each).
  When ready to deliver a final answer: FINAL: <your synthesized result>

Rules:
  - Think through the task before dispatching. You have chain-of-thought reasoning.
  - Pick only the agents you need. Don't dispatch all of them by default.
  - After receiving agent results, synthesize them — don't just concatenate.
  - Be decisive. Deliver a clear FINAL answer.
  - When writing and testing code: dispatch CODER to write, then EXECUTOR to run it.
    If exit_code != 0, dispatch CODER again with the error output to fix it.
    Repeat until exit_code is 0 or you exhaust your rounds.

Sandbox constraints (strictly enforced by EXECUTOR — violations will be rejected):
  - NO install commands of any kind: pip, pip3, apt, apt-get, npm, yarn, cargo,
    gem, conda, brew, snap, pipx. Do not ask CODER to write code that installs.
  - External tools and binaries are ONLY available from the ./tools/ folder.
    Do not call system binaries (curl, nmap, etc.) unless they exist in ./tools/.
  - Use Python standard library or tools already present in ./tools/ for all tasks.
"""


class Commander:
    @property
    def model(self) -> str:
        return MODELS.get("commander", "deepseek-r1:8b")

    def run(self, task: str, agents: dict, max_rounds: int = None, prior_notes: str = "") -> dict:
        max_rounds = max_rounds or _DEFAULT_MAX_ROUNDS
        preamble = f"{prior_notes}\n\nTask: {task}" if prior_notes else f"Task: {task}"
        conversation = preamble
        accumulated = ""
        last_code: str | None = None
        last_exit_code: int | None = None
        last_error: str | None = None

        for round_num in range(max_rounds):
            llmlog.commander_start(round_num)
            raw = self._query(f"{_SYSTEM}\n\n{conversation}")
            llmlog.commander_round_end()
            cleaned = _strip_thinking(raw)

            final_match = re.search(r"FINAL:\s*(.+)", cleaned, re.IGNORECASE | re.DOTALL)
            if final_match:
                final_text = final_match.group(1).strip()
                success = last_exit_code is None or last_exit_code == 0
                return {
                    "result": final_text,
                    "rounds": round_num + 1,
                    "context": accumulated,
                    "success": success,
                    "last_code": last_code,
                    "last_exit_code": last_exit_code,
                    "last_error": last_error,
                }

            dispatches = re.findall(
                r"DISPATCH:\s*(RESEARCHER|CODER|RECON|ANALYST|EXECUTOR)\s*\|\s*(.+?)(?=DISPATCH:|FINAL:|$)",
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
                    agent_out = agent.run(agent_task, context=accumulated[-1000:] if accumulated else "")
                    agent_results.append(f"{agent_name}:\n{agent_out}")
                    if agent_name == "CODER":
                        last_code = agent_out
                    elif agent_name == "EXECUTOR":
                        m = re.search(r"exit_code:\s*(\d+)", agent_out)
                        if m:
                            last_exit_code = int(m.group(1))
                        err_m = re.search(r"stderr:\n(.*)", agent_out, re.DOTALL)
                        if err_m:
                            last_error = err_m.group(1).strip()[:500]
                else:
                    agent_results.append(f"{agent_name}: [not available]")

            block = "\n\n".join(agent_results)
            accumulated += "\n\n" + block
            rounds_left = max_rounds - round_num - 1
            conversation = (
                conversation
                + f"\n\nRound {round_num+1} output:\n{cleaned}"
                + f"\n\nAgent results:\n{block}"
                + f"\n\nRounds remaining: {rounds_left}. "
                + ("Output FINAL: now." if rounds_left <= 1 else "Continue or output FINAL:.")
            )[-3000:]

        return {
            "result": f"Max rounds reached.\n{accumulated[-1000:]}",
            "rounds": max_rounds,
            "context": accumulated,
            "success": False,
            "last_code": last_code,
            "last_exit_code": last_exit_code,
            "last_error": last_error,
        }

    def run_loop(
        self,
        task: str,
        agents: dict,
        max_rounds: int = None,
        max_attempts: int = None,
        use_claude: bool = False,
    ) -> dict:
        """Retry loop: resets conversation each attempt, carries forward notes on what failed."""
        notes: list[dict] = []
        attempt = 0
        while True:
            attempt += 1
            if notes:
                llmlog.retry_attempt(attempt)
            guidance = None
            if use_claude and _is_stagnant(notes):
                from agents import claude_consult
                guidance = claude_consult.consult(task, _format_prior_notes(notes))
            prior = _format_prior_notes(notes, claude_guidance=guidance) if notes else ""
            result = self.run(task, agents, max_rounds, prior_notes=prior)
            result["attempts"] = attempt
            notes.append({
                "attempt": attempt,
                "code": result.get("last_code") or "",
                "exit_code": result.get("last_exit_code"),
                "error": result.get("last_error") or "",
                "final": result.get("result") or "",
            })
            result["attempt_history"] = notes
            if result["success"]:
                return result
            if max_attempts is not None and attempt >= max_attempts:
                return result

    def ask(self, question: str) -> str:
        """Direct question — commander reasons without dispatching agents."""
        llmlog.commander_start(0)
        raw = self._query(f"{_SYSTEM}\n\nQuestion: {question}")
        llmlog.commander_round_end()
        result = _strip_thinking(raw)
        result = re.sub(r"^FINAL:\s*", "", result, flags=re.IGNORECASE).strip()
        return result

    def _query(self, prompt: str) -> str:
        for attempt in range(3):
            try:
                resp = requests.post(
                    f"{OLLAMA_BASE_URL}/api/generate",
                    json={"model": self.model, "prompt": prompt, "stream": True},
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
                        llmlog.commander_token(token)
                        if chunk.get("done"):
                            break
                return raw.strip()
            except requests.exceptions.RequestException as e:
                llmlog.error("commander", f"attempt {attempt+1}/3: {e}")
                if attempt < 2:
                    time.sleep(3)
        return "[commander error: failed after 3 attempts]"


def _strip_thinking(text: str) -> str:
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


def _format_prior_notes(notes: list[dict], claude_guidance: str = None) -> str:
    lines = ["=== Prior Attempts — read before proceeding ===\n"]
    for n in notes:
        lines.append(f"Attempt {n['attempt']}:")
        if n["code"]:
            snippet = n["code"][:600] + ("..." if len(n["code"]) > 600 else "")
            lines.append(f"  Code written:\n```\n{snippet}\n```")
        if n["exit_code"] is not None:
            lines.append(f"  Exit code: {n['exit_code']}")
        if n["error"]:
            err = n["error"][:400] + ("..." if len(n["error"]) > 400 else "")
            lines.append(f"  Error:\n    {err}")
        elif n["final"]:
            lines.append(f"  Commander concluded: {n['final'][:200]}")
        lines.append("")
    lines.append("These approaches failed. Try a meaningfully different strategy.\n")
    if claude_guidance:
        lines.append("=== Claude Consultation ===\n")
        lines.append(claude_guidance)
        lines.append("\nApply the consultation guidance above in your next attempt.\n")
    return "\n".join(lines)


def _is_stagnant(notes: list[dict]) -> bool:
    """True if the last two attempts produced the same exit code and same error — genuinely stuck."""
    if len(notes) < 2:
        return False
    a, b = notes[-2], notes[-1]
    if a.get("exit_code") != b.get("exit_code"):
        return False
    a_err = (a.get("error") or "")[:150]
    b_err = (b.get("error") or "")[:150]
    return bool(a_err) and a_err == b_err
