# Contributing to Dasa Sradha Kit

Thank you for your interest in contributing! This guide explains how to add new Personas, Workflows, and Scripts.

---

## Prerequisites

- Node.js 18+
- Python 3.8+
- Antigravity IDE
- Git

---

## Project Structure

```
dasa-sradha-kit/
├── .agent/
│   ├── agents/          ← 10 Persona definitions
│   ├── rules/GEMINI.md  ← Global constraints (P0)
│   ├── scripts/         ← 17 Python scripts
│   ├── skills/          ← Modular domain resources
│   ├── workflows/       ← 16 Slash Commands
│   └── .shared/         ← Common templates
├── bin/                 ← CLI entry points
├── docs/                ← Additional documentation
├── package.json         ← NPM package definition
└── README.md
```

---

## Adding a New Persona

1. Create `.agent/agents/dasa-<name>.md` with this template:

```yaml
---
name: dasa-<name>
description: "What this persona does."
model: "Gemini 3.1 Pro"
---
```

2. Add sections: `Persona Description`, `Technical Implementation`, `Quality Control`.
3. Register the persona in `bin/dasa-cli.js` PERSONAS array.
4. All Personas MUST obey `.agent/rules/GEMINI.md` (SOLID, TDD, Methods < 10 lines).

---

## Adding an Auto-Routing Scenario

To teach the AI to trigger a new action automatically without a slash command:
1. Open `.agent/.shared/dasa-cheat-sheet.toon`.
2. Locate the `auto_routing_engine.scenarios` object.
3. Add a new Scenario (e.g., `I_NEW_SCENARIO_NAME`).
4. Define the `intent_pattern` (natural language triggers), the `auto_workflow` steps, and the `goal`.

---

## Adding a New Workflow

1. Create `.agent/workflows/dasa-<name>.md` with this template:

```yaml
---
description: Short description. Example: /dasa-<name> "arguments"
---
```

2. Include these mandatory sections:
   - **Guard Check**: Verify `dasa.config.toon` exists.
   - **Stack Detection**: Read `dasa.config.toon` for framework info.
   - **Execution Pipeline**: Define strict Persona handoffs.
   - **Expected Output**: Define the success message format.

3. All workflows MUST respect `dasa.config.toon` — never hardcode frameworks.

---

## Adding a New Script

1. Create `.agent/scripts/<name>.py`.
2. Scripts MUST be:
   - **Zero-dependency**: Standard library only (`os`, `sys`, `re`, `ast`, `json`, `pathlib`).
   - **Cross-platform**: No bash, no Windows-only APIs.
   - **Executable**: Include `#!/usr/bin/env python3` shebang.
3. Run `chmod +x .agent/scripts/<name>.py`.
4. Document the script in `.agent/ARCHITECTURE.md`.

---

## Code Quality Rules

All contributions MUST adhere to the constraints in `.agent/rules/GEMINI.md`:

- **Methods**: Strictly < 10 lines
- **Classes**: Strictly < 50 lines
- **TDD**: Write tests before implementation
- **No hardcoded versions**: Always detect or query the latest

---

## Submitting Changes

1. Fork the repository.
2. Create a feature branch: `git checkout -b feat/new-workflow`.
3. Make your changes following the guidelines above.
4. Test locally with `npx dasa-cli up`.
5. Submit a Pull Request.

---

## License

MIT — See [LICENSE](LICENSE).
