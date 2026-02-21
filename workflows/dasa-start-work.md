---
description: Start a focused work session based on a plan. Example: /dasa-start-work "Task 1"
---

```bash
if [ ! -f .dasa-sradha ]; then
  echo "This repository is not initialized. Run /dasa-init first."
  exit 1
fi
```

# Start Work Workflow

- **Step 1: Guard Check**
  Verify that `.dasa-sradha` exists in the repository root.
  If it's missing, **STOP IMMEDIATELY** and tell the user: "This repository is not initialized. Run `/dasa-init` first."
- **Step 2: Initialize Session**
  Review the active planning document at `.artifacts/implementation_plan.md`. 
  Based on the requested `$ARGUMENTS`:
  - Act as Nala (The Orchestrator).
  - Explicitly use the `write_to_file` tool with `IsArtifact` set to `true` to generate or update `.artifacts/task.md`.
  - Break down the implementation plan into granular, checkable `[ ]` subtasks inside the `task.md` file.
  
  If `$ARGUMENTS` is empty, prompt the user for what feature from the plan they want to break down into tasks.
