# Dasa Sradha Kit

Multi-agent orchestration framework Uses a workflows-only architecture for task planning, strict continuation, and Indonesian persona-based skill routing.

---

## 📦 What Dasa Installs

Dasa Sradha supports two initialization models: Global Installation and Local Repository Bootstrapping.

<details>
<summary><strong>Global Installation (<code>~/.gemini/</code>)</strong></summary>

Running `./install.sh` from this repository installs these tools globally to your environment:
- `~/.gemini/scripts/dasa-init`: Bootstrap script for initializing new repositories.
- `~/.gemini/scripts/dasa-uninstall`: Global kit uninstaller script.
- `~/.gemini/antigravity/workflows/dasa-sradha-kit/`: Master workflow templates that power the `/dasa-` slash commands natively in the IDE.
- `~/.gemini/antigravity/skills/`: The 10 distinct persona skill definitions, mapped as `dasa-*/SKILL.md` folders.
</details>

<details>
<summary><strong>Local Project Bootstrapping (<code>/dasa-init</code>)</strong></summary>

Running the `/dasa-init` slash command inside a repository creates the local framework state:
- `.dasa-sradha`: Activation guard marker file to prevent accidental runs elsewhere.
- `.agent/workflows/`: Local copies of the workflow templates.
- `.artifacts/`: The designated directory for state management, task evidence files, and output logs.
- `.artifacts/plans/`: Generates structured markdown execution plans.
- `boulder.json`: Sets the default system prompts and operational configurations for the IDE.
</details>

---

## ⚙️ How Dasa Works

Dasa Sradha uses a **Persona-based Orchestration** model natively integrated with Antigravity IDE. It splits complex software workflows into 10 distinct personas (e.g., Architect, Implementer, Debugger, Reviewer) and defines clear, phase-gated slash commands governed by a strict `dasa.config.toon` file.

👉 **[Read the Full Documentation & View the Flowchart in HOW_IT_WORKS.md](HOW_IT_WORKS.md)**

<details open>
<summary><strong>🧠 The "Max Power" Architecture (V3)</strong></summary>

Dasa Sradha is built on advanced heuristic principles to prevent AI hallucination and "slop":

*   **Adaptive Thinking:** Personas scale their effort. Simple tasks are executed instantly; complex tasks require deep planning and adversarial self-review.
*   **Design Memory:** Dasa Nala cannot hallucinate UI. It strictly reads a `.design-memory/` dictionary established by Dasa Mpu to ensure premium layout consistency.
*   **Infinite Memory:** Cross-session architecture decisions are permanently stored in an `.agent/memory/` version-controlled vault, preventing LLM amnesia.
*   **Context Compaction:** Long-running sessions are automatically condensed into dense summaries by native scripts to prevent token overflow.
*   **Native Tools:** Personas possess direct, executable scripts (e.g., semantic web searchers, static vulnerability scanners, and workspace mappers).

</details>

---

## 🔄 Available Workflows

| Slash Command | File | Description |
|---------------|------|-------------|
| `/dasa-init` | `dasa-init.md` | Bootstraps the current repository with `.artifacts/`, `.agent/`, and `dasa.config.toon`. |
| `/dasa-plan` | `dasa-plan.md` | Generates a structured `.artifacts/implementation_plan.md` and pauses for user review. |
| `/dasa-start-work` | `dasa-start-work.md` | **The Auto-Routing Orchestrator**: Automatically reads the plan, breaks it into tasks, assumes the correct Persona (Nala, Mpu, Indra, etc.) based on the domain, reads their native rules, and executes the code autonomously. |
| `/dasa-status` | `dasa-status.md` | Displays the current progress and active task state from the plan. |
| `/dasa-assimilate` | `dasa-assimilate.md` | **The Assimilation Protocol**: Run this on forked or undocumented codebases. It automatically detects your tech stack (including DDEV containers vs native NPM) and rewrites `dasa.config.toon` to perfectly match the environment. |
| `/dasa-docs` | `dasa-docs.md` | **The API Documentator**: Collaboratively invokes Dwipa (Scout), Mpu (Architect), and Sastra (Writer) to scan your defined backend workspace and autonomously generate Postman Collections or OpenAPI/Swagger `.json/.yaml` specs. |
| `/dasa-fix` | `dasa-fix.md` | **The Auto-Heal Orchestrator**: Accepts compiler or terminal errors (`/dasa-fix "error text"`) and autonomously dispatches Dasa Rsi to surgically patch the code without breaking the main plan. |
| `/dasa-sync` | `dasa-sync.md` | **Infinite Memory Session Compaction**: Aggressively compresses today's `.artifacts/` and chats into a dense `.agent/memory/architecture-state.md` vault, allowing you to close your IDE and safely restore 100% project context in a fresh chat tomorrow. |
| `/dasa-commit` | `dasa-commit.md` | **Atomic Checkpoints & QA**: Triggers Dasa Dwipa & Dharma to pre-scan the `git diff` for AI slop and leaked secrets before autonomously executing a Conventional Git Commit. |
| `/dasa-uninstall` | `dasa-uninstall.md` | Removes all local marker files, configuration, and workflows from the repository. |

