#!/bin/bash
# ============================================================================
# Dasa Indra: Deep Grep Helper Script
# ============================================================================
# This script performs a highly optimized, context-aware search of the local
# codebase. It formats the output specifically to prevent AI context bloat
# by returning only the essential snippets with line numbers.
#
# Usage: ./deep-grep.sh "search_term" [optional_directory]
# ============================================================================

SEARCH_TERM="$1"
TARGET_DIR="${2:-.}"

if [ -z "$SEARCH_TERM" ]; then
  echo "Usage: ./deep-grep.sh <search_term> [directory]"
  exit 1
fi

echo "🔍 Dasa Indra Discovery Report"
echo "Searching for: '$SEARCH_TERM' in $TARGET_DIR"
echo "--------------------------------------------------"

# Use ripgrep if available, fallback to standard grep
if command -v rg >/dev/null 2>&1; then
  # ripgrep: Context 2 lines, include line numbers, ignore hidden/vendor
  rg --context 2 --line-number --hidden --glob '!.git' --glob '!node_modules' --glob '!vendor' "$SEARCH_TERM" "$TARGET_DIR"
else
  # standard grep fallback
  grep -rn --context=2 --exclude-dir={.git,node_modules,vendor,dist,build} "$SEARCH_TERM" "$TARGET_DIR"
fi

echo "--------------------------------------------------"
echo "✅ Search complete."
