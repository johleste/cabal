"""
Loads RULES.md and approved_targets.txt from the project root.
Both files are gitignored and stay local.

Results are cached after first read — files are only opened once per process.
If RULES.md is missing, a warning is printed and agents run without the rules
preamble. If approved_targets.txt is missing, no targets are considered approved.
"""
import sys
from pathlib import Path

_ROOT = Path(__file__).parent
_RULES_PATH   = _ROOT / "RULES.md"
_TARGETS_PATH = _ROOT / "approved_targets.txt"

_rules_cache:   str | None       = None
_targets_cache: list[str] | None = None
_preamble_cache: str | None      = None


def _load_rules() -> str:
    global _rules_cache
    if _rules_cache is None:
        if _RULES_PATH.exists():
            _rules_cache = _RULES_PATH.read_text().strip()
        else:
            print(
                "[cabal] WARNING: RULES.md not found — operational rules not loaded. "
                "Create RULES.md in the project root.",
                file=sys.stderr,
            )
            _rules_cache = ""
    return _rules_cache


def _load_targets() -> list[str]:
    global _targets_cache
    if _targets_cache is None:
        if _TARGETS_PATH.exists():
            lines = _TARGETS_PATH.read_text().splitlines()
            _targets_cache = [
                l.split("#")[0].strip()
                for l in lines
                if l.strip() and not l.strip().startswith("#")
            ]
        else:
            _targets_cache = []
    return _targets_cache


def preamble() -> str:
    """Return the full rules + approved targets block to prepend to every prompt.
    Cached after first call."""
    global _preamble_cache
    if _preamble_cache is not None:
        return _preamble_cache

    rules = _load_rules()
    targets = _load_targets()

    if not rules:
        _preamble_cache = ""
        return _preamble_cache

    lines = [
        "╔══════════════════════════════════════════════════════════╗",
        "║       OPERATIONAL RULES — MANDATORY, NON-NEGOTIABLE      ║",
        "╚══════════════════════════════════════════════════════════╝",
        "",
        rules,
        "",
    ]

    lines += [
        "╔══════════════════════════════════════════════════════════╗",
        "║                    APPROVED TARGETS                      ║",
        "╚══════════════════════════════════════════════════════════╝",
        "",
    ]
    if targets:
        for t in targets:
            lines.append(f"  {t}")
        lines += [
            "",
            "Any target not listed above is invalid. Scrap and cancel operations",
            "against unlisted targets immediately.",
        ]
    else:
        lines += [
            "  (none — approved_targets.txt is empty)",
            "",
            "No targets are currently approved. No offensive operations are permitted",
            "until targets are added to approved_targets.txt.",
        ]

    lines += [
        "",
        "══════════════════════════════════════════════════════════════",
        "",
    ]

    _preamble_cache = "\n".join(lines)
    return _preamble_cache
