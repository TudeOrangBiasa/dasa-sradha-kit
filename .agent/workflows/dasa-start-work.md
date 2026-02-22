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

## 🛠️ Task Execution

1. **Review Memory:** Read `.artifacts/implementation_plan.toon`. If a `.artifacts/task.toon` doesn't exist yet, generate it now by breaking the plan into highly granular, verifiable sub-tasks.
2. **Select Target:** Identify the next uncompleted task from the list based on the user's `$ARGUMENTS`. If `$ARGUMENTS` is empty, pick the first uncompleted task.
3. **Shift Persona:** 
    - Frontend/UI → Assume **Dasa Nala**
    - Backend/Arch → Assume **Dasa Mpu**
    - Testing/QA → Assume **Dasa Indra**
    - Security/Deps → Assume **Dasa Dharma**
    - Docs/README → Assume **Dasa Sastra**
    - Scouting/Search → Assume **Dasa Dwipa**
4. **Execute:** Read the corresponding `.agent/agents/dasa-<name>.md` file silently. Adopt their principles, change into the correct workspace sub-directory, and execute the code changes.

---

## 🏁 After Execution

Once the task is complete, reply to the user exactly like this:

> **[OK] Task Complete:** `[Task Name]`
> **Persona:** `@[dasa-name]`
>
> I have executed the changes. Run `/dasa-commit` to review and save, or `/dasa-start-work` to proceed to the next task in the queue.
