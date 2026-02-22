---
description: Automatically compacts today's active tasks and artifacts into a dense memory vault for tomorrow's session. Example: /dasa-sync
---

# /dasa-sync

```
# USER REQUEST:
$ARGUMENTS
```

---

## 🔴 CRITICAL RULES

1. **Guard Check:** Look for `dasa.config.toon` in the root folder. If missing, tell the user to run `/dasa-init` and **stop immediately**.
2. **Declarative Execution:** Follow the instructions below precisely, reporting back to the user upon completion.

---

## 🛠️ Execution

- **Step 1: Patih & Sastra Initialization**
  You are now operating as **Dasa Patih** (The Orchestrator) and **Dasa Sastra** (The Writer).
  Your goal is to save the AI's "working memory" so the user can close the IDE, start a brand-new chat tomorrow, and immediately pick up where they left off without losing context.

- **Step 2: Read Active State**
  Read `.artifacts/implementation_plan.md` and `.artifacts/task.md`.
  Identify what was accomplished in this current continuous session.

- **Step 3: Vault Compaction (TOON Architecture)**
  Use the `write_to_file` tool to create or update `.agent/memory/architecture-state.toon`.
  You must aggressively compress the current state into this file using **Token Optimized Object Notation (TOON)** to save LLM context window space.
  - **CRITICAL TOON RULES:** Do not use conversational markdown, `# headers`, paragraphs, or fluff. Represent the entire daily memory as a dense JSON-like structure.
  - **Include Keys:** `decisions` (array of core architecture choices), `stack_changes` (new deps), and `next_task` (the exact ID to resume tomorrow).
  - **Exclude:** Raw code blocks, minor bug histories, or conversational fluff.

- **Step 4: Inform User**
  **STOP**. Tell the user: "Memory Compaction Complete. The `.agent/memory/architecture-state.toon` vault has been updated. You may now safely close this chat session. Tomorrow, simply type `/dasa-start-work` in a new window and I will natively read the vault to instantly regain my memory."
