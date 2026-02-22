---
description: Implement a complete vertical feature across the stack. Example: /dasa-feature "User Login"
---

# /dasa-feature

```
# USER REQUEST:
$ARGUMENTS
```

---

## 🔴 CRITICAL RULES

1. **Guard Check:** Read `dasa.config.toon` in the root folder. If missing, tell the user to run `/dasa-init`.
2. **Stack Detection (Agnostic Flow):** You must read `dasa.config.toon` to determine the exact frameworks, stack, and language you are writing code for. Do not assume React or Node unless explicitly stated in the config.
3. **Agile Integrity:** You must execute this entire workflow following the rigid Mpu -> Nala -> Indra pipeline.

---

## 🛠️ Execution Pipeline

### Phase 1: Dasa Mpu (The Architect)
1. Read the user's `$ARGUMENTS`.
2. Generate an architectural TOON map `.artifacts/architecture-state.toon` defining the interface, classes, methods, and required files for this feature based explicitly on the tech stack defined in `dasa.config.toon`.

### Phase 2: Dasa Nala (The Developer)
1. You are blocked until Phase 1 is complete.
2. Read `.artifacts/architecture-state.toon`.
3. Read the senior constraints from `.agent/rules/GEMINI.md` (Methods < 10 lines).
4. Implement the feature exactly as Mpu designed it.

### Phase 3: Dasa Indra (The QA Investigator)
1. You are blocked until Phase 2 is complete.
2. Verify the implementation aligns with `dasa.config.toon` (e.g., did they use the right testing framework?).
3. Output the final success message.

---

## 🏁 Expected Output

> **[OK] Feature Implementation Complete:** `$ARGUMENTS`
> **Stack Used:** `[Detected from dasa.config.toon]`
> 
> The feature has been developed and passed QA. Run `/dasa-commit` to save.
