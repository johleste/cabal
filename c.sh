#!/usr/bin/env bash
# c.sh — Cabal quick-access shell
#
# Usage:
#   ./c.sh run "task"              Commander orchestrates agents
#   ./c.sh ask "question"          Commander answers directly
#   ./c.sh research "topic"        Direct to Researcher
#   ./c.sh code "task"             Direct to Coder
#   ./c.sh recon "scenario"        Direct to Recon
#   ./c.sh analyse "task"          Direct to Analyst
#   ./c.sh quiet <cmd> [args]      Suppress LLM logging (CABAL_QUIET=1)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="${CABAL_PYTHON:-python3}"

CMD="${1:-help}"
shift || true

case "$CMD" in
    run|ask|research|code|recon|analyse|pull)
        exec "$PYTHON" "$SCRIPT_DIR/cabal.py" "$CMD" "$@"
        ;;

    quiet)
        CABAL_QUIET=1 exec "$PYTHON" "$SCRIPT_DIR/cabal.py" "$@"
        ;;

    help|--help|-h)
        cat "$CABAL_DIR/README.md"
        ;;

    *)
        echo "c.sh: unknown command '$CMD'. Run ./c.sh help for usage." >&2
        exit 1
        ;;
esac
