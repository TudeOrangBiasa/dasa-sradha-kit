---
description: Bootstrap dasa-sradha-kit by creating .dasa-sradha and initializing the repository. Example: /dasa-init my-project "Project description"
---

# /dasa-init

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

- **Step 1: Bootstrap Marker**
  Ensure the marker file `.dasa-sradha` exists. If it's missing, create it using: `touch .dasa-sradha`
- **Step 2: Initialize Repository**
  Execute the backend script: `npx dasa-cli init $ARGUMENTS`
  
> [!NOTE]
> If `$ARGUMENTS` is empty, the script will prompt you for the project name and description.
