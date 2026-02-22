# Dasa Sradha Kit — .agent/ Architecture
# V5 Zero-Dependency Native Workspace

---

## Overview

The `.agent/` folder is the **read-only brain** of the Dasa Sradha Kit.
It is installed per-project via `npx dasa-sradha-kit init` and never modified during execution.

```
.agent/
├── ARCHITECTURE.md        ← This file
├── agents/                ← 10 Dasa Personas (Antigravity Agent definitions)
├── rules/
│   └── GEMINI.md          ← P0 global constraints (always-on, SOLID, TDD)
├── skills/                ← Modular domain resources for Agents to load
├── .shared/               ← Common templates (infinite-memory.md)
├── workflows/             ← 16 Slash Commands (/dasa-plan, /dasa-e2e, etc.)
└── scripts/               ← 17 Cross-platform Python executables (no Bash)
```

The **read-write memory** lives separately:

```
<workspace-root>/
├── .artifacts/            ← Short-term: active task plans, walkthroughs, TOON memory vaults
├── .design-memory/        ← Long-term: UI specs, architectural decisions
└── dasa.config.toon       ← Workspace configuration (stack, paths, skills)
```

---

## Agents (10 Personas)

| Agent | Role | Domain |
|---|---|---|
| `dasa-patih` | Orchestrator / Prime Minister | Task routing, compaction |
| `dasa-mpu` | Master Architect | System design, planning |
| `dasa-rsi` | Sage Consultant / Reviewer | Code review, SOLID enforcement |
| `dasa-nala` | The Builder | Frontend/Backend implementation |
| `dasa-sastra` | Documentation Writer | Docs, API specs, READMEs |
| `dasa-widya` | Researcher | Library research, data analysis |
| `dasa-dwipa` | Scout / Semantic Search | Codebase exploration, skill search |
| `dasa-indra` | QA / E2E Tester | Testing, qa_gate.py enforcement |
| `dasa-dharma` | Security Guardian | Secret scanning, dependency audit |
| `dasa-kala` | Swift Hotfixer | Patches, quick tactical fixes |

---

## Workflows (16 Slash Commands)

| Command | Agent(s) | Description |
|---|---|---|
| `/dasa-init` | Patih | Initialize workspace config |
| `/dasa-plan` | Mpu | Create `implementation_plan.toon` |
| `/dasa-start-work` | Patih → Mpu → Nala → Indra | Execute plan via strict Agile pipeline |
| `/dasa-feature` | Mpu → Nala → Indra | Vertical feature (stack-agnostic via `dasa.config.toon`) |
| `/dasa-api` | Patih → Mpu → Sastra | API endpoint + docs (framework-agnostic) |
| `/dasa-refactor` | Rsi → Nala → Indra | Safe refactoring with mandatory QA gate |
| `/dasa-status` | Patih | Report progress |
| `/dasa-commit` | Dwipa + Indra | QA gate + atomic git commit |
| `/dasa-sync` | Patih → Sastra | Compress session to 5-sector TOON memory vault |
| `/dasa-fix` | Rsi → Kala | Auto-heal from terminal errors |
| `/dasa-pr` | Rsi | Adversarial GitHub PR review |
| `/dasa-e2e` | Indra | Native browser E2E test |
| `/dasa-seed` | Dwipa → Mpu → Nala | DB fixture generation |
| `/dasa-docs` | Dwipa → Mpu → Sastra | API documentation |
| `/dasa-assimilate` | Dwipa → Widya | Onboard pre-existing codebase |
| `/dasa-uninstall` | Patih | Remove `.agent/` from workspace |

---

## Scripts (17 Python — Zero-Dependency, Cross-Platform)

| Script | Persona | Description |
|---|---|---|
| `qa_gate.py` | Indra | Engineering Failures Bible scanner (~800 patterns) |
| `context_mapper.py` | Patih | Native AST-based codebase context generator |
| `skill_search.py` | Dwipa | Local SKILL.md semantic indexer |
| `design_engine.py` | Mpu/Nala | Strict TOON design system generator |
| `compact_memory.py` | Patih | 5-sector TOON memory compactor |
| `security_scan.py` | Dharma | Pre-commit secret/key leak detection |
| `validate_env.py` | Patih | Environment gatekeeper |
| `test_runner.py` | Indra | Universal test framework wrapper |
| `lint_fixer.py` | Nala | Auto-formatter dispatcher |
| `api_validator.py` | Sastra | OpenAPI/Postman JSON validator |
| `arch_mapper.py` | Mpu | Dependency graph cartographer |
| `status_parser.py` | Kala | Task progress JSON aggregator |
| `web_scraper.py` | Widya | HTML-to-Markdown URL extractor |
| `complexity_scorer.py` | Rsi | Cyclomatic complexity hotspot finder |
| `design_memory_sync.py` | Nala | Figma-to-TOON design bridge |
| `semantic-scan.py` | Dwipa | osgrep wrapper (optional) |
| `workspace-mapper.py` | Dwipa | Visual workspace tree generator |

---

## Rules Priority

```
P0: .agent/rules/GEMINI.md        (Always-on: SOLID, TDD, Methods < 10 lines)
P1: .agent/agents/dasa-*.md       (Per-persona overrides)
P2: .agent/skills/**              (Domain-specific knowledge, e.g. engineering-failures)
```
