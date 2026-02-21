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

Dasa Sradha uses a **Persona-based Orchestration** model natively integrated with Antigravity IDE. It splits complex software workflows into 10 distinct personas (e.g., Architect, Implementer, Debugger, Reviewer) and defines clear, phase-gated slash commands governed by a strict `dasa.config.yaml` file.

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
| `/dasa-init` | `dasa-init.md` | Bootstraps the current repository with `.artifacts/`, `.agent/`, and `boulder.json`. |
| `/dasa-plan` | `dasa-plan.md` | Generates a structured execution plan. **Stops automatically** for Persona review. |
| `/dasa-start-work` | `dasa-start-work.md` | Executes the next task on the plan using the chosen persona's specific abilities. |
| `/dasa-status` | `dasa-status.md` | Displays the current progress and active task state from the plan. |
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
Instead of manually typing out your `dasa.config.yaml` file, you can "vibe code" it by asking a fast, cheap model (like Gemini Flash) to interview you. 

Run `/dasa-init` and then ask your AI:
> "I want to build a new SaaS app. Ask me questions one-by-one to figure out my ideal frontend/backend stack, and then automatically populate the `.agent/dasa.config.yaml` file for the Dasa Sradha Personas."

## 🧩 Installing Community Awesome Skills
Dasa Sradha is built to be a zero-dependency powerhouse natively, but you can absolutely augment it with community skills from the [antigravity-awesome-skills](https://github.com/sickn33/antigravity-awesome-skills) repository!

**How to Integrate:**
1. Use `npx` or manually clone the `antigravity-awesome-skills` repository into your desired location.
2. Add the paths of the skills you want to use directly into your `dasa.config.yaml` file under an `external_skills` array.
3. If Dasa Mpu or Dasa Sastra see those skills defined in your config, they are permitted to read those files before writing their code.

Example `dasa.config.yaml` addition:
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
<summary><strong>2. Risk Analysis (Widya)</strong></summary>

Ask the Risk Analyst to evaluate potential pitfalls with third-party payment APIs:
```text
@dasa-widya analyze potential edge cases and API rate-limiting risks for Stripe integration.
```
</details>

<details>
<summary><strong>3. Architecture & Planning (Patih)</strong></summary>

With research complete, ask the Architect to draft the technical plan:
```text
/dasa-plan "Create a new Payment Gateway module using Stripe, considering Indra and Widya's findings."
```
*Once the plan is generated, the workflow halts.*
</details>

<details>
<summary><strong>4. Orchestration & Delegation (Nala)</strong></summary>

Tag the Orchestrator to review the plan and prepare the execution order:
```text
@dasa-nala review the plan in .artifacts/plans/ and outline the task priorities. /dasa-start-work
```
</details>

<details>
<summary><strong>5. Scheduling & Dependency Management (Kala)</strong></summary>

Before coding, ensure database migrations happen before API endpoints:
```text
@dasa-kala review the dependencies and ensure the database schema task is executed first.
```
</details>

<details>
<summary><strong>6. Library & Documentation Prep (Sastra)</strong></summary>

Gather external documentation for the implementer:
```text
@dasa-sastra please fetch the latest Stripe Node.js SDK documentation and save it to .artifacts/
```
</details>

<details>
<summary><strong>7. Implementation & Coding (Mpu)</strong></summary>

When it's time to write the actual code, tag the Implementer:
```text
@dasa-mpu please execute the coding tasks outlined in the plan using the Stripe SDK docs. /dasa-start-work
```
</details>

<details>
<summary><strong>8. Debugging (Rsi)</strong></summary>

If a web-hook test fails during implementation:
```text
@dasa-rsi the Stripe webhook signature verification is failing. Please analyze the logs and fix the root cause.
```
</details>

<details>
<summary><strong>9. Code Review & QA (Dwipa)</strong></summary>

Once coding and debugging are complete, bring in the QA reviewer:
```text
@dasa-dwipa please verify the code quality, unit tests, and coverage for the payment gateway.
```
</details>

<details>
<summary><strong>10. Security Audit & Ethics (Dharma)</strong></summary>

Finally, ensuring PCI-compliance and security:
```text
@dasa-dharma please audit the new payment implementation for security vulnerabilities and ensure no sensitive data is logged.
```
</details>

---

### 💻 Pseudocode Logic

To understand how the Dasa Sradha system natively routes tasks without external Python scripts, here is pseudo-code modeling the prompt logic and execution flow governed by `boulder.json` and `.artifacts`:

```javascript
function executeDasaWorkflow(userRequest, currentPlan) {
    // 1. Guard Check
    if (!fileExists(".dasa-sradha")) {
        return FAIL("Repository not initialized. Run /dasa-init");
    }

    // 2. Identify Persona Command
    const taggedPersona = extractMentions(userRequest); // e.g., "@dasa-mpu"
    
    // 3. Load State
    let taskState = loadArtifact(".artifacts/boulder.json");
    
    // 4. Route to Skill Context
    let personaPrompt = null;
    switch (taggedPersona) {
        case "dasa-patih": personaPrompt = loadSkill("High-Level Architect"); break;
        case "dasa-mpu":   personaPrompt = loadSkill("Feature Implementer"); break;
        case "dasa-rsi":   personaPrompt = loadSkill("Root Cause Debugger"); break;
        case "dasa-dwipa": personaPrompt = loadSkill("QA Code Reviewer"); break;
        // ... (routes for all 10 personas)
        default:           personaPrompt = loadSkill("General Assistant"); break;
    }

    // 5. Context Injection & Execution
    let systemPrompt = merge(personaPrompt, taskState, currentPlan);
    let output = LLM.generate(systemPrompt, userRequest);
    
    // 6. State Persistence
    if (workflow === "/dasa-plan") {
        saveArtifact(".artifacts/plans/", output);
        return HALT_FOR_USER_REVIEW(output);
    } else {
        updateBoulderJson(output.newProgress);
        return output;
    }
}
```



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
