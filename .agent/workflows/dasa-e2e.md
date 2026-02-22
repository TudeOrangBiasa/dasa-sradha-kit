---
description: Start an autonomous End-to-End browser test. Example: /dasa-e2e "Test the user login flow on localhost:3000"
---

```bash
if [ ! -f .dasa-sradha ]; then
  echo "This repository is not initialized. Run /dasa-init first."
  exit 1
fi
```

# Native E2E Testing Workflow

This workflow uses Antigravity's native `browser_subagent` to seamlessly execute visual tests without requiring Playwright or Puppeteer dependencies.

- **Step 1: Assumption of Identity**
  You must immediately assume the identity of **Dasa Indra (The QA Investigator)**. Read `~/.gemini/antigravity/skills/dasa-indra/SKILL.md` to load your Persona directives.

- **Step 2: Subagent Execution**
  Read the user's test request provided in `$ARGUMENTS`.
  You MUST use the `browser_subagent` tool. 
  In the `Task` parameter of the `browser_subagent`, write a highly detailed, step-by-step instruction for the subagent to follow (e.g., "Navigate to http://localhost:3000, wait for the DOM to load, click the 'Sign In' button, type 'admin' into the username field...").
  In the `RecordingName` parameter, use a descriptive name like `e2e_login_flow`.

- **Step 3: Verification**
  Once the `browser_subagent` returns, analyze its output to determine if the test passed or failed. 

- **Step 4: Reporting**
  Write a detailed E2E test report into `.artifacts/walkthrough.md` in Bahasa Indonesia. Embed the resulting WebP video of the test using standard markdown: `![E2E Test Recording](/absolute/path/to/.artifacts/e2e_login_flow.webp)`.
  Stop and notify the user: "Pengujian E2E selesai. Rekaman sesi dan hasil analisis dapat dilihat di `.artifacts/walkthrough.md`."
