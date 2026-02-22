---
description: Create a new execution plan for dasa-sradha-kit. Example: /dasa-plan "Refactor the authentication module"
---

---
description: Create a compressed execution plan for dasa-sradha-kit. Example: /dasa-plan "Refactor the authentication module"
---

# /dasa-plan - System Architecture Planning

```
# USER REQUEST:
$ARGUMENTS
```

---

## 🔴 CRITICAL RULES (Dasa Mpu)

1. **Guard Check First:** Look for `dasa.config.toon` in the root folder. If missing, tell the user to run `/dasa-init` and **stop immediately**.
2. **NO CODE WRITING:** This command generates the `.artifacts/implementation_plan.toon` ONLY. You must not write any project code.
3. **Format Mandate:** Use pure, whitespace-compressed TOON format in the `.toon` artifact (or `.md` containing only TOON syntax). No conversational paragraphs.
4. **Persona Assignment:** Every task in the plan MUST have an assigned `domain_persona` (e.g., `dasa-nala`, `dasa-dharma`) based on the routing definitions in `GEMINI.md`.

---

## 🛠️ Task Execution

Act as **Dasa Mpu (The Master Architect)**. 

1. Read the user's `$ARGUMENTS`. If empty, ask the user what they want to build via the chat interface.
2. Analyze the workspace and current tech stack as defined in `dasa.config.toon`.
3. Create a highly compressed plan file using the `write_to_file` tool (set `IsArtifact: true`).

**Required TOON Keys:**
- `goal` (String)
- `tasks` (Array of objects: `id`, `desc`, `domain_persona`)
- `verification_tests` (Array of strings)

---

## 📦 Expected Output

| Deliverable | Location |
|-------------|----------|
| Execution Plan | `.artifacts/implementation_plan.toon` |

---

## 🏁 After Planning

Once the file is generated, reply to the user exactly like this:

> **[OK] Plan Generated:** `.artifacts/implementation_plan.toon`
>
> Review the steps above. If everything looks correct, run `/dasa-start-work` and I will automatically coordinate the Dasa Personas to execute the plan.
