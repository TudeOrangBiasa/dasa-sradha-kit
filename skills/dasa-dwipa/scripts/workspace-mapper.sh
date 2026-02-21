#!/bin/bash

# workspace-mapper.sh
# Native execution script for Dasa Dwipa (The Scout)
# Generates a clean, depth-limited ASCII tree of the workspace, ignoring common slop vectors.

MAX_DEPTH="${1:-3}"

if ! command -v tree &> /dev/null; then
    echo "Error: 'tree' command not found. Falling back to find..."
    find . -maxdepth $MAX_DEPTH -not -path '*/\.*' | grep -v 'node_modules\|dist\|build\|.next\|.artifacts' | sed -e "s/[^-][^\/]*\// |/g" -e "s/|\([^ ]\)/|-\1/"
else
    tree -L $MAX_DEPTH -I "node_modules|dist|build|.next|.git|.artifacts|.vscode" --dirsfirst
fi

echo -e "\n[Dwipa Scout] Architectural map generated successfully up to depth $MAX_DEPTH."
