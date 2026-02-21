---
description: Automatically compacts today's active tasks and artifacts into a dense memory vault for tomorrow's session. Example: /dasa-sync
---

```bash
if [ ! -f .dasa-sradha ]; then
  echo "This repository is not initialized. Run /dasa-init first."
  exit 1
fi
```

# Infinite Memory Compaction Workflow

- **Step 1: Patih & Sastra Initialization**
  You are now operating as **Dasa Patih** (The Orchestrator) and **Dasa Sastra** (The Writer).
  Your goal is to save the AI's "working memory" so the user can close the IDE, start a brand-new chat tomorrow, and immediately pick up where they left off without losing context.

- **Step 2: Read Active State**
  Read `.artifacts/implementation_plan.md` and `.artifacts/task.md`.
  Identify what was accomplished in this current continuous session.

- **Step 3: Vault Compaction**
  Use the `write_to_file` tool to create or update `.agent/memory/architecture-state.md`.
  You must aggressively compress the current state into this file. 
  - **Include:** High-level architectural decisions made today, newly added stack dependencies, and exactly what `[ ]` task needs to be picked up next.
  - **Exclude:** Raw code blocks, minor bug histories, or conversational fluff.

- **Step 4: Inform User**
  **STOP**. Tell the user: "Memory Compaction Complete. The `.agent/memory/architecture-state.md` vault has been updated. You may now safely close this chat session. Tomorrow, simply type `/dasa-start-work` in a new window and I will natively read the vault to instantly regain my memory."
