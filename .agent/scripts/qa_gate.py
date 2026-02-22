#!/usr/bin/env python3
"""
Dasa Indra: The native QA Gate (qa_gate.py)
Assimilates ~800 patterns from `engineering-failures-bible` dynamically.
Provides native python text scanning against common language-specific pitfalls 
before a task can be marked complete.
"""

import sys
import os
import re
import argparse
from pathlib import Path

def load_dynamic_failures(skills_dir: Path) -> dict:
    """
    Dynamically parses all knowledge markdown files in the engineering-failures-bible
    skills to extract regex patterns meant for ripgrep (rg "pattern").
    Returns a dictionary of domain -> list of (regex, description) tuples.
    """
    failures = {}
    if not skills_dir.exists():
        return failures

    # Find all knowledge md files
    for md_file in skills_dir.glob("engineering-failures-*/knowledge/*.md"):
        domain = md_file.parent.parent.name.replace("engineering-failures-", "")
        if domain not in failures:
            failures[domain] = []
            
        try:
            content = md_file.read_text(encoding="utf-8")
            # Extract ripgrep patterns: rg "pattern"
            # We look for rg followed by space, then " or '
            matches = re.finditer(r'rg\s+["\']([^"\']+)["\']', content)
            for match in matches:
                pattern = match.group(1)
                # Fallback description since parsing the exact Markdown header is complex
                desc = f"Pattern '{pattern}' found in {md_file.name}"
                failures[domain].append((pattern, desc))
        except Exception as e:
            print(f"Warning: Failed to parse {md_file}: {e}")
            
    return failures

def scan_file(filepath: Path, dynamic_failures: dict) -> list:
    issues = []
    try:
        content = filepath.read_text(encoding="utf-8")
        lines = content.splitlines()
        for idx, line in enumerate(lines, 1):
            for domain, patterns in dynamic_failures.items():
                for regex_str, desc in patterns:
                    try:
                        if re.search(regex_str, line):
                            issues.append(f"[FAIL] {domain} | {filepath.name}:{idx} -> {desc}")
                    except re.error:
                        # Some ripgrep syntax might not map 1:1 to python re, ignore broken ones
                        pass
    except Exception:
        pass # Skip unreadable or binary files safely
    return issues

def main():
    parser = argparse.ArgumentParser(description="Dasa Indra QA Gate Scanner")
    parser.add_argument("target", help="Directory or file to scan")
    args = parser.parse_args()

    target_path = Path(args.target)
    skills_dir = Path(".agent/skills")

    if not target_path.exists():
        print(f"Error: Target {target_path} does not exist.")
        sys.exit(1)

    print(f"🕵️‍♂️ Dasa Indra: Initiating Dynamic Engineering Failure Scan on {target_path}...")
    
    # Load dynamic failures
    dynamic_failures = load_dynamic_failures(skills_dir)
    total_patterns = sum(len(p) for p in dynamic_failures.values())
    print(f"📚 Loaded {total_patterns} failure heuristics from .agent/skills/")

    if total_patterns == 0:
        print("⚠️ Warning: No heuristics found. Did you copy engineering-failures-bible into .agent/skills/?")
    
    total_issues = []
    if target_path.is_file():
        total_issues.extend(scan_file(target_path, dynamic_failures))
    else:
        for root, _, files in os.walk(target_path):
            if ".git" in root or "node_modules" in root or "target" in root:
                continue
            for file in files:
                ext = Path(file).suffix
                if ext in [".js", ".ts", ".go", ".rs", ".java", ".php", ".py", ".cpp"]:
                    full_path = Path(root) / file
                    total_issues.extend(scan_file(full_path, dynamic_failures))

    if total_issues:
        print("\n❌ ENGINEERING FAILURES DETECTED:")
        for issue in total_issues:
            print(f"   {issue}")
        print("\n>> Dasa Nala is BLOCKED from completing this task. Fix the issues first.")
        sys.exit(1)
    else:
        print("\n✅ QA Gate Passed. No critical engineering failures detected.")
        sys.exit(0)

if __name__ == "__main__":
    main()
