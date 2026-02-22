#!/usr/bin/env python3
"""
workspace-mapper.py — Cross-platform codebase tree visualization
Persona: Dasa Dwipa (The Scout)

Usage:
  python .agent/scripts/workspace-mapper.py
  python .agent/scripts/workspace-mapper.py --depth 3
"""

import os
import sys
import argparse
from pathlib import Path

IGNORE_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv", "vendor",
    ".next", "dist", "build", "coverage", ".cache", "tmp", ".agent",
    "ag-kit", "awesome-antigravity"
}

def build_tree(directory: Path, prefix: str = "", depth: int = 3, current_depth: int = 0) -> list[str]:
    if current_depth >= depth:
        return []

    lines = []
    try:
        entries = sorted(
            [e for e in directory.iterdir() if e.name not in IGNORE_DIRS],
            key=lambda e: (not e.is_dir(), e.name.lower())
        )
    except PermissionError:
        return []

    for i, entry in enumerate(entries):
        is_last = i == len(entries) - 1
        connector = "└── " if is_last else "├── "
        lines.append(f"{prefix}{connector}{entry.name}")
        if entry.is_dir():
            extension = "    " if is_last else "│   "
            lines.extend(build_tree(entry, prefix + extension, depth, current_depth + 1))

    return lines

def main():
    parser = argparse.ArgumentParser(description="Workspace structure map for Dasa Dwipa")
    parser.add_argument("--depth", type=int, default=3, help="Max depth to display (default: 3)")
    args = parser.parse_args()

    cwd = Path.cwd()
    print(f"\n📁 {cwd.name}/")
    lines = build_tree(cwd, depth=args.depth)
    for line in lines:
        print(line)
    print(f"\n[+] Scanned {len(lines)} entries (depth: {args.depth})")

if __name__ == "__main__":
    main()
