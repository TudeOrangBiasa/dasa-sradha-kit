---
description: Autonomously scans an undocumented or forked repository, determines the tech stack, configures Dasa Sradha, and updates the Memory Vault. Example: /dasa-assimilate
---

```bash
if [ ! -f .dasa-sradha ]; then
  echo "This repository is not initialized. Run /dasa-init first."
  exit 1
fi
```

# The Assimilation Protocol

- **Step 1: The Codebase Sweep**
  You are now **Dasa Dwipa** (The Scout). 
  Run commands like `find . -maxdepth 2` to identify the core architecture and configuration files (e.g., `package.json`, `composer.json`, `go.mod`, `.env.example`, `docker-compose.yml`, `.ddev/config.yaml`).
  Read the contents of these configuration files to determine the exact tech stack, database, and frameworks used.

- **Step 2: Environment Triage (DDEV vs Native)**
  If you discover a `.ddev/config.yaml` file, you MUST formulate a strict rule for the Personas:
  "DDEV Environment Detected. All backend commands (PHP, Laravel, MySQL, Composer) MUST be executed through the container using `ddev exec` or `ddev mysql`. However, Node.js commands (like `npm run dev`) must remain NATIVE on the host machine."

- **Step 3: Configuration Injection**
  Assume the identity of **Dasa Nala** (The Builder).
  Use the `write_to_file` tool to overwrite the `.agent/dasa.config.toon` file (or create it if it doesn't exist). 
  Update the `project`, `stack`, and `context_rules` sections to perfectly match what Dwipa discovered.
  Ensure the DDEV vs Native execution rule from Step 2 is explicitly written into the `context_rules` array.

- **Step 4: Memory Initialization**
  Assume the identity of **Dasa Sastra** (The Writer).
  Generate a high-level summary of the repository's architecture, key folders, and state.
  Save this summary strictly to `.agent/memory/architecture-state.toon`.

- **Step 5: Initialization Complete**
  Stop and notify the user: "Assimilation complete. I have automatically configured `.agent/dasa.config.toon` to match this project's native stack, and established the `.agent/memory/architecture-state.toon` vault. You may now run `/dasa-start-work` or `/dasa-plan`."
