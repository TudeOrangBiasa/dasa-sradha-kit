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
  
  Create a new detailed plan using explicitly the `write_to_file` tool with the `IsArtifact` flag set to `true`.
  The file MUST be named `.artifacts/implementation_plan.md`.
  
  Use the standard Antigravity plan format:
  1. **Background/Context:** Why are we doing this?
  2. **Scope/Steps:** What exactly needs to be done?
  3. **Verification Plan:** A checklist of what defines done.

- **Step 3: Auto-Routing Handover**
  **STOP IMMEDIATELY POST-PLANNING**. Present the plan to the user for review. 
  Crucially, you must explicitly instruct the user: "If the plan looks good, simply run `/dasa-start-work` and the Orchestrator will automatically route these tasks to the correct Personas for execution."
  DO NOT START WRITING ANY CODE OR EXECUTING TASKS. Wait for the user to invoke `/dasa-start-work`.
