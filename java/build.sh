#!/usr/bin/env bash
# build.sh — compile CabalAdapter and install to tools/Code/
#
# Requires: Java 17+ (uses switch expressions and text blocks)
# Usage: ./java/build.sh

set -euo pipefail

JAVA_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$JAVA_DIR/.." && pwd)"
OUT_DIR="$PROJECT_ROOT/tools/Code"

# ── Checks ────────────────────────────────────────────────────────────────────

if ! command -v javac &>/dev/null; then
    echo "Error: javac not found. Install JDK 17+."
    exit 1
fi

JAVA_VER=$(javac -version 2>&1 | grep -oP '\d+' | head -1)
if [[ "$JAVA_VER" -lt 17 ]]; then
    echo "Error: JDK 17+ required (found $JAVA_VER)."
    exit 1
fi

# ── Compile ───────────────────────────────────────────────────────────────────

echo "Compiling CabalAdapter..."
javac --release 17 "$JAVA_DIR/CabalAdapter.java" -d "$JAVA_DIR"

# ── Package ───────────────────────────────────────────────────────────────────

echo "Packaging jar..."
jar cfe "$JAVA_DIR/CabalAdapter.jar" CabalAdapter -C "$JAVA_DIR" CabalAdapter.class

# ── Install ───────────────────────────────────────────────────────────────────

echo "Installing to $OUT_DIR..."
mkdir -p "$OUT_DIR"
cp "$JAVA_DIR/CabalAdapter.jar" "$OUT_DIR/CabalAdapter.jar"

cat > "$OUT_DIR/adapter" <<'EOF'
#!/usr/bin/env bash
DIR="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
exec java -jar "$DIR/CabalAdapter.jar" "$@"
EOF
chmod +x "$OUT_DIR/adapter"

# ── Done ──────────────────────────────────────────────────────────────────────

echo ""
echo "Installed:"
echo "  $OUT_DIR/adapter"
echo "  $OUT_DIR/CabalAdapter.jar"
echo ""
echo "Commands:"
echo "  adapter py2java <file.py> [-o out.java]"
echo "  adapter java2py <file.java> [-o out.py]"
echo "  adapter call <url> [METHOD] [json_body]"
echo "  adapter probe <url>"
