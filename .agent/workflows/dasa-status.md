---
description: Show the current status of all plans and work sessions. Example: /dasa-status
---

```bash
if [ ! -f .dasa-sradha ]; then
  echo "This repository is not initialized. Run /dasa-init first."
  exit 1
fi
```

# Status Workflow

- **Step 1: Guard Check**
  Verify that `.dasa-sradha` exists in the repository root.
  If it's missing, **STOP IMMEDIATELY** and tell the user: "This repository is not initialized. Run `/dasa-init` first."
- **Step 2: Check Status**
  Act as Kala (The Project Manager) for the Dasa Sradha system.
  Read the active plan in `.artifacts/implementation_plan.toon`, the checklist in `.artifacts/task.toon`, and any test outputs in `.artifacts/walkthrough.md`.
  
  Provide a concise, formatted markdown summary to the user that includes:
  - **Currently Active Task:** What is being worked on right now.
  - **Recent Progress:** What was recently completed according to the logs.
  - **Next Steps:** What is outstanding in the plan.
  - **Blockers:** Any issues or dependencies currently holding up progress.
