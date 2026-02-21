# Contributing to the Dasa Sradha Kit

Welcome! We are thrilled that you want to contribute to the **Dasa Sradha Kit**. This project is built by the community, for the community, to supercharge the Antigravity IDE with Autonomous Agentic Workflows.

Whether you are fixing a typo, adding a new Persona skill, or building a V4 workflow, your contributions are highly valued.

---

## 🏗️ Project Structure
To contribute effectively, you need to understand how the Kit is organized. Everything is built using native Markdown (`.md`) and Shell (`.sh`) scripts to adhere to the **Zero-Dependency** philosophy.

```text
dasa-sradha-kit/
│
├── workflows/                # The Global Slash Commands (e.g., /dasa-plan)
│   ├── dasa-init.md          # Bootstraps a new repository
│   ├── dasa-e2e.md           # Native Browser Subagent Testing
│   └── ...                   
│
├── skills/                   # The 10 Personas (Dasa Sradha)
│   ├── dasa-mpu/             # The Architect
│   │   ├── SKILL.md          # The core AI system prompt & heuristics
│   │   ├── resources/        # Static guidelines (e.g., design-memory.md)
│   │   └── scripts/          # Executable tools for the Persona
│   ├── dasa-nala/            # The Builder
│   └── ...                   
│
├── install.sh                # The global installer script
├── HOW_IT_WORKS.md           # The core architecture guide
└── README.md                 # Public documentation
```

---

## 🛠️ How to Contribute

### 1. Fork the Repository
Click the **Fork** button at the top right of this repository to create your own copy.

### 2. Clone Your Fork
Open your terminal and run:
```bash
git clone https://github.com/YOUR_USERNAME/dasa-sradha-kit.git
cd dasa-sradha-kit
```

### 3. Create a Feature Branch
Always create a new branch for your changes instead of committing directly to `master`.
```bash
git checkout -b feature/my-awesome-new-workflow
```

### 4. Make Your Changes
- **Adding a Workflow:** Create a new markdown file in `workflows/` and ensure you update `scripts/dasa-init` so the installer knows to copy your new file into user directories. Update `README.md` to list the new command.
- **Updating a Persona:** Modify the `SKILL.md` file inside the `skills/` directory. If you add a script (e.g., an OSGrep wrapper), make sure it is actively referenced in the Persona's rules so they know it exists.

### 5. Test Your Changes Locally
Run `./install.sh` on your local machine to globally install your modified version into Antigravity (`~/.gemini/`). 
Initialize an empty folder (`/dasa-init`) and test that your new workflow or Persona behaves as expected.

### 6. Commit and Push
Use Conventional Commits (e.g., `feat:`, `fix:`, `docs:`).
```bash
git add .
git commit -m "feat: added a new automated deployment workflow"
git push origin feature/my-awesome-new-workflow
```

### 7. Open a Pull Request (PR)
Navigate back to the original `TudeOrangBiasa/dasa-sradha-kit` repository on GitHub and click **Compare & pull request**. 
Provide a detailed description of what you changed, why you changed it, and how you tested it.

*(Fun fact: If you are using the Kit, you can actually run `/dasa-pr` to have Dasa Rsi automatically review your PR before submitting it!)*

---

## 📜 Coding Guidelines & Philosophy

When building for Dasa Sradha, please adhere to these core principles:
1. **Zero-Dependency where possible.** We prefer relying on Antigravity's native tools (like `browser_subagent`) rather than forcing users to install massive NPM packages (like Playwright).
2. **Token Efficiency (TOON).** If a Persona is generating data, favor compact JSON/YAML (TOON format) over conversational prose to save the user's LLM context window.
3. **Bahasa Indonesia Outputs.** While the internal `SKILL.md` reasoning and source code should be written in English for the AI, the Personas MUST respond to the user and generate reports (like `walkthrough.md`) in Bahasa Indonesia.

Thank you for helping us build the ultimate Agentic Framework!
