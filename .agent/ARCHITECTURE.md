# Dasa Sradha Kit — .agent/ Architecture
# V5.2.1 Zero-Dependency Native Workspace (53-Gap Hardened)

---

## Overview

The `.agent/` folder is the **read-only brain** of the Dasa Sradha Kit.
It is installed per-project via `npx dasa-sradha-kit init` and never modified during execution.

```
.agent/
├── ARCHITECTURE.md        ← This file
├── VERSION                ← Kit semver (e.g., 5.2.1) for migration detection
├── agents/                ← 10 Dasa Personas (Antigravity Agent definitions)
├── rules/
│   └── GEMINI.md          ← P0 global constraints (SOLID, TDD, 53-gap hardening)
├── skills/                ← Modular domain resources for Agents to load
├── .shared/               ← Common templates (dasa-cheat-sheet.toon, skill_trust_ledger.json)
├── workflows/             ← 16 Slash Commands (/dasa-plan, /dasa-e2e, etc.)
└── scripts/               ← 17 Cross-platform Python executables (no Bash)
```

The **read-write memory** lives separately:

```
<workspace-root>/
├── .artifacts/            ← Short-term memory
│   ├── task.toon                   (PORTABLE — committable)
│   ├── architecture-state.toon     (PORTABLE — committable)
│   ├── implementation_plan.md      (PORTABLE — committable)
│   ├── dasa_memory.toon            (EPHEMERAL — gitignored)
│   ├── trace.toon                  (EPHEMERAL — gitignored)
│   ├── merge_digest.toon           (EPHEMERAL — gitignored)
│   ├── process_registry.toon       (EPHEMERAL — gitignored)
│   ├── side-effects.toon           (EPHEMERAL — gitignored)
│   └── generated-skills/           (EPHEMERAL — gitignored)
├── .design-memory/        ← Long-term: UI specs, architectural decisions
└── dasa.config.toon       ← Workspace configuration (stack, paths, skills)
```

---

## Agents (10 Personas)

| Agent | Role | Domain |
|---|---|---|
| `dasa-patih` | Orchestrator / Prime Minister | Task routing, compaction, trace logging |
| `dasa-mpu` | Master Architect | System design, planning, vision analysis |
| `dasa-rsi` | Sage Consultant / Reviewer | Code review, SOLID enforcement |
| `dasa-nala` | The Builder | Frontend/Backend implementation |
| `dasa-sastra` | Documentation Writer | Docs, API specs, READMEs |
| `dasa-widya` | Researcher | Library research, data analysis |
| `dasa-dwipa` | Scout / Semantic Search | Codebase exploration, skill search |
| `dasa-indra` | QA / E2E Tester | Testing, qa_gate.py, local linter enforcement |
| `dasa-dharma` | Security Guardian | Secret scanning, injection audit, git hygiene |
| `dasa-kala` | Swift Hotfixer | Patches, quick tactical fixes |

---

## Core Orchestration Pipelines

There are two distinct pipelines operating within the kit:

**1. The Auto-Routing Pipeline (Intent to Action)**
`Prompt -> Intent Detection (Scenarios A-J) -> Auto-Workflow Execution`
This pipeline handles zero-command routing. 10 scenarios cover: initialization, assimilation, feature building, hotfixing, sync, docs, commits, visuals, preference pivots, and graceful fallbacks.

**2. The Execution Pipeline (Agile Handoff)**
`Phase 1: Mpu -> Phase 1.5: Rsi (Deep/Exhaustive only) -> Phase 2: Nala -> Phase 3: Indra`
Once a workflow is active, the strict chain of command applies. Rsi review is effort-gated — only invoked for complex tasks. Indra enforces the QA gate with a 3-bounce circuit breaker.

---

## Workflows (16 Slash Commands)

