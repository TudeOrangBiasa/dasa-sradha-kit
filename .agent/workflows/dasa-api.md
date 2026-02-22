---
description: Generate a stack-agnostic API endpoint. Example: /dasa-api "GET /users"
---

# /dasa-api

```
# USER REQUEST:
$ARGUMENTS
```

---

## 🔴 CRITICAL RULES

1. **Guard Check:** Read `dasa.config.toon` in the root folder. If missing, tell the user to run `/dasa-init`.
2. **Framework Detection:** You MUST respect the `backend` field in `dasa.config.toon`. If the backend is Express, generate Express routes. If it is Spring Boot, generate Java controllers. If it is Axum, generate Rust handlers.
3. **Question-Driven Validation:** If the user request `$ARGUMENTS` is too vague (e.g. missing HTTP method or payload structure), do NOT guess. Ask clarifying questions first.

---

## 🛠️ Execution Pipeline

### Phase 1: Clarification (Dasa Patih)
- If the required API schema (request body, response body, HTTP codes) is not defined in `$ARGUMENTS`, pause and ask the user to provide it. If provided, proceed.

### Phase 2: Implementation (Dasa Mpu)
- Implement the controller/handler, the service layer, and the data-access layer for the API route.
- Strictly follow `.agent/rules/GEMINI.md` logic (Clean Architecture).

### Phase 3: Documentation (Dasa Sastra)
- Assume Dasa Sastra. 
- Append the new route to the project's Swagger/Postman JSON or general Markdown API docs.

---

## 🏁 Expected Output

> **[OK] API Endpoint Generated:** `$ARGUMENTS`
> **Controller Path:** `[Path to file]`
> 
> The API has been generated. Run `/dasa-commit` to save.
