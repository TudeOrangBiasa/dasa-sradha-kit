# Scenario: Building a Company Profile with Dasa Sradha Kit & Antigravity IDE

This guide demonstrates how a developer can use the **Dasa Sradha Kit** native workflows alongside external skills (like those from [antigravity-awesome-skills](https://github.com/sickn33/antigravity-awesome-skills)) to build a 5-10 page Astro company profile entirely within the Antigravity IDE.

---

## Phase 1: Global Setup (One-Time)

Before starting the project, the developer ensures both kits are installed globally in their Antigravity IDE environment.

1. **Install Awesome Skills:**
   ```bash
   git clone https://github.com/sickn33/antigravity-awesome-skills.git /tmp/skills
   cp /tmp/skills/skills/*.md ~/.gemini/antigravity/skills/
   ```
2. **Install Dasa Sradha Kit:**
   ```bash
   git clone <dasa-sradha-repository-url> /tmp/dasa
   cd /tmp/dasa
   ./install.sh
   # This installs dasa-init, the 5 workflow templates, and the 10 Dasa personas.
   ```

---

## Phase 2: Project Initialization

The developer creates a new folder for the Astro site and initializes Dasa Sradha.

1. **Create Repo & Init Astro:**
   ```bash
   mkdir company-profile && cd company-profile
   npm create astro@latest ./ -- --template basics --yes
   git init
   ```
2. **Bootstrap Dasa Sradha Kit:**
   ```bash
   ~/.gemini/scripts/dasa-init
   ```
   *What happens:* The script creates the `.dasa-sradha` guard file and copies the `dasa-plan.md`, `dasa-start-work.md`, etc., straight into `company-profile/.agent/workflows/`.  
   *The Result:* The Antigravity IDE immediately registers `/dasa-plan`, `/dasa-start-work`, and `/dasa-status` as native slash commands in the chat window.

---

## Phase 3: Project Planning (`/dasa-plan` + Mpu)

The developer uses the IDE chat window to engage the Dasa planning workflow.

**User Prompt in IDE Chat:**
> `/dasa-plan` "We need to build a modern 7-page company profile using Astro and TailwindCSS. It needs a Home, About, Services, Portfolio, Blog, Career, and Contact page. Please use @dasa-mpu to design the technical architecture and task breakdown."

**What Antigravity Does:**
1. Recognizes the `/dasa-plan` workflow.
2. Checks for the `.dasa-sradha` guard file.
3. Invokes the **Mpu** persona (who outputs in Bahasa Indonesia).
4. **Mpu** creates `.artifacts/plans/plan-company-profile-v1.md` containing the data architecture, Astro routing structure, and a step-by-step checklist of the pages to build.

---

## Phase 4: Execution & Implementation (`/dasa-start-work` + Hybrid Skills)

With the plan created, the developer starts working through the tasks. This is where the magic of combining Dasa orchestration with specialized execution skills shines.

**User Prompt in IDE Chat (Task 1):**
> `/dasa-start-work` "Task 1: Setup Layout and Tailwind"  
> "@frontend-expert (from awesome-skills), please install Tailwind for this Astro project and set up the main `Layout.astro` file according to the plan."

**What Antigravity Does:**
1. `/dasa-start-work` logs the session start in `.artifacts/notepads/session.md` (e.g., "Starting Task 1...").
2. The `@frontend-expert` persona perfectly executes the Tailwind config and writes the layout code.

**User Prompt in IDE Chat (Task 2):**
> `/dasa-start-work` "Task 2: Build Homepage"  
> "@dasa-nala please build the `src/pages/index.astro` hero section and feature grid based on Mpu's design."

**What Antigravity Does:**
1. Tracks the task in the session log.
2. **Nala** (The Builder) writes the Astro component code and responds in Bahasa Indonesia.

---

## Phase 5: Verification & QA (Indra)

After a few pages are built, the developer needs to ensure everything is working securely.

**User Prompt in IDE Chat:**
> "@dasa-indra please run the Astro dev server, crawl the local pages to ensure no 404s, and verify the forms on the Contact page."

**What Antigravity Does:**
1. **Indra** executes `npm run dev` in the background.
2. Indra checks the routes, verifies the layout, and generates an evidence report in `.artifacts/evidence/qa-report-1.md` detailing the test results.

---

## Phase 6: Reporting & Handoff (`/dasa-status` + Sastra)

The developer needs to hand the project over to the client or a teammate.

**User Prompt in IDE Chat:**
> `/dasa-status`

**What Antigravity Does:**
1. Reads the plans and session logs.
2. Outputs a clean status report in the chat: "Status: 5/7 pages complete. Blockers: Waiting on client SVG logo for the header."

**User Prompt in IDE Chat:**
> "Great job. @dasa-sastra, please write a comprehensive `README.md` for this repository explaining how to run the Astro site and deploy it."

**What Antigravity Does:**
1. **Sastra** creates a beautiful, bilingual (EN/ID) README detailing the `npm run build` steps and Tailwind configuration.

---

### Summary of the Flow
- **Global `install.sh`** gets the tools onto the machine.
- **`dasa-init`** securely brings the framework into the specific project.
- **Dasa Workflows (`/dasa-plan`, etc.)** enforce structure, create artifacts, and manage the state.
- **Dasa Personas (`@dasa-mpu`, `@dasa-nala`)** provide culturally-aligned, heavily contextualized AI guidance and orchestration in Bahasa.
- **Awesome Skills (`@frontend-expert`)** seamlessly drop in to do highly specific functional tasks when needed.
