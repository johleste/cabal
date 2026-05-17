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
    run|ask|research|code|recon|analyse)
        exec "$PYTHON" "$SCRIPT_DIR/cabal.py" "$CMD" "$@"
        ;;

    quiet)
        CABAL_QUIET=1 exec "$PYTHON" "$SCRIPT_DIR/cabal.py" "$@"
        ;;

    help|--help|-h)
        cat <<'EOF'
c.sh — Cabal multi-agent AI shell

  ./c.sh run "task"         Commander orchestrates agents to complete a task
  ./c.sh ask "question"     Commander answers directly (no agent dispatch)
  ./c.sh research "topic"   Direct to Researcher (deepseek-coder-v2)
  ./c.sh code "task"        Direct to Coder (deepseek-coder-v2)
  ./c.sh recon "scenario"   Direct to Recon (wizard-vicuna-uncensored)
  ./c.sh analyse "task"     Direct to Analyst (dolphin-llama3)
  ./c.sh quiet <cmd> [args] Run any command with LLM logging suppressed

LLM output is logged to stderr by default. Set CABAL_QUIET=1 to suppress.
EOF
        ;;

    *)
        echo "c.sh: unknown command '$CMD'. Run ./c.sh help for usage." >&2
        exit 1
        ;;
esac
