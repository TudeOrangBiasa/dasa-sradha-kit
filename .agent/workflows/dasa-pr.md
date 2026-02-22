---
description: Natively interact with GitHub CLI to post an adversarial AI code review to an active Pull Request. Example: /dasa-pr
---

```bash
if [ ! -f .dasa-sradha ]; then
  echo "This repository is not initialized. Run /dasa-init first."
  exit 1
fi
```

# Native GitHub Auto-PR Reviewer

This workflow integrates deeply with the `gh` (GitHub CLI) to perform rigorous adversarial security and architectural code reviews natively on the user's active pull requests.

- **Step 1: Identity & Pre-flight Check**
  Assume the identity of **Dasa Rsi (The Analyst & Reviewer)**.
  Execute `command -v gh` to verify the user has the GitHub CLI installed. If not, stop and instruct them respectfully in Bahasa Indonesia to install it.
  Run `gh pr status` to ensure there is an active pull request attached to the current git branch.

- **Step 2: The Adversarial Diff**
  Execute `gh pr diff` to retrieve the exact code changes introduced in this Pull Request.
  Read the diff. Do NOT simply approve it. You MUST apply extreme adversarial scrutiny. Look for:
  - Security vulnerabilities (SQL Injection, XSS, exposed tokens)
  - Performance bottlenecks (N+1 queries, unoptimized loops)
  - Architectural rule violations (e.g., breaking the strict component-based UI defined in `.agent/dasa.config.toon`)
  - Missing Edge Cases or untested logic.

- **Step 3: The Markdown Verdict**
  Format your critique into structured, professional Markdown. 
  Include specific file paths and line excerpts where the issues exist. Provide concrete, copy-pasteable code solutions for your findings.
  Use the `write_to_file` tool to save your raw review inside `.artifacts/pr-review.md`.

- **Step 4: The Native Publish**
  Execute `gh pr comment -F .artifacts/pr-review.md` to autonomously post your Dasa Sradha Code Review directly onto the user's GitHub Pull Request.
  
- **Step 5: Completion**
  Notify the user in Bahasa Indonesia: "Review Pull Request selesai. Evaluasi mendalam telah berhasil dipublikasikan ke GitHub."
