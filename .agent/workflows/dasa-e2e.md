---
description: Start an autonomous End-to-End browser test. Example: /dasa-e2e "Test the user login flow on localhost:3000"
---

---
description: Start an autonomous End-to-End browser test. Example: /dasa-e2e "Test the user login flow on localhost:3000"
---

# /dasa-e2e - Native E2E Testing

```
# USER REQUEST:
$ARGUMENTS
```

---

## 🔴 CRITICAL RULES (Dasa Indra)

1. **Guard Check:** Look for `dasa.config.toon` in the root folder. If missing, tell the user to run `/dasa-init` and **stop immediately**.
2. **Native Tooling ONLY:** This workflow relies exclusively on Antigravity's native `browser_subagent` to execute visual tests. Do not attempt to install Playwright or Puppeteer inside the terminal.
3. **Identity:** Assume the identity of **Dasa Indra (The QA Investigator)**. Apply your Max Power heuristics automatically.

---

## 🛠️ Execution

1. **Read Request:** Analyze the user's test scenario provided in `$ARGUMENTS`.
2. **Subagent Execution:** You MUST use the `browser_subagent` tool.
   - In the `Task` parameter of the `browser_subagent`, write a highly detailed, step-by-step instruction for the subagent to follow (e.g., "Navigate to http://localhost:3000, wait for the DOM to load, click the 'Sign In' button, type 'admin' into the username field...").
   - In the `RecordingName` parameter, use a descriptive name like `e2e_login_flow`.
3. **Verification:** Once the `browser_subagent` returns, analyze its output/the DOM state to determine if the test passed or failed.

---

## 📦 Expected Output

Write a detailed E2E test report into `.artifacts/walkthrough.md` in Bahasa Indonesia. Embed the resulting WebP video of the test using standard markdown syntax.

> **[✅/❌] Pengujian E2E Selesai:**
> Rekaman sesi dan analisis kegagalan/keberhasilan telah dicatat di `.artifacts/walkthrough.md`.
