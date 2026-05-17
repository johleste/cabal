"""
LLM output logger. Always-on in Cabal — raw model output is the point.
Set CABAL_QUIET=1 to suppress.
"""
import os
import sys

_QUIET = os.environ.get("CABAL_QUIET", "").strip() not in ("", "0")
_TTY   = sys.stderr.isatty()

_DIM    = "\033[2m"   if _TTY else ""
_CYAN   = "\033[36m"  if _TTY else ""
_YELLOW = "\033[33m"  if _TTY else ""
_GREEN  = "\033[32m"  if _TTY else ""
_RED    = "\033[31m"  if _TTY else ""
_BOLD   = "\033[1m"   if _TTY else ""
_RESET  = "\033[0m"   if _TTY else ""


def _out(text):
    if not _QUIET:
        print(text, file=sys.stderr)


def agent_call(role: str, model: str, prompt_preview: str):
    _out(f"\n{_CYAN}┌─ {role.upper()}  {_DIM}{model}{_RESET}")
    _out(f"{_CYAN}│{_RESET}  {_DIM}{prompt_preview[:120]}{'…' if len(prompt_preview) > 120 else ''}{_RESET}")


def agent_response(role: str, elapsed: float, raw: str):
    _out(f"{_CYAN}│{_RESET}  {_DIM}({elapsed:.1f}s){_RESET}")
    for line in raw.splitlines():
        _out(f"{_CYAN}│{_RESET}  {line}")
    _out(f"{_CYAN}└{'─' * 55}{_RESET}")


def commander_round(round_num: int, raw: str):
    _out(f"\n{_YELLOW}╔═ COMMANDER  round {round_num + 1} {'═' * 36}{_RESET}")
    for line in raw.splitlines():
        _out(f"{_YELLOW}║{_RESET}  {line}")
    _out(f"{_YELLOW}╚{'═' * 55}{_RESET}")


def commander_dispatch(agent: str, prompt: str):
    preview = prompt[:100].replace('\n', ' ')
    _out(f"  {_GREEN}→ {agent}{_RESET}  {_DIM}{preview}{'…' if len(prompt) > 100 else ''}{_RESET}")


def commander_final(text: str):
    _out(f"\n{_BOLD}{_GREEN}╔═ FINAL {'═' * 47}{_RESET}")
    for line in text.splitlines():
        _out(f"{_BOLD}{_GREEN}║{_RESET}  {line}")
    _out(f"{_BOLD}{_GREEN}╚{'═' * 55}{_RESET}\n")


def error(role: str, msg: str):
    _out(f"{_RED}[{role} error]{_RESET} {msg}")
