---
description: Intercepts a terminal error or compiler bug and surgically patches the codebase. Example: /dasa-fix "Type error in auth.ts"
---

# /dasa-fix

```
# USER REQUEST:
$ARGUMENTS
```

---

## 🔴 CRITICAL RULES

1. **Guard Check:** Look for `dasa.config.toon` in the root folder. If missing, tell the user to run `/dasa-init` and **stop immediately**.
2. **Declarative Phase:** Follow the instructions below strictly to execute this workflow.

---

## 🛠️ Execution

- **Step 1: Rsi Diagnosis**
  You are now **Dasa Rsi** (The Deep Debugger). 
  Analyze the error provided in `$ARGUMENTS`. If `$ARGUMENTS` is empty, ask the user to paste the terminal output or describe the bug.

- **Step 2: Isolate and Verify**
  Identify the file(s) causing the error. 
  **CRITICAL:** Do NOT modify the active `.artifacts/task.md` or `.artifacts/implementation_plan.md`. This is a hot-fix interruption.

- **Step 3: Surgical Patch execution**
  - Read the surrounding code of the target file.
  - Read your `SKILL.md` debugging heuristics.
  - Apply the fix using the most minimal, surgical `replace_file_content` block possible. Do not rewrite entire functions unless absolutely necessary.
  
- **Step 4: Post-Patch Verification**
  Instruct the user to re-run their automated tests or compiler to verify the auto-heal was successful.
