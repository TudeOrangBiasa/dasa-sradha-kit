---
description: Autonomously generate Postman Collections or OpenAPI/Swagger specs for the backend API. Example: /dasa-docs "Generate a Postman collection for the Users API"
---

```bash
if [ ! -f .dasa-sradha ]; then
  echo "This repository is not initialized. Run /dasa-init first."
  exit 1
fi
```

# API Documentator Workflow

This is a collaborative, 3-Persona workflow designed to map out complex backends and generate perfect API specifications.

- **Phase 1: Dasa Dwipa (The Scout)**
  Assume the identity of Dasa Dwipa. Read the `backend` path in `.agent/dasa.config.toon` (under `"workspaces"`).
  Navigate to that directory and sweep the codebase specifically looking for routing configurations (`routes/`, `api.php`, `routes.ts`, etc.) and their corresponding Controller files. Do not modify anything.

- **Phase 2: Dasa Mpu (The Architect)**
  Assume the identity of Dasa Mpu. Analyze the raw routes and controller logic discovered by Dwipa.
  Determine the exact HTTP verbs, request payload schemas, JSON response structures, authentication middleware requirements (e.g., Bearer tokens), and standard error codes (400, 401, 500).

- **Phase 3: Dasa Sastra (The Writer)**
  Assume the identity of Dasa Sastra. Take Mpu's technical breakdown and format it perfectly into a valid `.json` Postman Collection OR a `.yaml` OpenAPI/Swagger specification (based on the user's `$ARGUMENTS`).
  Use the `write_to_file` tool to save the absolute final specification inside the `.artifacts/api-docs/` directory.

- **Phase 4: Completion**
  Stop and tell the user: "API Documentation Complete. You can find the generated specification in `.artifacts/api-docs/` ready to be imported into Postman or Swagger UI."
