---
description: Remove dasa-sradha-kit from the repository and delete marker file. Example: /dasa-uninstall
---

# /dasa-uninstall

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

- **Step 1: Guard Check**
  Verify that `.dasa-sradha` exists in the repository root.
  If it's missing, **STOP IMMEDIATELY** and tell the user: "This repository is not initialized. Run `/dasa-init` first."
- **Step 2: Uninstall kit**
  Execute the backend script: `~/.gemini/scripts/dasa-uninstall $ARGUMENTS`

> [!NOTE]
> This will delete `.dasa-sradha` and other project-related files.
