# Dasa Sradha Kit — .agent/ Architecture
# V4 Hybrid Local Workspace Pattern

---

## Overview

The `.agent/` folder is the **read-only brain** of the Dasa Sradha Kit.
It is installed per-project via `npx dasa-sradha-kit init` and never modified during execution.

```
.agent/
├── ARCHITECTURE.md        ← This file
├── agents/                ← 10 Dasa Personas (Antigravity Agent definitions)
├── rules/
│   └── GEMINI.md          ← P0 global constraints (always-on)
├── skills/                ← Modular domain resources for Agents to load
├── .shared/               ← Common templates (max-power-core.md, infinite-memory.md)
├── workflows/             ← 13 Slash Commands (/dasa-plan, /dasa-e2e, etc.)
└── scripts/               ← Cross-platform Python executables (no Bash)
```

The **read-write memory** lives separately from this folder:

```
<workspace-root>/
├── .artifacts/            ← Short-term: active task plans, walkthroughs, logs
├── .design-memory/        ← Long-term: UI specs, architectural decisions
└── dasa.config.toon       ← Workspace configuration (stack, paths, skills)
```

---

## Agents (10 Personas)

| Agent | Role | Model |
|---|---|---|
| `dasa-patih` | Orchestrator / Prime Minister | Gemini 3.1 Pro (high) |
| `dasa-mpu` | Master Architect | Gemini 3.1 Pro (high) |
| `dasa-rsi` | Sage Consultant / Reviewer | Gemini 3.1 Pro (high) |
| `dasa-nala` | The Builder | Claude Sonnet 4.6 (thinking) |
| `dasa-sastra` | Documentation Writer | Claude Sonnet 4.6 (thinking) |
| `dasa-widya` | Researcher | Claude Sonnet 4.6 (thinking) |
| `dasa-dwipa` | Scout / Semantic Search | Gemini 3.1 Pro (low) |
| `dasa-indra` | QA / E2E Tester | Gemini 3.1 Pro (low) |
| `dasa-dharma` | Security Guardian | Gemini 3.1 Pro (low) |
| `dasa-kala` | Swift Hotfixer | Gemini 3 Flash |

---

## Workflows (13 Slash Commands)

| Command | Agent(s) | Description |
|---|---|---|
| `/dasa-init` | Patih | Initialize workspace config |
| `/dasa-plan` | Mpu | Create `implementation_plan.md` |
| `/dasa-start-work` | Nala → Mpu | Execute plan via `task.md` |
| `/dasa-status` | Patih | Report progress |
| `/dasa-commit` | Dwipa | QA + atomic git commit |
| `/dasa-sync` | Patih → Sastra | Compress session to memory vault |
| `/dasa-fix` | Rsi → Kala | Auto-heal from terminal errors |
| `/dasa-pr` | Rsi | Adversarial GitHub PR review |
| `/dasa-e2e` | Indra | Native browser E2E test |
| `/dasa-seed` | Dwipa → Mpu → Nala | DB fixture generation |
| `/dasa-docs` | Dwipa → Mpu → Sastra | API documentation |
| `/dasa-assimilate` | Dwipa → Widya | Onboard pre-existing codebase |
| `/dasa-uninstall` | Patih | Remove `.agent/` from workspace |

---

## Scripts (Python — Cross-Platform)

| Script | Persona | Description |
|---|---|---|
| `semantic-scan.py` | Dwipa | Wraps `osgrep` for token-efficient semantic code search |
| `workspace-mapper.py` | Dwipa | Generates visual workspace tree |

---

## Rules Priority

```
P0: .agent/rules/GEMINI.md        (Always-on, applied globally)
P1: .agent/agents/dasa-*.md       (Per-persona overrides)
P2: .agent/skills/**              (Domain-specific knowledge)
```
