---
description: Performs a pre-commit QA check and automatically commits changes using Conventional Commits. Example: /dasa-commit "chore: fix typo"
---

```bash
if [ ! -f .dasa-sradha ]; then
  echo "This repository is not initialized. Run /dasa-init first."
  exit 1
fi
```

# Atomic Safe Checkpoints Workflow

- **Step 1: QA Initialization**
  You are now **Dasa Dwipa** (The QA Reviewer).
  Run `git diff` and `git status` in the terminal to fetch all unstaged and staged changes.

- **Step 2: Pre-Commit Security & Rules Audit**
  Assume the identity of **Dasa Dharma** (The Security Guardian).
  Silently scan the diff specifically looking for:
  - Accidentally committed `.env` files or API secrets.
  - "AI Slop": UI components with random undocumented hex colors, inline styles, or poorly typed variables that violate the project's `dasa.config.yaml`.
  
  If you find severe violations, **STOP THE WORKFLOW** and inform the user of the error. Force them to run `/dasa-fix` before proceeding.

- **Step 3: Atomic Git Execution**
  If the diff is clean and complies with the design parameters:
  - If the user provided `$ARGUMENTS`, format their input into a Conventional Commit (e.g., `feat: ...`, `fix: ...`, `chore: ...`).
  - If `$ARGUMENTS` is empty, autonomously generate a Conventional Commit message based on the `git diff`.
  
  Execute `git add .` followed by `git commit -m "[GENERATED_MESSAGE]"`.

- **Step 4: Completion Output**
  Confirm to the user that Dasa Sradha has safely checkpointed the `.git` tree.
