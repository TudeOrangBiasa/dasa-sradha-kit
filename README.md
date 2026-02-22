# Dasa Sradha Kit for Antigravity

The **Dasa Sradha Kit** is a native, zero-dependency agentic framework designed exclusively for the **Antigravity IDE**. It splits complex software workflows into 10 distinct AI Personas, orchestrating massive full-stack builds without exploding your LLM context window.

## Key Features

- **Zero-Command Orchestration**: No need to memorize slash commands. Just prompt naturally (e.g., *"Build me a blog"*), and the P0 GEMINI.md constraints will intercept and autonomously route the task into the Dasa pipeline.
- **Visual-to-Code Workflow**: Drop Figma mockups or PNGs into `.design-memory/reference/`. Dasa Mpu analyzes them, and local native scripts compress the visual data into text tokens for Dasa Nala to build.
- **10 Persona-Based Orchestration**: Distinct AI agents (Scout, Architect, Builder, etc.) with strict Agile handoffs.
- **Zero-Dependency Native Execution**: Uses Antigravity's built-in `browser_subagent` for E2E testing and `run_command` for execution. No Playwright, no heavy NPM packages.
- **5-Sector TOON Long-Term Memory**: Compresses chat histories into `episodic`, `semantic`, `procedural`, `emotional`, and `reflective` vaults for infinite context without token bloat.
- **17 Native Python Scripts**: Cross-platform tooling for QA gates, AST-based context mapping, security scanning, and design system generation — all zero-dependency.
- **Senior Engineer Constraints**: Hard limits enforcing Methods < 10 lines and Classes < 50 lines across all Personas.
- **Stack-Agnostic Workflows**: Framework detection via `dasa.config.toon` — works with React, Go, Python, Rust, or any stack.

---

## Prerequisites

- **Antigravity IDE**: You must be running the Antigravity editor.
- **Node.js**: Version 18+ (for the CLI).
- **Python 3**: Version 3.8+ (for the native scripts).
- **Git**: Required for version control and PR workflows.
- **osgrep** (Optional): `npm install -g osgrep` for enhanced semantic search.

---

## Getting Started

### Option A: NPX (Recommended)

```bash
npx dasa-sradha-kit init
```

### Option B: Global Install

```bash
npm install -g dasa-sradha-kit
dasa-sradha init
```

### Option C: Clone & Init

```bash
git clone https://github.com/TudeOrangBiasa/dasa-sradha-kit.git
cd dasa-sradha-kit
npm link
dasa-sradha init
```

This generates your `dasa.config.toon`, builds the `.agent/` mechanics folder, and creates the `.artifacts/` memory vault.

---

## Architecture Overview

```
<workspace-root>/
├── .agent/                    ← Read-Only Mechanics (installed by dasa-cli)
│   ├── agents/                ← 10 Dasa Personas
│   ├── rules/GEMINI.md        ← P0 global constraints (SOLID, TDD, Methods < 10)
│   ├── skills/                ← Modular domain resources (engineering failures, etc.)
│   ├── workflows/             ← 16 Slash Commands
│   └── scripts/               ← 17 Python scripts (zero-dependency)
├── .artifacts/                ← Read-Write Memory (active tasks, TOON vaults)
├── .design-memory/            ← Long-term UI specs
├── dasa.config.toon           ← Your tech stack configuration
└── bin/
    ├── cli.js                 ← `dasa` CLI entry point
    └── dasa-cli.js            ← `dasa-cli` orchestrator dashboard
```

---

## Available Commands

| Command | Description |
|:---|:---|
| `/dasa-plan` | Break down a feature request into strict phase-gated tasks. |
| `/dasa-start-work` | Execute the plan via the rigid Agile pipeline: Mpu → Nala → Indra. |
| `/dasa-feature` | Implement a complete vertical feature (stack-agnostic). |
| `/dasa-api` | Generate API endpoints (framework-agnostic via `dasa.config.toon`). |
| `/dasa-refactor` | Safe refactoring with mandatory QA gate. |
| `/dasa-status` | Display current progress. |
| `/dasa-commit` | QA gate + atomic Conventional Commit. |
| `/dasa-sync` | Compress session to 5-sector TOON memory vault. |
| `/dasa-fix` | Auto-heal from terminal errors. |
| `/dasa-pr` | Adversarial GitHub PR review via `gh`. |
| `/dasa-e2e` | Native browser E2E test (records `.webp` videos). |
| `/dasa-seed` | Generate realistic database fixtures. |
| `/dasa-docs` | Generate Postman/OpenAPI specs. |
| `/dasa-assimilate` | Onboard a pre-existing, undocumented codebase. |
| `/dasa-uninstall` | Remove `.agent/` from the workspace. |

---

## The 10 Dasa Personas

| Persona | Role |
|:---|:---|
| **Dasa Patih** | Orchestrator — routes tasks, compacts memory |
| **Dasa Mpu** | Master Architect — system design, planning |
| **Dasa Rsi** | Sage Consultant — code review, SOLID enforcement |
| **Dasa Nala** | Builder — frontend/backend implementation |
| **Dasa Sastra** | Writer — documentation, API specs |
| **Dasa Widya** | Researcher — library analysis, data research |
| **Dasa Dwipa** | Scout — codebase exploration, skill search |
| **Dasa Indra** | QA Investigator — testing, `qa_gate.py` enforcement |
| **Dasa Dharma** | Security Guardian — secret scanning, audits |
| **Dasa Kala** | Swift Fixer — patches, quick tactical fixes |

---

## Extensibility

### Community Skills
Download any Antigravity-compatible skill into `.agent/skills/` and Dasa Dwipa will automatically find and index it:

```bash
python3 .agent/scripts/skill_search.py "database migration"
```

### External Skill Paths
Add external skill paths to your `dasa.config.toon`:
```yaml
external_skills:
  - "/path/to/community-skill"
```

---

## Deep Dives

- [HOW_IT_WORKS.md](HOW_IT_WORKS.md) — Complete Architectural Manual
- [CONTRIBUTING.md](CONTRIBUTING.md) — How to forge new Personas and Workflows
- [CHANGELOG.md](CHANGELOG.md) — Latest updates
