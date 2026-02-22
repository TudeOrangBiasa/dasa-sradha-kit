# Dasa Sradha Kit — Project Summary

> **Current Version:** 5.2.1 | **Date:** 2026-02-23 | **53-Gap Hardened**

## What Is It?

A native, zero-dependency AI orchestration framework for **Antigravity IDE**. 10 AI Personas split complex software workflows into strict Agile pipelines (Architect → Builder → QA) — all triggered by natural language prompts.

## Architecture at a Glance

| Layer | Path | Purpose |
|:---|:---|:---|
| **Read-Only Mechanics** | `.agent/` | 10 personas, 17 scripts, 16 workflows, P0 rules |
| **Portable Artifacts** | `.artifacts/task.toon` etc. | Committable state (survives cross-device) |
| **Ephemeral Artifacts** | `.artifacts/dasa_memory.toon` etc. | Session-scoped (gitignored) |
| **Design Memory** | `.design-memory/` | Long-term UI specs, Figma references |
| **Configuration** | `dasa.config.toon` | Tech stack, paths, skills |

## Core Pipelines

1. **Auto-Routing (A-J):** Prompt → Intent Detection → Auto Workflow
2. **Execution (Agile):** Mpu → Rsi (if complex) → Nala → Indra (QA)

## 10 Personas

| Persona | Domain |
|:---|:---|
| Patih | Orchestration, trace logging |
| Mpu | Architecture, planning, vision |
| Rsi | Code review, SOLID enforcement |
| Nala | Frontend/Backend, design token grounding |
| Indra | QA gate, linter, circuit breaker |
| Dharma | Security, injection audit, git hygiene |
| Dwipa | Scouting, skill search, assimilation |
| Widya | Research, library analysis |
| Sastra | Documentation, API specs |
| Kala | Hotfixes, tactical patches |

## v5.2.1 Highlights

- **53-gap defense-in-depth** across 10 security/reliability layers
- **10 auto-routing scenarios** (A-J) including preference pivots and catch-all fallback
- **Effort-gated Rsi review** (Phase 1.5) for Deep/Exhaustive tasks
- **QA circuit breaker** (3-bounce max before Rsi escalation)
- **Design system token grounding** (prevents framework default drift)
- **Artifact portability model** (portable vs ephemeral classification)
- **Shell injection prevention**, trace log masking, git hygiene enforcement

## Quick Start

```bash
npx dasa-sradha-kit init
```

## Deep Dives

- [README.md](../README.md) — Overview + getting started
- [HOW_IT_WORKS.md](../HOW_IT_WORKS.md) — Full architectural manual
- [CONTRIBUTING.md](../CONTRIBUTING.md) — Contribution guide
- [ARCHITECTURE.md](../.agent/ARCHITECTURE.md) — File-level architecture
- [dasa-sradha-project-summary.toon](dasa-sradha-project-summary.toon) — Full TOON dump for AI context
- [CHANGELOG.md](../CHANGELOG.md) — Release history
