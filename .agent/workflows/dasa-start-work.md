---
description: Start a focused work session based on a plan. Example: /dasa-start-work "Task 1"
---

---
description: Start a focused work session based on a plan. Example: /dasa-start-work "Task 1"
---

# /dasa-start-work - Auto-Routing Execution

```
# USER REQUEST:
$ARGUMENTS
```

---

## 🔴 CRITICAL RULES (Patih & Sub-Agents)

1. **Guard Check:** Look for `dasa.config.toon` in the root folder. If missing, tell the user to run `/dasa-init` and **stop immediately**.
2. **Auto-Routing:** You are **Dasa Patih (The Orchestrator)**. You must read `.artifacts/task.toon` (or `.md`) and delegate the execution to the correct Persona based on the domain rules in `.agent/rules/GEMINI.md`.
3. **Workspace Awareness:** If `dasa.config.toon` defines a `workspaces` key (e.g., frontend/backend separation), you MUST execute commands inside the correct sub-directory based on the active task.

---

## 🛠️ Task Execution (The Strict Agile Pipeline)

**CRITICAL:** You must follow this strict BMad-inspired pipeline. Personas CANNOT jump out of order.

1. **Phase 1: Dasa Mpu (The Architect)**
   - Patih must assign Mpu to generate `.artifacts/architecture-state.toon` containing the technical design for the active task.
   - **BLOCK:** Dasa Nala cannot start until Mpu's artifact explicitly exists and is reviewed against `GEMINI.md` constraints.

2. **Phase 2: Dasa Nala / Backend Devs (Execution)**
   - Once the architecture TOON is approved, Patih spawns the developers to write the actual code.
   - **Constraint:** Code must conform to Mpu's architecture.

3. **Phase 3: Dasa Indra / Dasa Rsi (QA Gate & Failure Heuristics)**
   - The task is **NOT** complete yet. Patih must execute `.agent/scripts/qa_gate.py` to run the engineering-failures-bible checks natively against the modified files.
   - If tests or scans fail, bounce back to Phase 2.

---

## 🏁 After Execution

Once the task is complete, reply to the user exactly like this:

> **[OK] Task Complete:** `[Task Name]`
> **Persona:** `@[dasa-name]`
>
> I have executed the changes. Run `/dasa-commit` to review and save, or `/dasa-start-work` to proceed to the next task in the queue.
