# Antigravity Native Skill Routing Guide

This guide explains how skills are routed and selected in the Antigravity native workflow system, using the persona skills in `~/.gemini/antigravity/skills/`.

## Routing Taxonomy

Skills are selected using a three-tier routing strategy based on the task text:

1.  **Triggers**: Primary intent keywords.
2.  **Domains**: Broad work area categories.
3.  **Complexity**: Estimated effort level (low, medium, high).

### Scoring Formula

The system uses a deterministic scoring formula to rank candidate skills:

```
score = (trigger_hits * 10) + (domain_hits * 3) + (persona_bonus * 2) + (complexity_bonus * 1) + priority
```

- **Trigger Hits (10x)**: Matching a keyword from the `triggers` list is the strongest signal.
- **Domain Hits (3x)**: Overlap between the task's domain and the skill's `domains` list.
- **Persona Bonus (2x)**: Matches the `recommended_persona` if provided in the task context.
- **Complexity Bonus (1x)**: Matches the `complexity` level requested.
- **Priority**: A static tie-breaker defined in the `SKILL.md` frontmatter.

## Progressive Disclosure Patterns

The `requires` field in the frontmatter allows skills to be composed without bloating the primary skill file.

- **Example**: The `dasa-patih` (High Complexity) requires both `dasa-mpu` and `dasa-rsi`.
- When `dasa-patih` is loaded, the runner also provides the context from the required skills, enabling the agent to transition from planning to execution seamlessly.

## Creating New Skills

To create a new skill, follow these steps:

1.  **Define the Persona**: Choose a Dasa Sradha persona that fits the work (e.g., **Patih** for architecture, **Mpu** for implementation, **Rsi** for debugging).
2.  **Select Triggers**: List specific phrases that should activate this skill. Avoid overlap with other skills.
3.  **Tag Domains**: Use canonical tags like `planning`, `architecture`, `implementation`, `testing`, `debugging`.
4.  **Set Complexity**: Estimate the effort required.
5.  **Write the Body**: Include `## Purpose`, `## When to Use`, `## Approach`, and `## Examples`.

## Testing Skill Matching

You can simulate routing results by analyzing the task text against the example skills:

- **Prompt**: "I need a technical blueprint for a new service."
    - `dasa-patih` matches "technical blueprint" (Trigger Hit) -> Score ~10+ (High)
    - `dasa-mpu` matches nothing -> Score 0
    - **Result**: `dasa-patih` is selected.

- **Prompt**: "Fix the typo in the login page."
    - `dasa-rsi` matches "fix" (partial) or "bug" (if mentioned).
    - If `fix bug` is the trigger, and "Fix" is in the prompt, it hits.
    - **Result**: `dasa-rsi` wins for low-complexity, tactical tasks.

## Anti-Patterns to Avoid

- **Trigger Bloat**: Don't add generic triggers like "code" or "work" that match everything.
- **Persona Mismatch**: Using an implementation-heavy skill with a planning persona.
- **Circular Requirements**: Skill A requiring Skill B which requires Skill A.
