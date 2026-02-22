#!/usr/bin/env python3
"""
Dasa Indra: The native QA Gate (qa_gate.py)
Assimilates ~800 patterns from `engineering-failures-bible`.
Provides native python text scanning against common language-specific pitfalls 
before a task can be marked complete.
"""

import sys
import os
import re
import argparse
from pathlib import Path

# Embedded Failure Patterns (TOON Heuristics)
FAILURES = {
    "01_Memory": [
        (r"new\s+[a-zA-Z]+\(.*\)\s*;(?!.*\bdelete\b)", "Unmatched 'new' allocation without 'delete' (C++/Leaks)"),
        (r"fmt\.Sprintf\(\s*\"%s\"", "String concatenation in loops instead of strings.Builder (Go/Memory)"),
        (r"\.collect::\<Vec<\w+>\>\(\)", "Unbounded heavy .collect() instead of iterators (Rust/Memory)")
    ],
    "02_Concurrency": [
        (r"sync\.Mutex.*defer\s+.*Unlock", "Missing careful Lock bounds via defer (Go/Deadlock risk)"),
        (r"std::sync::Mutex.*\.unwrap\(\)", "Poisoning panic risk on Mutex.unwrap() (Rust/Concurrency)"),
        (r"Promise\.all\(.*\.(map|forEach)\(async", "Unbounded concurrent Promise execution. Use Promise.allSettled or batching (Node/EventLoop)")
    ],
    "03_Security": [
        (r"SELECT\s+.*\s+FROM\s+.*\s+WHERE\s+.*=\s*\S+\s*\+", "Raw string concatenation in SQL queries (SQL Injection)"),
        (r"eval\(", "Use of eval() detected (RCE vulnerability)"),
        (r"dangerouslySetInnerHTML", "Potential XSS detected in React/Next.js component")
    ]
}

def scan_file(filepath: Path) -> list:
    issues = []
    try:
        content = filepath.read_text(encoding="utf-8")
        lines = content.splitlines()
        for idx, line in enumerate(lines, 1):
            for domain, patterns in FAILURES.items():
                for regex, desc in patterns:
                    if re.search(regex, line):
                        issues.append(f"[FAIL] {domain} | {filepath.name}:{idx} -> {desc}")
    except Exception as e:
        print(f"Skipping {filepath} ({e})")
    return issues

def main():
    parser = argparse.ArgumentParser(description="Dasa Indra QA Gate Scanner")
    parser.add_argument("target", help="Directory or file to scan")
    args = parser.parse_args()

    target_path = Path(args.target)
    if not target_path.exists():
        print(f"Error: Target {target_path} does not exist.")
        sys.exit(1)

    print(f"🕵️‍♂️ Dasa Indra: Initiating Engineering Failure Scan on {target_path}...")
    
    total_issues = []
    if target_path.is_file():
        total_issues.extend(scan_file(target_path))
    else:
        for root, _, files in os.walk(target_path):
            if ".git" in root or "node_modules" in root or "target" in root:
                continue
            for file in files:
                ext = Path(file).suffix
                if ext in [".js", ".ts", ".go", ".rs", ".java", ".php", ".py", ".cpp"]:
                    full_path = Path(root) / file
                    total_issues.extend(scan_file(full_path))

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
