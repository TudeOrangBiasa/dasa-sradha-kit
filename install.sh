#!/usr/bin/env bash
set -euo pipefail

# ============================================================================
# Dasa Sradha Kit — Installer for Antigravity Desktop IDE (Linux)
# ============================================================================
# Installs global slash commands (/plan, /start-work), boulder utilities,
# and example skills into ~/.gemini/.
#
# Usage:
#   ./install.sh          # install (default)
#   ./install.sh uninstall  # remove installed files
# ============================================================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Target directories
SKILLS_DIR="${HOME}/.gemini/antigravity/skills"
SCRIPTS_DIR="${HOME}/.gemini/scripts"
WORKFLOWS_DIR="${SCRIPTS_DIR}/dasa-sradha-kit/workflows"

# Colors (if terminal supports it)
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

info()  { echo -e "${GREEN}[+]${NC} $*"; }
warn()  { echo -e "${YELLOW}[!]${NC} $*"; }
error() { echo -e "${RED}[x]${NC} $*" >&2; }

# ============================================================================
# Pre-flight checks
# ============================================================================

check_deps() {
    local missing=()
    command -v python3 >/dev/null 2>&1 || missing+=("python3")
    command -v bash >/dev/null 2>&1 || missing+=("bash")

    if [[ ${#missing[@]} -gt 0 ]]; then
        error "Missing required dependencies: ${missing[*]}"
        exit 1
    fi
}

# ============================================================================
# Install
# ============================================================================

do_install() {
    info "Installing Dasa Sradha Kit..."
    echo ""

    check_deps

    # 1. Create target directories
    info "Creating directories..."
    mkdir -p "$SKILLS_DIR"
    mkdir -p "$SCRIPTS_DIR"

    info "Installing backend scripts to ${SCRIPTS_DIR}/"
    for script in dasa-init dasa-uninstall; do
        cp "${SCRIPT_DIR}/scripts/${script}" "$SCRIPTS_DIR/"
        chmod +x "$SCRIPTS_DIR/${script}"
    done

    info "Installing master workflow templates to ${WORKFLOWS_DIR}/"
    mkdir -p "$WORKFLOWS_DIR"
    for workflow in dasa-init.md dasa-plan.md dasa-start-work.md dasa-status.md dasa-uninstall.md; do
        cp "${SCRIPT_DIR}/workflows/${workflow}" "$WORKFLOWS_DIR/"
    done

    info "Installing persona skills to ${SKILLS_DIR}/"
    for skill in dasa-patih.md dasa-mpu.md dasa-nala.md dasa-rsi.md dasa-sastra.md dasa-widya.md dasa-indra.md dasa-dharma.md dasa-kala.md dasa-dwipa.md; do
        cp "${SCRIPT_DIR}/skills/${skill}" "${SKILLS_DIR}/"
    done

    echo ""
    info "Installation complete!"
    echo ""
    echo "  Backend scripts installed:"
    echo "    ${SCRIPTS_DIR}/dasa-init"
    echo "    ${SCRIPTS_DIR}/dasa-uninstall"
    echo ""
    echo "  Master workflow templates:"
    echo "    ${WORKFLOWS_DIR}/"
    echo "    (5 workflows: init, plan, start-work, status, uninstall)"
    echo ""
    echo "  Persona skills installed (flat):"
    echo "    ${SKILLS_DIR}/dasa-patih.md ... dasa-dwipa.md (10 total)"
    echo ""
    echo "  To activate in a project:"
    echo "    cd <your-project> && ${SCRIPTS_DIR}/dasa-init"
}

# ============================================================================
# Uninstall
# ============================================================================

do_uninstall() {
    warn "Uninstalling Dasa Sradha Kit..."
    echo ""

    local files=(
        "${SCRIPTS_DIR}/dasa-init"
        "${SCRIPTS_DIR}/dasa-uninstall"
    )

    for f in "${files[@]}"; do
        if [[ -f "$f" ]]; then
            rm "$f"
            info "Removed $f"
        fi
    done

    for skill in dasa-patih.md dasa-mpu.md dasa-nala.md dasa-rsi.md dasa-sastra.md dasa-widya.md dasa-indra.md dasa-dharma.md dasa-kala.md dasa-dwipa.md; do
        target="${SKILLS_DIR}/${skill}"
        if [[ -f "$target" ]]; then
            rm "$target"
            info "Removed skill: $skill"
        fi
    done

    if [[ -d "$WORKFLOWS_DIR" ]]; then
        rm -rf "$WORKFLOWS_DIR"
        info "Removed master workflow templates directory: $WORKFLOWS_DIR"
    fi

    echo ""
    info "Uninstall complete."
    echo "  Note: ~/.gemini/ directories are preserved (may contain other tools)."
}

# ============================================================================
# Entry point
# ============================================================================

case "${1:-install}" in
    install)
        do_install
        ;;
    uninstall|remove)
        do_uninstall
        ;;
    *)
        echo "Usage: $0 [install|uninstall]"
        exit 1
        ;;
esac
