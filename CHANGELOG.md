# Changelog

All notable changes to the Dasa Sradha Kit will be documented in this file.

---

## [5.0.0] - 2026-02-22

### 🚀 Major Release: V5 Zero-Dependency Ecosystem

#### Added
- **3 new stack-agnostic workflows**: `/dasa-feature`, `/dasa-api`, `/dasa-refactor` — all dynamically read `dasa.config.toon` instead of hardcoding frameworks.
- **`qa_gate.py`**: Native Python engineering failures scanner with ~800 patterns assimilated from `engineering-failures-bible` (Memory, Concurrency, Security domains).
- **`context_mapper.py`**: Zero-dependency AST-based codebase context generator. Replaces the need for `amdb` or external vector DBs.
- **`skill_search.py`**: Native local skill indexer. Scans `.agent/skills/` and `~/.gemini/antigravity/skills/` using semantic text overlap.
- **`design_engine.py`**: Strict TOON design system generator assimilating `ui-ux-pro-max-skill` and `design-rules-ai` logic.
- **`compact_memory.py`**: 5-sector TOON memory compactor (episodic, semantic, procedural, emotional, reflective) imitating `OpenMemory`.
- **Background persona spawning**: `npx dasa-cli run <persona>` spawns detached Node processes to keep the main chat token-free.
- **Senior Engineer Constraints (SOLID)**: Methods < 10 lines, Classes < 50 lines, TDD enforcement, Value Objects — injected globally into `GEMINI.md`.
- **Strict Agile Pipeline**: `/dasa-start-work` now enforces rigid `Mpu (Architect) → Nala (Dev) → Indra (QA)` handoffs. Nala is blocked until Mpu's architecture TOON exists.

#### Changed
- **`ARCHITECTURE.md`**: Completely rewritten for V5. Now documents all 10 agents, 16 workflows, and 17 scripts.
- **`README.md`**: Completely rewritten for V5. Removed all V3 global-install legacy references.
- **`HOW_IT_WORKS.md`**: Completely rewritten. Documents the strict Agile pipeline, TOON memory system, and token efficiency strategies.
- **`CONTRIBUTING.md`**: Updated with V5 templates for adding Personas, Workflows, and Scripts.
- **`package.json`**: Bumped from `4.0.0` to `5.0.0`.
- **`infinite-memory.md`**: Updated to teach Personas the 5-sector TOON memory vault instead of legacy markdown files.
- **`dasa-init.md`**: Updated to use `npx dasa-cli init` instead of the legacy bash wrapper.

#### Removed
- **`dasa-suta` phantom persona**: Removed from `dasa-cli.js` (no corresponding agent file existed).
- **Empty `.agent/skills/` subdirectories**: Pruned all deprecated V3 skill folders.
- **Legacy bash `scripts/` references**: All workflows now reference native Python or Node CLI tools.

#### Ecosystem Research (Phase 2)
Knowledge extracted and compressed into `.toon` files for 6 community repositories:
- `runkids/skillshare` → `.artifacts/knowledge_skillshare.toon`
- `harikrishna8121999/antigravity-workflows` → `.artifacts/knowledge_ag_workflows.toon`
- `OleynikAleksandr/antigravity-subagents` → `.artifacts/knowledge_ag_subagents.toon`
- `salacoste/antigravity-bmad-config` → `.artifacts/knowledge_bmad_config.toon`
- `mduongvandinh/engineering-failures-bible` → `.artifacts/knowledge_failures_bible.toon`
- `BETAER-08/amdb` → `.artifacts/knowledge_amdb.toon`

---

## [4.0.0] - 2026-02-21

### 🏗️ V4: The Local Workspace Pivot

#### Added
- Cross-platform NPM CLI (`npx dasa-sradha-kit init`).
- Hybrid Workspace Architecture: `.agent/` (read-only mechanics) + `.artifacts/` (read-write state).
- `dasa.config.toon` workspace configuration format.
- 11 cross-platform Python scripts replacing all bash logic.
- `GEMINI.md` global constraints file with P0 priority.

#### Changed
- Migrated from global `~/.gemini/` install to local `.agent/` workspace pattern.
- Migrated from bash scripts to Python 3 for Windows/macOS/Linux compatibility.
- Restructured all 13 workflows to declarative markdown format.

#### Removed
- `install.sh` global installer (replaced by NPM CLI).
- Root `scripts/`, `skills/`, `workflows/` directories (moved to `.agent/`).

---

## [3.0.0] - 2026-02-20

### Added
- Native E2E testing via Antigravity `browser_subagent`.
- Database seeder workflow (`/dasa-seed`).
- GitHub PR auto-reviewer (`/dasa-pr`).
- `osgrep` semantic search integration for Dasa Dwipa.

---

## [2.0.0] - 2026-02-19

### Added
- Monorepo workspace routing.
- API documentation workflow (`/dasa-docs`).
- TOON format adoption for all state files.

---

## [1.0.0] - 2026-02-18

### Added
- Initial release with 10 Dasa Personas.
- 7 core slash commands.
- `install.sh` global installer.
- Bahasa Indonesia persona outputs.
