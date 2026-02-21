#!/bin/bash

# compact-session.sh
# Native execution script for Dasa Patih (The Orchestrator)
# Compresses workspace state into a dense session file.

echo "[Patih Orchestrator] Initiating Context Compaction..."

ARTIFACTS_DIR="${1:-.artifacts}"
MEMORY_FILE="$ARTIFACTS_DIR/session-state.md"

if [ ! -d "$ARTIFACTS_DIR" ]; then
    mkdir -p "$ARTIFACTS_DIR"
fi

echo "# [COMPACTED SESSION STATE]" > "$MEMORY_FILE"
echo "Generation Time: $(date)" >> "$MEMORY_FILE"
echo "" >> "$MEMORY_FILE"
echo "## Core Directives Active" >> "$MEMORY_FILE"
echo "- Max Power Core: ACTIVE" >> "$MEMORY_FILE"
echo "- Strict UI: ACTIVE" >> "$MEMORY_FILE"
echo "" >> "$MEMORY_FILE"

echo "## Workspace Summary" >> "$MEMORY_FILE"
# Summarize task.md if it exists
if [ -f "$ARTIFACTS_DIR/task.md" ]; then
    echo "### Active Tasks (from task.md):" >> "$MEMORY_FILE"
    grep "\- \[ \]" "$ARTIFACTS_DIR/task.md" | head -n 5 >> "$MEMORY_FILE"
else
    echo "No task.md found." >> "$MEMORY_FILE"
fi

echo "" >> "$MEMORY_FILE"
echo "## Current Working Directory Snapshot" >> "$MEMORY_FILE"
ls -la | head -n 10 >> "$MEMORY_FILE"

echo "" >> "$MEMORY_FILE"
echo "[Patih Orchestrator] Compaction complete. Context window may now be theoretically flushed by the LLM."
echo "Compacted state written to: $MEMORY_FILE"
