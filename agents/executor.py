"""
Executor — runs code produced by the Coder and returns exit code + output.
Does not call Ollama. Extracts the last fenced code block from its input,
saves it to a session-scoped file, executes it, and returns structured results.

Generated code is kept at sessions/<stamp>_code_NNN.<ext> for review.
Commander should dispatch here after CODER writes a script, then re-dispatch
CODER with the error output if exit_code != 0.
"""
import os
import re
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import session
from config import EXECUTOR_TIMEOUT
from agents import llmlog

# Set to True at runtime (from --confirm flag) to prompt before each execution.
CONFIRM = False

_LANG_CMDS = {
    "python":  ["python3"],
    "python3": ["python3"],
    "bash":    ["bash"],
    "sh":      ["sh"],
}
_LANG_EXTS = {
    "python":  ".py",
    "python3": ".py",
    "bash":    ".sh",
    "sh":      ".sh",
}
_DEFAULT_CMD = ["python3"]
_DEFAULT_EXT = ".py"


class ExecutorAgent:
    role = "executor"

    def run(self, task: str, context: str = "") -> str:
        source = (context + "\n\n" + task) if context else task
        code, lang = _extract_code(source)

        if not code:
            return "[EXECUTOR] No fenced code block found. CODER must wrap the script in a fenced block."

        cmd = _LANG_CMDS.get(lang, _DEFAULT_CMD)
        ext = _LANG_EXTS.get(lang, _DEFAULT_EXT)

        if CONFIRM:
            label = lang or "python"
            print(f"\n[executor] Script to run ({label}):", file=sys.stderr)
            print("─" * 50, file=sys.stderr)
            print(code, file=sys.stderr)
            print("─" * 50, file=sys.stderr)
            answer = input("[executor] Run this? [y/N] ").strip().lower()
            if answer != "y":
                llmlog.agent_call(self.role, "exec", task[:80])
                llmlog.agent_response_end(self.role, 0)
                return "[EXECUTOR] Execution cancelled by user."

        # Save to a session-scoped file so generated code is never lost
        code_path = session.next_code_file(ext)
        code_path.write_text(code)
        print(f"[executor] code → {code_path}", file=sys.stderr)

        llmlog.agent_call(self.role, " ".join(cmd), str(code_path))
        t0 = time.monotonic()
        try:
            proc = subprocess.run(
                cmd + [str(code_path)],
                capture_output=True,
                text=True,
                timeout=EXECUTOR_TIMEOUT,
            )
            elapsed = time.monotonic() - t0
            parts = [f"exit_code: {proc.returncode}", f"elapsed: {elapsed:.1f}s"]
            if proc.stdout.strip():
                parts.append(f"stdout:\n{proc.stdout.strip()}")
            if proc.stderr.strip():
                parts.append(f"stderr:\n{proc.stderr.strip()}")
            result = "\n".join(parts)
        except subprocess.TimeoutExpired:
            elapsed = time.monotonic() - t0
            result = f"[EXECUTOR] Timed out after {EXECUTOR_TIMEOUT}s."
        except Exception as e:
            elapsed = time.monotonic() - t0
            result = f"[EXECUTOR] Failed to launch script: {e}"

        llmlog.agent_response_end(self.role, elapsed)
        return result


def _extract_code(text: str) -> tuple[str, str]:
    """Return (code, language) from the last fenced code block in text."""
    matches = list(re.finditer(r"```(\w*)\n(.*?)```", text, re.DOTALL))
    if not matches:
        return "", ""
    m = matches[-1]
    return m.group(2).strip(), m.group(1).lower()
