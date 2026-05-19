#!/usr/bin/env bash
# rebuild.sh — rebuild all Cabal adapters and install to tools/Code/
#
# Usage: ./rebuild.sh

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
failed=0

run() {
    local name="$1"
    local script="$2"
    echo ""
    echo "── $name ──────────────────────────────────────────────"
    if bash "$script"; then
        echo "✓ $name"
    else
        echo "✗ $name (failed)"
        failed=$((failed + 1))
    fi
}

echo "Cabal — rebuilding all adapters"
echo "════════════════════════════════════════"

run "Java adapter" "$ROOT/java/build.sh"
run "Go adapter"   "$ROOT/go/build.sh"

echo ""
echo "════════════════════════════════════════"
if [[ $failed -eq 0 ]]; then
    echo "All adapters built successfully."
    echo ""
    echo "Installed in tools/Code/:"
    ls -1 "$ROOT/tools/Code/" 2>/dev/null | sed 's/^/  /'
else
    echo "$failed adapter(s) failed to build."
    exit 1
fi
