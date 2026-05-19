#!/usr/bin/env bash
# pull_models.sh — download all Ollama models required by Cabal
#
# By default models are stored in ~/.ollama/models.
# To store them locally in this folder instead:
#
#   OLLAMA_MODELS="$(pwd)/models" ./pull_models.sh
#
# Ollama must be installed and running before this script is called.
# Install: https://ollama.ai
# Start:   ollama serve

set -euo pipefail

# ── Models ────────────────────────────────────────────────────────────────────
# Keep in sync with config.py MODELS dict.

declare -A MODELS=(
    ["deepseek-r1:8b"]="Commander — orchestration and chain-of-thought reasoning"
    ["deepseek-coder-v2:latest"]="Researcher + Coder — technical research and code generation"
    ["wizard-vicuna-uncensored:latest"]="Recon — red team reasoning, no refusals"
    ["dolphin-llama3:8b"]="Analyst — synthesis and report writing"
)

# ── Checks ────────────────────────────────────────────────────────────────────

if ! command -v ollama &>/dev/null; then
    echo "Error: ollama not found in PATH."
    echo "Install from https://ollama.ai and re-run this script."
    exit 1
fi

if ! ollama list &>/dev/null 2>&1; then
    echo "Error: Ollama service is not responding."
    echo "Start it with: ollama serve"
    exit 1
fi

# ── Optional local model directory ───────────────────────────────────────────

if [[ -n "${OLLAMA_MODELS:-}" ]]; then
    mkdir -p "$OLLAMA_MODELS"
    echo "Using local model directory: $OLLAMA_MODELS"
    export OLLAMA_MODELS
fi

# ── Pull ──────────────────────────────────────────────────────────────────────

echo ""
echo "Cabal — pulling required Ollama models"
echo "════════════════════════════════════════"

failed=0
for model in "${!MODELS[@]}"; do
    echo ""
    echo "  ${model}"
    echo "  ${MODELS[$model]}"
    echo "  ──────────────────────────────────────"
    if ollama pull "$model"; then
        echo "  ✓ done"
    else
        echo "  ✗ failed"
        failed=$((failed + 1))
    fi
done

echo ""
echo "════════════════════════════════════════"
if [[ $failed -eq 0 ]]; then
    echo "All models pulled successfully."
    echo "Run 'cabal help' to get started."
else
    echo "${failed} model(s) failed. Re-run this script to retry."
    exit 1
fi
