"""
LLM output logger. Always-on in Cabal — raw model output is the point.
Set CABAL_QUIET=1 to suppress stderr output; session file is always written.
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


def _err(text):
    if not _QUIET:
        print(text, file=sys.stderr)


def _ses(text):
    try:
        import session
        session.write(text)
    except Exception:
        pass


def agent_call(role: str, model: str, prompt_preview: str):
    header = f"\n┌─ {role.upper()}  {model}\n│  {prompt_preview[:120]}{'…' if len(prompt_preview) > 120 else ''}\n│  "
    _err(f"\n{_CYAN}┌─ {role.upper()}  {_DIM}{model}{_RESET}")
    _err(f"{_CYAN}│{_RESET}  {_DIM}{prompt_preview[:120]}{'…' if len(prompt_preview) > 120 else ''}{_RESET}")
    if not _QUIET:
        print(f"{_CYAN}│{_RESET}  ", end="", flush=True, file=sys.stderr)
    _ses(f"\n┌─ {role.upper()}  {model}\n│  {prompt_preview[:120]}{'…' if len(prompt_preview) > 120 else ''}\n│  ")


def agent_token(token: str):
    if not _QUIET:
        print(token, end="", flush=True, file=sys.stderr)
    _ses(token)


def agent_response_end(role: str, elapsed: float):
    _err("")
    _err(f"{_CYAN}│{_RESET}  {_DIM}({elapsed:.1f}s){_RESET}")
    _err(f"{_CYAN}└{'─' * 55}{_RESET}")
    _ses(f"\n│  ({elapsed:.1f}s)\n└{'─' * 55}\n")


def commander_start(round_num: int):
    _err(f"\n{_YELLOW}╔═ COMMANDER  round {round_num + 1} {'═' * 36}{_RESET}")
    if not _QUIET:
        print(f"{_YELLOW}║{_RESET}  ", end="", flush=True, file=sys.stderr)
    _ses(f"\n╔═ COMMANDER  round {round_num + 1} {'═' * 36}\n║  ")


def commander_token(token: str):
    if not _QUIET:
        print(token, end="", flush=True, file=sys.stderr)
    _ses(token)


def commander_round_end():
    _err("")
    _err(f"{_YELLOW}╚{'═' * 55}{_RESET}")
    _ses(f"\n╚{'═' * 55}\n")


def commander_dispatch(agent: str, prompt: str):
    preview = prompt[:100].replace('\n', ' ')
    _err(f"  {_GREEN}→ {agent}{_RESET}  {_DIM}{preview}{'…' if len(prompt) > 100 else ''}{_RESET}")
    _ses(f"  → {agent}  {preview}{'…' if len(prompt) > 100 else ''}\n")


def error(role: str, msg: str):
    _err(f"{_RED}[{role} error]{_RESET} {msg}")
    _ses(f"[{role} error] {msg}\n")
