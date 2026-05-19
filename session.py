"""
Session manager — writes all run output to sessions/<timestamp>_<cmd>.txt
incrementally, flushed per token, so you can read it mid-run.

On failure, fail() writes a separate <timestamp>_<cmd>_notes.txt summarising
every attempt: what code was written, exit codes, and errors.
"""
import sys
from datetime import datetime
from pathlib import Path
from config import SESSION_DIR

_file = None
_path: Path | None = None
_code_counter = 0


def start(cmd: str, task: str) -> Path:
    global _file, _path, _code_counter
    Path(SESSION_DIR).mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    slug = cmd.replace(" ", "_")[:32]
    _path = Path(SESSION_DIR) / f"{stamp}_{slug}.txt"
    _code_counter = 0
    _file = open(_path, "w", buffering=1)  # line-buffered
    _write(f"CABAL SESSION\n")
    _write(f"started : {datetime.now().isoformat()}\n")
    _write(f"command : {cmd}\n")
    _write(f"task    : {task}\n")
    _write(f"{'─' * 60}\n\n")
    print(f"[cabal] session → {_path}", file=sys.stderr)
    return _path


def write(text: str):
    _write(text)


def writeln(text: str = ""):
    _write(text + "\n")


def finish(result: str):
    _write(f"\n{'═' * 60}\n")
    _write(f"FINAL RESULT\n")
    _write(f"{'═' * 60}\n")
    _write(result + "\n")
    _write(f"\nfinished: {datetime.now().isoformat()}\n")
    if _file:
        _file.close()


def fail(task: str, result: dict):
    """Write FINAL RESULT to the session log, then write a separate _notes.txt
    with a structured summary of every attempt that was made."""
    finish(result.get("result", "[no result]"))

    if _path is None:
        return

    notes_path = _path.parent / (_path.stem + "_notes.txt")
    history: list[dict] = result.get("attempt_history") or []
    attempts = result.get("attempts", len(history))

    lines = []
    lines.append("CABAL FAILURE NOTES")
    lines.append(f"{'═' * 60}")
    lines.append(f"task     : {task}")
    lines.append(f"attempts : {attempts}")
    lines.append(f"session  : {_path}")
    lines.append(f"written  : {datetime.now().isoformat()}")
    lines.append("")

    if history:
        lines.append(f"{'─' * 60}")
        lines.append("ATTEMPT HISTORY")
        lines.append(f"{'─' * 60}")
        for n in history:
            lines.append(f"\nAttempt {n['attempt']}:")
            ec = n.get("exit_code")
            lines.append(f"  exit_code : {ec if ec is not None else 'n/a'}")
            if n.get("error"):
                lines.append(f"  error     :")
                for ln in n["error"].splitlines():
                    lines.append(f"    {ln}")
            if n.get("code"):
                lines.append(f"  code      :")
                for ln in n["code"].splitlines():
                    lines.append(f"    {ln}")
            if n.get("final"):
                snip = n["final"][:300] + ("..." if len(n["final"]) > 300 else "")
                lines.append(f"  commander : {snip}")

    lines.append(f"\n{'─' * 60}")
    last_code = result.get("last_code")
    last_exit = result.get("last_exit_code")
    last_err  = result.get("last_error")
    lines.append(f"LAST KNOWN STATE")
    lines.append(f"{'─' * 60}")
    lines.append(f"exit_code : {last_exit if last_exit is not None else 'n/a'}")
    if last_err:
        lines.append("error     :")
        for ln in last_err.splitlines():
            lines.append(f"  {ln}")
    if last_code:
        lines.append("code      :")
        for ln in last_code.splitlines():
            lines.append(f"  {ln}")

    lines.append(f"\n{'═' * 60}")
    lines.append(f"All {attempts} attempt(s) exhausted without a passing execution.")
    lines.append(f"Full session log: {_path}")
    lines.append(f"{'═' * 60}")

    notes_path.write_text("\n".join(lines) + "\n")
    print(f"[cabal] failure notes → {notes_path}", file=sys.stderr)


def next_code_file(ext: str) -> Path:
    """Return a session-scoped path for saving generated code, e.g.
    sessions/20260518_161234_run_code_001.py"""
    global _code_counter
    _code_counter += 1
    if _path is not None:
        return _path.parent / f"{_path.stem}_code_{_code_counter:03d}{ext}"
    # fallback if called before session starts
    Path(SESSION_DIR).mkdir(exist_ok=True)
    return Path(SESSION_DIR) / f"code_{_code_counter:03d}{ext}"


def latest() -> Path | None:
    d = Path(SESSION_DIR)
    if not d.exists():
        return None
    files = sorted(d.glob("*.txt"))
    return files[-1] if files else None


def _write(text: str):
    if _file:
        _file.write(text)
        _file.flush()
