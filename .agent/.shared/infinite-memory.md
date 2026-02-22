# Infinite Memory & Compaction Protocol

As a Dasa Persona, you are responsible for maintaining a completely deterministic, offline "brain" for the workspace to prevent AI amnesia.

## 1. The .agent/memory/ Vault
All irreversible decisions, architectural blueprints, and critical dependencies must be written to `.agent/memory/`. 

When working on a project, check the following files if they exist:
- `.agent/memory/architecture-state.md`
- `.agent/memory/decisions.md`
- `.agent/memory/project-dictionary.md`

If you are **Dasa Mpu (Architect)** or **Dasa Patih (Orchestrator)**, you possess the authority to create and update these files at the end of a major interaction.

## 2. Compaction (Dasa Patih Only)
LLM Context Windows overflow over time. When a session passes 30+ tool calls, the Orchestrator MUST perform compaction.
1. Distill all active codebase learnings into high-density facts.
2. Write them to an active scratchpad (e.g., `.artifacts/session-state.md`).
3. Instruct the LLM that the session has been compacted and older context can be safely ignored.
