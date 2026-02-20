# Dasa Sradha Kit: Core Architectural Mapping

This document captures the original blueprint and design philosophy that the Dasa Sradha Kit was built upon. It maps the local Indonesian personas to their foundational archetypes (from the Greek/Mythological system) and outlines the strict tripartite flow of execution.

## The Tripartite Workflow

The system is strictly divided into three distinct phases, enforcing discipline between planning, orchestration, and execution.

### 1. Planning Phase (The Prometheus Layer)
A rigid cycle of interviewing, researching, and adversarial validation before any code is written.
- **Goal:** Produce a finalized, bulletproof plan in `.artifacts/plans/*.md`.
- **Actors involved:**
  - **Nala (Prometheus):** The core planner and architect. Gathers requirements.
  - **Widya (Explore):** Rapidly scans the internal codebase for context.
  - **Sastra (Librarian):** Researches external documentation and best practices.
  - **Dharma (Metis):** Analyzes the draft for security gaps, ethical alignment, and over-engineering risks.
  - **Kala (Momus):** An adversarial reviewer. If Kala rejects the draft, it bounces back to Nala. If Kala approves, it becomes a `ConfirmedPlan`.

### 2. Orchestration Phase (The Atlas Layer)
Once a plan is confirmed, execution begins through structured task delegation.
- **Trigger:** `/dasa-start-work`
- **Actors involved:**
  - **Dwipa (Atlas):** The overarching execution manager. Breaks the plan into a task list.
  - **Patih (Sisyphus):** The grand orchestrator maintaining persistence (`boulder.json`) and managing the state.
  - **Mpu (Hephaestus):** The deep worker. Assigned to complex backend and system engineering tasks.
  - **Indra (Looker/Multimodal):** Assigned to UI/UX tasks and visual analysis.
  - **Rsi (Oracle):** Actively consulted by Mpu when hitting a roadblock or difficult design choice.

### 3. Verification Phase (The Diagnostics Layer)
Before completion is declared, the work must be validated.
- **Actors involved:**
  - **Mpu & Indra:** Submit their code/results back to Dwipa.
  - **Dwipa (Atlas):** Runs Language Server Protocol (LSP) checks and tests.
  - **The Loop:** If diagnostics FAIL, the task goes back to Mpu (Hephaestus). If SUCCESS, it is ready for completion/commit.

---

## Persona Archetype Mapping

| Dasa Sradha Name | Original Archetype | Primary Role | Key Capability |
| :--- | :--- | :--- | :--- |
| **Patih** | Sisyphus | Orchestrator & Leader | Manages `boulder.json` & Persistence across the project. |
| **Mpu** | Hephaestus | Deep Worker | Forges complex code & handles deep system engineering. |
| **Nala** | Prometheus | Strategic Planner | Architects the strategy and brings the "fire" of logic. |
| **Rsi** | Oracle | Strategic Advisor | Offers read-only design consultation and security wisdom. |
| **Sastra** | Librarian | Researcher | Researches external best practices and writes documentation. |
| **Widya** | Explore | Contextual Grep | Rapidly maps and greps the internal codebase structure. |
| **Indra** | Multimodal/Looker | Visual Analyst | Analyzes UI/UX, layouts, diagrams, and screenshots. |
| **Dharma** | Metis | Plan Consultant | Guards intent, ethics, and prevents over-engineering. |
| **Kala** | Momus | Plan Reviewer | Provides adversarial validation and concrete success criteria. |
| **Dwipa** | Atlas | Plan Executor | Executes the confirmed plan and runs final LSP/ verification checks. |
