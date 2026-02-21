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
- **Step 2: Auto-Routing Session**
  Review the active planning document at `.artifacts/implementation_plan.toon` (or `.md`). 
  If `.artifacts/task.toon` does not exist, use the `write_to_file` tool to generate it, breaking the plan down into granular TOON syntax subtasks. Do not use conversational markdown or checkboxes.
  
  Read the next uncompleted task in `task.toon`. Based on the task's domain, you MUST automatically assume the identity of the most relevant Persona:
  - **Frontend / UI / Styling:** Assume **Dasa Nala**.
  - **Architecture / Backend / Complex Logic:** Assume **Dasa Mpu**.
  - **Testing / QA / CI:** Assume **Dasa Indra**.
  - **Security / Dependency Config:** Assume **Dasa Dharma**.
  - **Documentation / README:** Assume **Dasa Sastra**.
  - **Data Collection / Web Search:** Assume **Dasa Widya**.

  **CRITICAL GUARDRAIL:** Before you write a single line of code for this task, you MUST silently read the exact `SKILL.md` rules corresponding to your chosen persona (e.g. `~/.gemini/antigravity/skills/dasa-nala/SKILL.md`) to apply their specific Max Power heuristics!
  
  Proceed to execute the task fully as that persona.
