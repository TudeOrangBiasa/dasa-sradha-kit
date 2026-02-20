---
description: Create a new execution plan for dasa-sradha-kit. Example: /dasa-plan "Refactor the authentication module"
---

```bash
if [ ! -f .dasa-sradha ]; then
  echo "This repository is not initialized. Run /dasa-init first."
  exit 1
fi
```

# Planning Workflow

- **Step 1: Guard Check**
  Verify that `.dasa-sradha` exists in the repository root.
  If it's missing, **STOP IMMEDIATELY** and tell the user: "This repository is not initialized. Run `/dasa-init` first."
- **Step 2: Generate Plan**
  Act as a Senior System Analyst for the Dasa Sradha system.
  Read the user's prompt provided in `$ARGUMENTS`. If `$ARGUMENTS` is empty, ask the user what they want to plan.
  
  Create a new detailed plan document inside `.artifacts/plans/` using the following format:
  1. **Background/Context:** Why are we doing this?
  2. **Scope/Steps:** What exactly needs to be done?
  3. **Acceptance Criteria:** A checklist of what defines done.
  
  Make sure the filenames are descriptive and timestamped or versioned appropriately (e.g., `plan-auth-refactor-v1.md`).
