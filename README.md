# Dasa Sradha Kit for Antigravity

The **Dasa Sradha Kit** is a native, Zero-Dependency Agentic Framework designed exclusively for the **Antigravity IDE**. It splits complex software workflows into 10 distinct AI Personas, allowing you to orchestrate massive full-stack builds without exploding your LLM context window.

## Key Features

- **Persona-Based Orchestration**: 10 distinct AI agents (The Scout, The Architect, The Builder, etc.) that natively hand off tasks to one another.
- **Zero-Dependency Native Execution**: Uses Antigravity's built-in `browser_subagent` for E2E testing and `run_command` for execution. No Playwright or massive NPM packages required.
- **Token Optimized Object Notation (TOON)**: Strips conversational filler from configurations to maximize context window usage.
- **Semantic Code Sight**: Deep, local vector embedding searches via `osgrep` to stop hallucinated grep requests.
- **Infinite Compaction Memory**: Condenses entire conversations into the `.agent/memory/architecture-state.md` vault.

---

## Tech Stack

- **Platform**: Antigravity IDE
- **Core Engine**: Built-in LLM Prompt Engineering (`SKILL.md` format)
- **Workflows**: Global Action Definitions (`workflows/*.md`)
- **Semantic Engine**: `osgrep` (Vector embeddings over local code)
- **Execution Environment**: Native Bash (`.sh`)

---

## Prerequisites

Before installing the Dasa Sradha Kit, ensure your environment meets these requirements:

- **Antigravity IDE**: You must be running the Antigravity editor.
- **Node.js**: Version 18 or higher (required by `osgrep`).
- **NPM/Bun/Yarn**: A JavaScript package manager.
- **Git**: Required for version control and the Dasa Rsi Checkpoint / PR workflows.

---

## Getting Started

### 1. Install Prerequisites

First, install the Semantic Engine (`osgrep`) so Dasa Dwipa (The Scout) has semantic vision:

```bash
npm install -g osgrep
```

### 2. Install the Dasa Sradha Kit Globally

#### Option A: Native Antigravity Installation (Recommended)
You can simply ask your Antigravity AI agent to install the kit for you. Just copy and paste this prompt into your IDE:
> "Please install the Dasa Sradha Kit globally for me. Clone the repository at `https://github.com/TudeOrangBiasa/dasa-sradha-kit.git` into a temporary directory if needed, run the `npm install -g osgrep` prerequisite and the `./install.sh` script, and then initialize the kit in the current repository using the `/home/$USER/.gemini/scripts/dasa-init` script."

#### Option B: Manual Installation

Clone the repository and run the global installer. This will inject the 10 Personas and the global Slash Commands directly into your Antigravity `~/.gemini/` brain.

```bash
# Clone the repo locally
git clone https://github.com/TudeOrangBiasa/dasa-sradha-kit.git
cd dasa-sradha-kit

# Run the installer
chmod +x install.sh
./install.sh
```

### 3. Initialize Your Project Workspace

Navigate to the project directory you actually want to work on (e.g., your SaaS app, your game, your website) and orchestrate the kit:

```bash
cd /path/to/your/actual/project
/home/$USER/.gemini/scripts/dasa-init
```

This generates your `dasa.config.toon` file and builds the `.artifacts/` folder.

---

## Architecture Overview

### Directory Structure (Inside Antigravity `~/.gemini/`)

```
├── workflows/                # Global Slash Commands
│   ├── dasa-assimilate.md    # Codebase Assimilation Protocol
│   ├── dasa-commit.md        # Atomic Checkpoints & QA
│   ├── dasa-docs.md          # Collaborative API Documentation
│   ├── dasa-e2e.md           # Native Browser Automation
│   ├── dasa-fix.md           # Auto-Heal Orchestrator
│   ├── dasa-init.md          # Project Initialization
│   ├── dasa-plan.md          # Architectural Planning
│   ├── dasa-pr.md            # GitHub Auto-Reviewer
│   ├── dasa-seed.md          # Database Fixture Generation
│   ├── dasa-start-work.md    # Core Execution Engine
│   ├── dasa-status.md        # Progress Tracking
│   ├── dasa-sync.md          # Infinite Memory Compaction
│   └── dasa-uninstall.md     # Kit Removal
├── skills/                   # The 10 Personas
│   ├── dasa-dwipa/           # The Scout (Semantic Search / Context Gathering)
│   ├── dasa-patih/           # The Mastermind (Task Planning)
│   ├── dasa-mpu/             # The Architect (Backend / Data Modeling)
│   ├── dasa-nala/            # The Builder (Frontend / UI / Styling)
│   ├── dasa-rsi/             # The Analyst (Security / PR Reviews)
│   ├── dasa-indra/           # The QA Investigator (E2E Testing / Automation)
│   ├── dasa-dharma/          # The Maintainer (CI/CD / Package Management)
│   ├── dasa-widya/           # The Researcher (Docs / Exploration)
│   ├── dasa-sastra/          # The Writer (API Specs / Copywriting)
│   └── dasa-brahma/          # The Vanguard (Blue-Sky Prototyping)
```

