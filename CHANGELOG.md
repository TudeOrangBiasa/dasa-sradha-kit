# Changelog

All notable changes to Dasa Sradha Kit will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.0] - 2026-02-20

### Added
- **Workflows-only architecture**: Repo-local workflows in `.agent/workflows/` via bootstrap
- **Bootstrap command**: `/dasa-init` copies master workflow templates into project
- **10 Indonesian persona skills**: Flat structure in `~/.gemini/antigravity/skills/dasa-*.md`
  - dasa-patih (Orchestrator), dasa-mpu (Architect), dasa-nala (Builder)
  - dasa-rsi (Consultant), dasa-sastra (Writer), dasa-widya (Researcher)
  - dasa-indra (Tester), dasa-dharma (Security), dasa-kala (Quick Fix), dasa-dwipa (Explorer)
- **Activation guard**: `.dasa-sradha` marker file (empty) at repo root
- **Backend scripts**: `dasa-init`, `dasa-uninstall` in `~/.gemini/scripts/`
- **Master workflow templates**: Stored in `~/.gemini/scripts/dasa-sradha-kit/workflows/`
- **Core workflows**: `/dasa-plan`, `/dasa-start-work`, `/dasa-status`, `/dasa-uninstall`
- **Bilingual documentation**: English + Bahasa Indonesia README
- **MIT License**: Open source release

### Changed
- **Install method**: Global install + per-repo bootstrap (Option C architecture)
- **Skills structure**: Migrated from nested directories to flat file naming
- **Activation mechanism**: `.dasa-sradha` marker replaces `GEMINI.md` guard
- **Documentation**: Complete rewrite for workflows-only architecture

### Removed
- **Legacy command system**: TOML manifests + Python wrappers (`commands/` directory)
- **Boulder utilities**: Removed `boulder-*` scripts (future: native workflows implementation)
- **Global workflows**: No longer assumes global workflow paths in Antigravity
- **GEMINI.md guard**: Moved to `docs/` as historical reference only

## Release Process

### Creating a Release

1. Update `CHANGELOG.md` with release date and notes
2. Commit changes: `git add CHANGELOG.md && git commit -m "Release v1.0.0"`
3. Create annotated tag: `git tag -a v1.0.0 -m "v1.0.0: Workflows-only public release"`
4. Push with tags: `git push origin main --tags`

### Version Numbering

- **MAJOR**: Breaking changes to install/usage patterns
- **MINOR**: New features, new personas, new workflows
- **PATCH**: Bug fixes, documentation updates

[Unreleased]: https://github.com/YOUR_USER/dasa-sradha-kit/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/YOUR_USER/dasa-sradha-kit/releases/tag/v1.0.0