| Command | Agent(s) | Description |
|---|---|---|
| `/dasa-api` | Patih → Mpu → Sastra | API endpoint + docs (framework-agnostic) |
| `/dasa-assimilate` | Dwipa → Widya | Onboard pre-existing codebase |
| `/dasa-commit` | Dwipa + Indra + Dharma | QA gate + security audit + atomic git commit |
| `/dasa-docs` | Dwipa → Mpu → Sastra | API documentation |
| `/dasa-e2e` | Indra | Native browser E2E test |
| `/dasa-feature` | Mpu → Nala → Indra | Vertical feature (stack-agnostic via `dasa.config.toon`) |
| `/dasa-fix` | Rsi → Kala | Auto-heal from terminal errors |
| `/dasa-init` | Patih | Initialize workspace config + git hygiene + VERSION |
| `/dasa-plan` | Mpu | Create `implementation_plan.md` |
| `/dasa-pr` | Rsi | Adversarial GitHub PR review |
| `/dasa-refactor` | Rsi → Nala → Indra | Safe refactoring with mandatory QA gate |
| `/dasa-seed` | Dwipa → Mpu → Nala | DB fixture generation |
| `/dasa-start-work` | Patih → Mpu → Nala → Indra | Execute plan via strict Agile pipeline |
| `/dasa-status` | Patih | Report progress |
| `/dasa-sync` | Patih → Sastra | Compress session to 5-sector TOON memory vault |
| `/dasa-uninstall` | Patih | Remove `.agent/` from workspace |

---

## Scripts (17 Python — Zero-Dependency, Cross-Platform)

| Script | Persona | Description |
|---|---|---|
| `api_validator.py` | Sastra | OpenAPI/Postman JSON validator |
| `arch_mapper.py` | Mpu | Dependency graph cartographer |
| `compact_memory.py` | Patih | 5-sector TOON memory compactor (memU active learning) |
| `complexity_scorer.py` | Rsi | Cyclomatic complexity hotspot finder (> 10 warning) |
| `context_mapper.py` | Patih | Native AST-based codebase context generator |
| `design_engine.py` | Mpu/Nala | Strict TOON design system generator |
| `design_memory_sync.py` | Nala | Figma-to-TOON design bridge |
| `lint_fixer.py` | Nala | Auto-formatter dispatcher |
| `qa_gate.py` | Indra | Engineering failure pattern scanner (1,000+ heuristics) |
| `security_scan.py` | Dharma | Pre-commit secret/key leak detection |
| `semantic-scan.py` | Dwipa | Fast grep fallback if osgrep is missing |
| `skill_search.py` | Dwipa | Local SKILL.md semantic indexer |
| `status_parser.py` | Kala | Task progress JSON aggregator |
| `test_runner.py` | Indra | Universal test framework wrapper |
| `validate_env.py` | Patih | Environment gatekeeper (container detection, binary preflight, orphan cleanup) |
| `web_scraper.py` | Widya | HTML-to-Markdown URL extractor |
| `workspace-mapper.py` | Dwipa | Visual workspace tree generator |

---

## Rules Priority

```
P0: .agent/rules/GEMINI.md        (Always-on: SOLID, TDD, 53-Gap Hardening)
P1: .agent/agents/dasa-*.md       (Per-persona overrides)
P2: .agent/skills/**              (Domain-specific knowledge, e.g. engineering-failures)
```

---

## v5.2.1 Defense Layers (53 Gaps)

| Layer | Gaps | Domain |
|---|---|---|
| L1 Architecture | 1-6 | Intent routing, pipeline, rules, QA, memory, security |
| L2 Meta-Gaps | 1-6 dual | Second-order patch risks |
| L3 Infrastructure | 7-11 | Visual QA, races, monorepo, fallback, stdlib |
| L4 Deep Infra | 12-15 | Container, source locks, supply chain, bloat |
| L5 Meta-Security | 16-20 | Immutable ledger, read-barrier, synthesis, a11y, broadcast |
| L6 Refinement | 21-25 | Path map, skill GC, plan drift, noise, shedding |
| L7 Security+ | 26-30 | Shell injection, creds, legacy files, facts, IDE version |
| L8 Operational | 31-40 | Rollback, license, model drift, loops, trace, budget, circuit breaker |
| L9 Practitioner | 41-46 | Dirty read, truncation, linter, sync, pins, design tokens |
| L10 Hygiene | 47-53 | Brain leak, zombies, git safety, portability, secrets, migration |
