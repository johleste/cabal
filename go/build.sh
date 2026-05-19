#!/usr/bin/env bash
# build.sh — compile go-adapter and install to tools/Code/
#
# Requires: Go 1.21+
# Usage: ./go/build.sh

set -euo pipefail

GO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$GO_DIR/.." && pwd)"
OUT_DIR="$PROJECT_ROOT/tools/Code"

# ── Check Go ──────────────────────────────────────────────────────────────────

if ! command -v go &>/dev/null; then
    echo "Error: go not found. Install Go 1.21+ from https://go.dev/dl/"
    exit 1
fi

GO_VER=$(go version | grep -oP 'go\K[0-9]+\.[0-9]+' | head -1)
GO_MAJOR=$(echo "$GO_VER" | cut -d. -f1)
GO_MINOR=$(echo "$GO_VER" | cut -d. -f2)
if [[ "$GO_MAJOR" -lt 1 ]] || [[ "$GO_MAJOR" -eq 1 && "$GO_MINOR" -lt 21 ]]; then
    echo "Error: Go 1.21+ required (found $GO_VER)."
    exit 1
fi

# ── Build ─────────────────────────────────────────────────────────────────────

echo "Building go-adapter..."
mkdir -p "$OUT_DIR"

CGO_ENABLED=0 go build \
    -ldflags="-s -w" \
    -o "$OUT_DIR/go-adapter" \
    "$GO_DIR/cabal_adapter.go"

# ── Done ──────────────────────────────────────────────────────────────────────

echo ""
echo "Installed: $OUT_DIR/go-adapter"
echo ""
echo "Commands:"
echo "  go-adapter py2go   <file.py>   [-o out.go]"
echo "  go-adapter go2py   <file.go>   [-o out.py]"
echo "  go-adapter java2go <file.java> [-o out.go]"
echo "  go-adapter go2java <file.go>   [-o out.java]"
echo "  go-adapter run     <file.go>   [-- args...]"
echo "  go-adapter build   <file.go>   [-o binary]"
echo "  go-adapter call    <url>       [METHOD] [body]"
echo "  go-adapter probe   <url>"