### The Orchestration Lifecycle

1. **Initialization (`/dasa-init`)**: The user defines their tech-stack and repositories in `dasa.config.toon`.
2. **Analysis (`/dasa-plan`)**: The User requests a feature. Dasa Patih drafts a comprehensive execution plan in `.artifacts/task.md`.
3. **Execution (`/dasa-start-work`)**: The Orchestrator reads `task.md`. It automatically selects the correct Persona (Auto-Routing), routes them to the correct workspace (e.g., frontend vs backend), and executes the code block.
4. **Validation (`/dasa-status`)**: The AI updates `task.md` until the feature is complete.

### 🤖 Auto-Routing (Zero Learning Curve)
You do **not** need to manually tag `@dasa-mpu` or `@dasa-nala` if you don't want to!
Simply use `/dasa-plan` and `/dasa-start-work`. 

**The Orchestrator will automatically:**
1. Silently analyze your request.
2. Detect the required domain (frontend, backend, security, testing).
3. Select the best Dasa Persona for the job.
4. Auto-route to the correct repository workspace.

---

## Available Commands

Once installed, use these Global Slash Commands anywhere in Antigravity:

| Command | Description |
| :--- | :--- |
| `/dasa-plan` | **The Architect**: Reads your config and breaks down massive user requests into strict phase-gated tasks natively saved to `.artifacts/task.md`. |
| `/dasa-start-work` | **The Orchestrator**: The engine. It autonomously loops through `task.md`, selects the correct Persona, and executes the native IDE tools to write your code. |
| `/dasa-status` | Displays the current progress and active task state from the plan. |
| `/dasa-docs` | **The API Documentator**: Collaboratively invokes Dwipa, Mpu, and Sastra to generate Postman Collections or OpenAPI/Swagger specs. |
| `/dasa-e2e` | **Native Browser Automation**: Commands Dasa Indra to natively hook into Antigravity's `browser_subagent` and record `.webp` videos of the test. |
| `/dasa-seed` | **Database Fixtures**: Dwipa reads schemas, Mpu generates a massive payload of highly realistic JSON data, and Nala injects it. |
| `/dasa-pr` | **GitHub Auto-Reviewer**: Integrates natively with `gh pr diff`. Dasa Rsi executes adversarial security heuristics on your PR. |
| `/dasa-sync` | **Infinite Memory Session Compaction**: Aggressively compresses today's work into a dense `architecture-state.md` vault for tomorrow. |

---

## Testing & Quality Assurance

Dasa Sradha natively implements End-to-End browser testing without third-party tools like Puppeteer or Playwright. 

To run E2E visual tests:
1. Spin up your local development server (e.g., `npm run dev` running on `localhost:3000`).
2. Run `/dasa-e2e`.
3. Tell Dasa Indra what to do: *"Go to localhost:3000, wait for the red div to appear, type 'admin' in the username box, and click Submit."*

The native `browser_subagent` will autonomously execute these instructions, verify the DOM, and save a full `.webp` recording directly to your `.artifacts/` folder.

---

## Extensibility

### 🧩 Integrating Community "Awesome Skills"
Dasa Sradha maps external community skills directly into the orchestrator. If you want to use the [antigravity-awesome-skills](https://github.com/sickn33/antigravity-awesome-skills) package:

1. Clone `antigravity-awesome-skills` onto your local machine.
2. Add the absolute paths to your `dasa.config.toon`:
```yaml
external_skills:
  - "/path/to/antigravity-awesome-skills/skills/nextjs-expert"
  - "/path/to/antigravity-awesome-skills/skills/prisma-schema-builder"
```
3. When `/dasa-start-work` triggers, the assigned Persona will organically read and obey these external guidelines before executing their task.

---

## Deep Dives

*   Read [HOW_IT_WORKS.md](HOW_IT_WORKS.md) for the complete Architectural Manual.
*   Read [CONTRIBUTING.md](CONTRIBUTING.md) to learn how to forge new Personas and Workflows.
*   See the [CHANGELOG.md](CHANGELOG.md) for the latest updates.
