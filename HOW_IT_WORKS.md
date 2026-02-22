# How It Works — Dasa Sradha Kit V5

## The Core Philosophy

Dasa Sradha is built on one principle: **Move intelligence OUT of the AI prompt and INTO native code.** Every Python script, every TOON file, and every workflow exists to reduce the number of tokens the LLM has to process.

---

## 2. Zero-Command Orchestration (Triggerless Auto-Routing)

You do **not** need to memorize or explicitly type slash commands like `/dasa-plan` or `/dasa-start-work`.

If you simply type:
> *"Build me a blog website with Astro and Express. The design mockups are in .design-memory/reference/"*

The baseline IDE agent (restricted by `.agent/rules/GEMINI.md`) will **autonomously intercept your intent** and bootstrap the Dasa Sradha workflow on its own. It will:
1. Ensure `dasa.config.toon` exists.
2. Read `.artifacts/dasa-cheat-sheet.toon`.
3. Populate `.artifacts/task.toon`.
4. Run the Pipeline natively.

## 3. The Agile Pipeline (Strict Multi-Agent Handoff)

When a user types `/dasa-start-work`, the following strict Agile pipeline is enforced:

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Phase 1: Mpu   │ ──► │  Phase 2: Nala  │ ──► │  Phase 3: Indra │
│  (Architect)    │     │  (Developer)    │     │  (QA Gate)      │
│                 │     │                 │     │                 │
│  Generates      │     │  BLOCKED until  │     │  Runs qa_gate.py│
│  architecture-  │     │  Phase 1 done.  │     │  (~800 patterns)│
│  state.toon     │     │  Code < 10 ln   │     │  Pass or bounce │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

#### Phase 1: Mpu (The Master Architect)
Triggered by `/dasa-start-work` (or autonomously), Mpu takes over. Mpu *never writes code*. Mpu's entire job is to:
1. Analyze your requirements.
2. Analyze any visual PNG mockups inside `.design-memory/reference/`.
3. Plan the component architecture and define state.
4. Output the exact findings into `.artifacts/architecture-state.toon`.

> **Note:** Nala (the Frontend Engineer) is strictly blocked from writing a single line of code until Mpu populates `architecture-state.toon`.

#### Phase 2: Nala (The Builder)
Nala reads the architecture TOON and writes code. All code must conform to `GEMINI.md` constraints: Methods < 10 lines, Classes < 50 lines, TDD enforcement.

### Phase 3: QA Gate (Dasa Indra)
Indra runs `.agent/scripts/qa_gate.py` — a native Python scanner containing ~800 failure patterns (Memory Leaks, Concurrency, Security) assimilated from the Engineering Failures Bible. If any critical issue is found, the task bounces back to Phase 2.

---

## The TOON Memory System

Instead of relying on LLM chat history (which overflows and gets expensive), Dasa Sradha compresses all knowledge into a 5-sector Temporal Knowledge Graph:

| Sector | Purpose | Example |
|:---|:---|:---|
| **Episodic** | Events | "User asked to switch to SQLite" |
| **Semantic** | Facts | "App runs on port 3000" |
| **Procedural** | Skills | "Deployment: `npm run build && vercel`" |
| **Emotional** | Preferences | "User strictly hates Tailwind classes" |
| **Reflective** | Insights | "Last build failed due to outdated dep" |

This is managed by `.agent/scripts/compact_memory.py` and stored in `.artifacts/dasa_memory.toon`.

---

## The 17 Native Python Scripts

All scripts are **zero-dependency** (standard library only) and **cross-platform** (Windows, macOS, Linux):

| Script | Owner | Purpose |
|:---|:---|:---|
| `qa_gate.py` | Indra | Engineering failure pattern scanner |
| `context_mapper.py` | Patih | AST-based codebase context generator |
| `skill_search.py` | Dwipa | Local skill semantic indexer |
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

## Stack-Agnostic Workflows

The new V5 workflows (`/dasa-feature`, `/dasa-api`, `/dasa-refactor`) do not hardcode any framework. They dynamically read `dasa.config.toon` to determine:
- Which language to generate code in
- Which testing framework to run
- Which styling approach to use

This means the same `/dasa-feature "User Login"` command will generate React components if your config says `"framework": "React"`, or Go handlers if it says `"framework": "Go"`.

---

## Token Efficiency

V5 achieves radical token savings through:

1. **Native Python scripts** offload heavy computation (AST parsing, security scanning) from the LLM context.
2. **TOON memory vaults** replace verbose chat history with compressed, structured data.
3. **Senior constraints** (Methods < 10 lines) force tiny, atomic responses.
4. **Background spawning** (`npx dasa-cli run <persona>`) keeps sub-agent thinking out of the main chat.
5. **Design Engine** generates strict UI rules in ~50 lines, eliminating the need for the LLM to read thousands of tokens of Figma CSS.
