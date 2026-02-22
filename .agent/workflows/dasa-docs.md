---
description: Autonomously generate Postman Collections or OpenAPI/Swagger specs for the backend API. Example: /dasa-docs "Generate a Postman collection for the Users API"
---

---
description: Autonomously generate Postman Collections or OpenAPI/Swagger specs for the backend API. Example: /dasa-docs "Generate a Postman collection for the Users API"
---

# /dasa-docs - API Documentation Generator

```
# USER REQUEST:
$ARGUMENTS
```

---

## 🔴 CRITICAL RULES (Multiple Personas)

1. **Guard Check:** Look for `dasa.config.toon` in the root folder. If missing, tell the user to run `/dasa-init` and **stop immediately**.
2. **Collaborative Orchestration:** This command requires swapping between 3 distinct Dasa Personas (Dwipa, Mpu, Sastra) to effectively document the system.

---

## 🛠️ Execution

1. **Scouting (Dasa Dwipa):** 
   - Read the `backend` path in `.agent/dasa.config.toon` (under `"workspaces"`).
   - Navigate to that directory and sweep the codebase looking for routing configurations (`routes/`, `api.php`, `routes.ts`, etc.) and corresponding Controller files. Do not modify anything.

2. **Analysis (Dasa Mpu):** 
   - Analyze the raw routes and controller logic discovered by Dwipa.
   - Determine the exact HTTP verbs, request payload schemas, JSON response structures, authentication middleware requirements (e.g., Bearer tokens), and standard error codes (400, 401, 500).

3. **Writing (Dasa Sastra):** 
   - Based on the user's `$ARGUMENTS`, format Mpu's technical breakdown into a valid `.json` Postman Collection OR a `.yaml` OpenAPI/Swagger specification.
   - Use the `write_to_file` tool to save the absolute final specification inside the `.artifacts/api-docs/` directory.

---

## 📦 Expected Output

Once the files are written, stop and reply to the user exactly like this:

> **[✅] API Documentation Complete.** 
> You can find the generated specification in `.artifacts/api-docs/` ready to be imported into Postman or Swagger UI.
