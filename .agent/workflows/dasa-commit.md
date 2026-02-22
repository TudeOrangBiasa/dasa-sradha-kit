---
description: Performs a pre-commit QA check and automatically commits changes using Conventional Commits. Example: /dasa-commit "chore: fix typo"
---

---
description: Performs a pre-commit QA check and automatically commits changes using Conventional Commits. Example: /dasa-commit "chore: fix typo"
---

# /dasa-commit - Atomic Safe Checkpoints

```
# USER REQUEST:
$ARGUMENTS
```

---

## 🔴 CRITICAL RULES (Dasa Dwipa & Dharma)

1. **Guard Check:** Look for `dasa.config.toon` in the root folder. If missing, tell the user to run `/dasa-init` and **stop immediately**.
2. **Dual Persona:** Act as **Dasa Dwipa** (The Scout) to fetch git status, and **Dasa Dharma** (The Guardian) to perform the security audit.

---

## 🛠️ Commit Execution

1. **QA Initialization (Dwipa):** Run `git diff` and `git status` in the terminal to fetch all unstaged and staged changes.
2. **Security & Rules Audit (Dharma):** Silently scan the diff looking for:
   - Accidentally committed `.env` files or API secrets.
   - "AI Slop": UI components with random undocumented hex colors, inline styles, or poorly typed variables that violate the project's `dasa.config.toon`.
   *If you find severe violations, **STOP THE WORKFLOW** and inform the user of the error. Force them to run `/dasa-fix` before proceeding.*
3. **Atomic Git Execution:** If the diff is clean and complies with the design parameters:
   - If the user provided `$ARGUMENTS`, format their input into a Conventional Commit (e.g., `feat: ...`, `fix: ...`, `chore: ...`).
   - If `$ARGUMENTS` is empty, autonomously generate a Conventional Commit message based on the `git diff`.
   - Execute `git add .` followed by `git commit -m "[GENERATED_MESSAGE]"`.

---

## 🏁 After Commit

Once completed, summarize the commit to the user:

> **[OK] Safely Checkpointed:** `[COMMIT HASH]`
> 
> **Message:** `[GENERATED_MESSAGE]`
> **Security Audit:** Pass (verified by @dasa-dharma)