---

## 🚀 How to Use It

### Option A: Manual Installation

1. **Install Globally:**
   ```bash
   git clone https://github.com/TudeOrangBiasa/dasa-sradha-kit.git
   cd dasa-sradha-kit
   ./install.sh
   ```
2. **Initialize Your Project:** Open your target project in Antigravity IDE and run:
   ```text
   /dasa-init
   ```

### Option B: AI Agent Installation (Recommended)

You can ask Antigravity (or another advanced agent) to install the kit for you by copying and pasting this prompt:

> "Please install the Dasa Sradha Kit globally for me. Clone the repository at `https://github.com/TudeOrangBiasa/dasa-sradha-kit.git` into a temporary directory if needed, run the `./install.sh` script, and then initialize it in the current repository using the `/home/$USER/.gemini/scripts/dasa-init` script."

---

## ⚡ "Vibe Coding" the Architecture (Pro Tip)
Instead of manually typing out your `dasa.config.toon` file, you can "vibe code" it by asking a fast, cheap model (like Gemini Flash) to interview you. 

Run `/dasa-init` and then ask your AI:
> "I want to build a new SaaS app. Ask me questions one-by-one to figure out my ideal frontend/backend stack, and then automatically populate the `.agent/dasa.config.toon` file for the Dasa Sradha Personas."

## 🧩 Installing Community Awesome Skills
Dasa Sradha is built to be a zero-dependency powerhouse natively, but you can absolutely augment it with community skills from the [antigravity-awesome-skills](https://github.com/sickn33/antigravity-awesome-skills) repository!

**How to Integrate:**
1. Use `npx` or manually clone the `antigravity-awesome-skills` repository into your desired location.
2. Add the paths of the skills you want to use directly into your `dasa.config.toon` file under an `external_skills` array.
3. If Dasa Mpu or Dasa Sastra see those skills defined in your config, they are permitted to read those files before writing their code.

Example `dasa.config.toon` addition:
```yaml
external_skills:
  - "/path/to/antigravity-awesome-skills/skills/nextjs-expert"
  - "/path/to/antigravity-awesome-skills/skills/prisma-schema-builder"
```

---

## 🎨 Free Figma Alternative (Batch Mockups)
If you have a massive Figma file (e.g., a 30-page dashboard) but don't want to pay for external Figma MCP tools, Dasa Sradha has a **zero-cost native alternative**.

**How to use Visual Mockups:**
1. Export your Figma screens as high-resolution `.png` or `.jpg` files.
2. Drop them all into the `.design-memory/mockups/` folder inside your project.
3. Automatically, **Dasa Nala (The Builder)** will use Antigravity's native Vision capabilities to "look" at those images before writing any UI code. It will perfectly replicate the layout, padding, and visual hierarchy directly from your images.

---

### 📖 Full Workflow Example (All 10 Personas)

Here is an advanced end-to-end lifecycle demonstrating how **all 10 personas** seamlessly hand off tasks to one another for a massive feature like a new "Payment Gateway":

<details>
<summary><strong>1. Investigation & Discovery (Indra)</strong></summary>

Before anything begins, ask the Investigator to map the current codebase and find where the payment system should integrate:
```text
@dasa-indra review the codebase and find all touchpoints for user billing.
```
</details>

<details>
With research complete, ask the Architect to draft the technical plan:
```text
/dasa-plan "Create a new Payment Gateway module using Stripe, considering Indra and Widya's findings."
```
*Once the plan is generated, the workflow halts.*
</details>




## 🎭 The 10 Personas (Dasa Sradha)

The framework is divided into 10 domains of expertise. Mentioning them with `@dasa-<name>` triggers their unique skill logic:

1. **Patih**: High-level system architect.
2. **Mpu**: Core feature implementer and coder.
3. **Nala**: Orchestrator and delegation manager.
4. **Rsi**: Deep debugger and root-cause analyst.
5. **Sastra**: Librarian, documentation, and research.
6. **Widya**: Risk analyst and edge-case specialist.
7. **Indra**: Investigator and system explorer.
8. **Dharma**: Guardian of ethics, security, and standards.
9. **Kala**: Time, dependency, and priority manager.
10. **Dwipa**: Code reviewer and QA validator.

---
*License: MIT*
