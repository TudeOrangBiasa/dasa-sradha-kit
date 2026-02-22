---
description: Perform a stack-agnostic code refactor safely. Example: /dasa-refactor "src/utils.js"
---

# /dasa-refactor

```
# USER REQUEST:
$ARGUMENTS
```

---

## 🔴 CRITICAL RULES

1. **Guard Check:** Read `dasa.config.toon` in the root folder. If missing, tell the user to run `/dasa-init`.
2. **Non-Destructive Target:** Only refactor the specific file, module, or pattern requested in `$ARGUMENTS`.
3. **Mandatory QA Gate:** You must run the project's test suite *before* and *after* the refactor to guarantee zero regressions.

---

## 🛠️ Execution Pipeline

### Phase 1: Dasa Rsi (The Analyst)
1. Read the target block defined in `$ARGUMENTS`.
2. Calculate the Cyclomatic Complexity or code smells.
3. Define exactly *what* needs to be refactored (e.g., "Extract function to reduce nesting" or "Convert to pure functions").

### Phase 2: Dasa Nala / Mpu (The Developer)
1. Execute the refactor.
2. Adhere strictly to the `Methods < 10 lines` and `Classes < 50 lines` rule defined in `.agent/rules/GEMINI.md`.

### Phase 3: Dasa Indra (The QA Investigator)
1. Execute the test command defined in `dasa.config.toon`'s test script.
2. If tests fail, send it back to Phase 2 for fixing. You are not allowed to complete this workflow with failing tests.

---

## 🏁 Expected Output

> **[OK] Refactor Complete:** `$ARGUMENTS`
> **Metrics Improved:** `[Brief reason]`
> 
> The code has been refactored and all tests pass. Run `/dasa-commit` to save.
