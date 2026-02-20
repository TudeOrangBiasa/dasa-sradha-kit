---
description: Remove dasa-sradha-kit from the repository and delete marker file. Example: /dasa-uninstall
---

```bash
if [ ! -f .dasa-sradha ]; then
  echo "This repository is not initialized. Run /dasa-init first."
  exit 1
fi
```

# Uninstall Workflow

- **Step 1: Guard Check**
  Verify that `.dasa-sradha` exists in the repository root.
  If it's missing, **STOP IMMEDIATELY** and tell the user: "This repository is not initialized. Run `/dasa-init` first."
- **Step 2: Uninstall kit**
  Execute the backend script: `~/.gemini/scripts/dasa-uninstall $ARGUMENTS`

> [!NOTE]
> This will delete `.dasa-sradha` and other project-related files.
