---
description: Bootstrap dasa-sradha-kit by creating .dasa-sradha and initializing the repository. Example: /dasa-init my-project "Project description"
---

# Initializing dasa-sradha-kit

- **Step 1: Bootstrap Marker**
  Ensure the marker file `.dasa-sradha` exists. If it's missing, create it using: `touch .dasa-sradha`
- **Step 2: Initialize Repository**
  Execute the backend script: `~/.gemini/scripts/dasa-init $ARGUMENTS`
  
> [!NOTE]
> If `$ARGUMENTS` is empty, the script will prompt you for the project name and description.
