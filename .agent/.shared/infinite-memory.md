# Infinite Memory & Compaction Protocol

As a Dasa Persona, you are responsible for maintaining a completely deterministic, offline "brain" for the workspace to prevent AI amnesia.

## 1. The 5-Sector TOON Memory Vault (`.artifacts/dasa_memory.toon`)
All irreversible decisions, architectural blueprints, and critical dependencies must be written to the centralized Temporal Knowledge Graph. 

When working on a project, always read the 5 memory sectors:
- **Episodic:** Events (e.g., User asked to switch to SQLite)
- **Semantic:** Facts (e.g., App runs on port 3000)
- **Procedural:** Skills (e.g., Deployment instructions)
- **Emotional:** Preferences (e.g., User strictly hates Tailwind classes)
- **Reflective:** Insights (e.g., Our last build failed because of an outdated dependency)

## 2. Compaction (Dasa Patih Only)
LLM Context Windows overflow over time. When a session passes 30+ tool calls, the Orchestrator MUST invoke `.agent/scripts/compact_memory.py <sector> <knowledge>`.
1. Distill all active codebase learnings into high-density facts.
2. Execute the python script mapping the knowledge to a specific sector.
3. Instruct the LLM that the session has been compacted and older context can be safely ignored.
