#!/usr/bin/env python3
"""
Dasa Patih: Zero-Dependency Context Mapper (context_mapper.py)
Replicates the focused vector mapping of `amdb` and `osgrep` but runs 100% natively.
Extracts class and function signatures from Python/JS/TS/Go/Rust codebases
to build highly compressed `.artifacts/context.toon` snippets for the LLM.
"""

import sys
import os
import re
import ast
from pathlib import Path

def parse_python(filepath: Path):
    signatures = []
    try:
        content = filepath.read_text(encoding="utf-8")
        tree = ast.parse(content)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
                signatures.append(f"def {node.name}(...)")
            elif isinstance(node, ast.ClassDef):
                signatures.append(f"class {node.name}")
    except Exception:
        pass
    return signatures

def parse_regex(filepath: Path, class_pattern, func_pattern):
    signatures = []
    try:
        content = filepath.read_text(encoding="utf-8")
        lines = content.splitlines()
        for line in lines:
            if re.search(class_pattern, line):
                signatures.append(line.strip().rstrip('{'))
            elif re.search(func_pattern, line):
                signatures.append(line.strip().rstrip('{'))
    except Exception:
        pass
    return signatures

def parse_file(filepath: Path):
    ext = filepath.suffix
    if ext == ".py":
        return parse_python(filepath)
    elif ext in [".js", ".ts", ".jsx", ".tsx"]:
        return parse_regex(filepath, r"^\s*(export\s+)?class\s+\w+", r"^\s*(export\s+)?(async\s+)?function\s+\w+|^\s*(export\s+)?const\s+\w+\s*=\s*\(.*\)\s*=>")
    elif ext == ".go":
        return parse_regex(filepath, r"^\s*type\s+\w+\s+struct", r"^\s*func\s+")
    elif ext == ".rs":
        return parse_regex(filepath, r"^\s*(pub\s+)?(struct|enum|trait)\s+\w+", r"^\s*(pub\s+)?(async\s+)?fn\s+\w+")
    return []

def main():
    if len(sys.argv) < 2:
        print("Usage: context_mapper.py <directory>")
        sys.exit(1)

    target_dir = Path(sys.argv[1])
    if not target_dir.exists() or not target_dir.is_dir():
        print(f"Directory {target_dir} not found.")
        sys.exit(1)
        
    print(f"🗺️ Dasa Patih: Mapping codebase context for {target_dir}...")
    
    context_lines = [f"# Codebase Context: {target_dir.name}\n"]
    
    for root, dirs, files in os.walk(target_dir):
        # Exclude typical noise
        dirs[:] = [d for d in dirs if d not in [".git", "node_modules", "target", "dist", ".gemini", ".artifacts"]]
        for file in files:
            ext = Path(file).suffix
            if ext in [".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".rs"]:
                filepath = Path(root) / file
                sigs = parse_file(filepath)
                if sigs:
                    rel_path = filepath.relative_to(target_dir)
                    context_lines.append(f"\n## {rel_path}")
                    for sig in sigs:
                        context_lines.append(f"- {sig}")

    artifacts_dir = target_dir / ".artifacts"
    artifacts_dir.mkdir(exist_ok=True)
    out_file = artifacts_dir / "context.toon"
    
    out_file.write_text("\n".join(context_lines), encoding="utf-8")
    print(f"✅ Context successfully compressed into {out_file}")

if __name__ == "__main__":
    main()
