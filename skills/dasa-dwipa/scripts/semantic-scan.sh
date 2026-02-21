#!/usr/bin/env bash
set -euo pipefail

# ============================================================================
# Dasa Sradha Semantic Engine (Powered by OSGrep)
# Persona: Dasa Dwipa (The Scout)
# ============================================================================
# This script allows Dasa Dwipa to search the codebase by SEMANTIC MEANING 
# rather than exact string matches. It natively wraps `osgrep` to save tokens.
# ============================================================================

query="${1:-}"
max_results="${2:-10}"

if [ -z "$query" ]; then
    echo "Usage: ./semantic-scan.sh \"<abstract search query>\" [max_results]"
    echo "Example: ./semantic-scan.sh \"where does user authentication happen?\""
    exit 1
fi

if ! command -v osgrep >/dev/null 2>&1; then
    echo "[!] CRITICAL ERROR: osgrep is not installed."
    echo "Dasa Dwipa requires 'npm install -g osgrep' for semantic sight."
    exit 1
fi

echo "=========================================================="
echo "Dasa Dwipa Semantic Scan: \"$query\""
echo "=========================================================="
echo "Booting OSGrep local embedding engine..."

# We use --compact false to ensure Dwipa can see the actual code chunks
# We use --scores to show relevance
osgrep search "$query" -m "$max_results" --content true --scores true

echo ""
echo "[+] Semantic Scan Complete."
echo "If results are empty or irrelevant, the logic may not exist yet."
