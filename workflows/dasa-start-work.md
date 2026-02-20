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
  Review the active planning documents in `.artifacts/plans/`. 
  Based on what the user specified in `$ARGUMENTS` (e.g., a task number or feature description):
  - Identify the relevant files that need to be changed.
  - Set up the environment or open the necessary context.
  - Create or append to a log entry in `.artifacts/notepads/session.md` indicating that work on this task has officially started, including the timestamp.
  
  If `$ARGUMENTS` is empty, prompt the user for which task from the current plan they want to tackle.
