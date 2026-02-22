# How It Works — Dasa Sradha Kit V5.2.1

## The Core Philosophy

Dasa Sradha is built on one principle: **Move intelligence OUT of the AI prompt and INTO native code.** Every Python script, every TOON file, and every workflow exists to reduce the number of tokens the LLM has to process.

---

## 2. Zero-Command Orchestration (Triggerless Auto-Routing)

You do **not** need to memorize or explicitly type slash commands like `/dasa-plan` or `/dasa-start-work`.

If you simply type:
> *"Build me a blog website with Astro and Express. The design mockups are in .design-memory/reference/"*

The baseline IDE agent (restricted by `.agent/rules/GEMINI.md`) will **autonomously intercept your intent** and bootstrap the Dasa Sradha workflow on its own.

### Context Verification Branching

If `dasa.config.toon` is blank (missing frontend/backend definitions), the AI will evaluate the workspace before proceeding:
- **Scenario A (Empty Folder):** The AI pauses and interviews you ("What tech stack are we using?"). Once answered, Dasa Dwipa fetches the necessary community skills.
- **Scenario B (Existing Codebase, blank/stale config):** If files like `package.json` exist, the AI silently triggers `/dasa-assimilate`, allowing Dasa Dwipa to map the architecture and auto-populate the config without bothering you. **Staleness Guard:** If config is >7 days old, offers both quick explanation (F) and deep re-assimilation (B).

### 10 Auto-Routing Scenarios (A-J)

| Scenario | When | What Happens |
|:---|:---|:---|
| **A** | Empty folder, "make me an app" | Interview → populate config |
| **B** | Existing code, blank/stale config | Silent assimilation |
| **C** | "add login", "build feature" | Auto plan + execute pipeline |
| **D** | "fix this", terminal error | Kala/Rsi surgical hotfix |
| **E** | "bye", "context is full" | Compress to memory vault |
| **F** | "explain", "docs" | Auto documentation generation |
| **G** | "commit", "push" | Security scan → QA gate → local linter → commit |
| **H** | "check design", mockup detected | Vision analysis → UI generation |
| **I** | "I changed my mind about..." | Preference pivot in memory vault |
| **J** | *(nothing matches)* | Present 3 most likely scenarios |

Once the context is secure, the AI will:
1. Generate the plan into `.artifacts/task.toon` via the **Mpu Phase**.
2. Compress visual tokens using `design_memory_sync.py` if Figma PNGs exist.
3. Automatically trigger the `Mpu -> Nala -> Indra` Agile Pipeline.

## 3. The Agile Pipeline (Strict Multi-Agent Handoff)

