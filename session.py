"""
Session manager — writes all run output to sessions/<timestamp>_<cmd>.txt
incrementally, flushed per token, so you can read it mid-run.
"""
import os
import sys
from datetime import datetime
from pathlib import Path
from config import SESSION_DIR

_file = None
_path = None


def start(cmd: str, task: str) -> Path:
    global _file, _path
    Path(SESSION_DIR).mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    slug = cmd.replace(" ", "_")[:32]
    _path = Path(SESSION_DIR) / f"{stamp}_{slug}.txt"
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