When a user types `/dasa-start-work`, the following strict Agile pipeline is enforced:

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│ Phase 1  │ ─► │Phase 1.5 │ ─► │ Phase 2  │ ─► │ Phase 3  │
│   Mpu    │    │   Rsi    │    │   Nala   │    │  Indra   │
│(Architect)    │(Reviewer)│    │(Builder) │    │(QA Gate) │
│          │    │Deep/Exh  │    │          │    │          │
│architecture   │only      │    │BLOCKED   │    │qa_gate.py│
│-state.toon    │          │    │until P1  │    │+linter   │
└──────────┘    └──────────┘    └──────────┘    └──────────┘
```

#### Phase 1: Mpu (The Master Architect)
Mpu *never writes code*. Mpu's entire job is to:
1. Analyze your requirements.
2. Analyze any visual PNG mockups inside `.design-memory/reference/`.
3. Plan the component architecture and define state.
4. Output the exact findings into `.artifacts/architecture-state.toon`.
5. Document side-effects in `.artifacts/side-effects.toon` with rollback commands.
6. Pin critical architectural decisions as `pinned: true` memories.

#### Phase 1.5: Rsi (Effort-Gated Review)
**Only for 'Deep' and 'Exhaustive' tasks.** Rsi performs adversarial review of Mpu's architecture before Nala begins building. Skipped for 'Instant' and 'Light' tasks.

#### Phase 2: Nala (The Builder)
Nala reads the architecture TOON and writes code. Must conform to `GEMINI.md` constraints. Before writing UI code, Nala checks for **design system configs** (tailwind.config, theme.json, `:root {}`) and uses project tokens instead of framework defaults.

#### Phase 3: QA Gate (Dasa Indra)
Indra runs:
1. `.agent/scripts/qa_gate.py` — 1,000+ failure patterns.
2. **Project-local linter** (auto-detected or from `lint_command` in config).
3. **Circuit breaker:** If Nala → Indra fails 3 consecutive times, escalate to Rsi.

---

## The TOON Memory System

Instead of relying on LLM chat history (which overflows and gets expensive), Dasa Sradha compresses all knowledge into a 5-sector Temporal Knowledge Graph:

| Sector | Purpose | Example |
|:---|:---|:---|
| **Episodic** | Events | "User asked to switch to SQLite" |
| **Semantic** | Facts | "App runs on port 3000" |
| **Procedural** | Skills (Proactive) | "Deployment: `npm run build && vercel`" |
| **Emotional** | Preferences (Proactive)| "User strictly hates Tailwind classes" |
| **Reflective** | Insights (Pinnable) | "DB schema uses UUID not auto-increment" |

**Key features:**
- **Temporal Decay:** Memories older than 7 days lose weight. MAX_WEIGHT = 20.
- **Pinned Memory:** Architecture-critical decisions survive all shedding cycles.
- **Project Isolation:** Memory is scoped per-workspace. No cross-project contamination.
- **Portable vs Ephemeral:** `task.toon` and `architecture-state.toon` are committable. Memory vaults and traces are gitignored.

---

## The 17 Native Python Scripts

All scripts are **zero-dependency** (stdlib whitelist only) and **cross-platform** (Windows, macOS, Linux):

| Script | Owner | Purpose |
|:---|:---|:---|
| `api_validator.py` | Sastra | OpenAPI/Postman JSON validator |
| `arch_mapper.py` | Mpu | Dependency graph cartographer |
| `compact_memory.py` | Patih | 5-sector TOON memory compactor (memU active learning) |
| `complexity_scorer.py` | Rsi | Cyclomatic complexity hotspot finder (> 10 warning) |
| `context_mapper.py` | Patih | Native AST-based codebase context generator |
| `design_engine.py` | Mpu/Nala | Strict TOON design system generator |
| `design_memory_sync.py` | Nala | Figma-to-TOON design bridge |
| `lint_fixer.py` | Nala | Auto-formatter dispatcher |
| `qa_gate.py` | Indra | Engineering failure pattern scanner (~1,000 patterns) |
| `security_scan.py` | Dharma | Pre-commit secret/key leak detection |
| `semantic-scan.py` | Dwipa | Fast grep fallback if osgrep is missing |
| `skill_search.py` | Dwipa | Local skill semantic indexer |
| `status_parser.py` | Kala | Task progress JSON aggregator |
| `test_runner.py` | Indra | Universal test framework wrapper |
| `validate_env.py` | Patih | Environment gatekeeper (container detection, binary preflight, orphan cleanup) |
| `web_scraper.py` | Widya | HTML-to-Markdown URL extractor |
| `workspace-mapper.py` | Dwipa | Visual workspace tree generator |

---

## Token Efficiency

V5.2.1 achieves radical token savings through:

1. **Native Python scripts** offload heavy computation (AST parsing, security scanning) from the LLM context.
2. **TOON memory vaults** replace verbose chat history with compressed, structured data.
3. **Senior constraints** (Methods < 10 lines) force tiny, atomic responses.
4. **Effort-gated reviews** skip Rsi for simple tasks, saving pipeline overhead.
5. **Design Engine** generates strict UI rules in ~50 lines, eliminating the need for the LLM to read thousands of tokens of Figma CSS.
6. **500-line AST-windowed reading** prevents large legacy files from consuming the context.
7. **Token Budget Guard** caps tool calls at 100 per task (configurable) to prevent runaway costs.

---

## Security Hardening (53 Gaps)

V5.2.1 includes a 10-layer defense system:

| Layer | Coverage |
|:---|:---|
| **Architecture** | Intent routing, pipeline, rules, QA, memory, security |
| **Infrastructure** | Visual QA, race conditions, monorepo, stdlib whitelist |
| **Security** | Shell injection, skill trust (SHA-256), container credentials |
| **Operational** | Rollback, circuit breaker, trace logging, token budgets |
| **Hygiene** | Git safety, cross-device portability, secret masking, migration |
