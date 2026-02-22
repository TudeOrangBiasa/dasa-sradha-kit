#!/usr/bin/env python3
"""
semantic-scan.py — Cross-platform semantic search wrapper (uses osgrep)
Persona: Dasa Dwipa (The Scout)

Usage:
  python .agent/scripts/semantic-scan.py "JWT authentication middleware"
  python .agent/scripts/semantic-scan.py "where is the login form handled"
"""

import sys
import subprocess
import shutil
import os

def check_osgrep():
    return shutil.which("osgrep") is not None

def run_semantic_search(query: str) -> int:
    if not check_osgrep():
        print("[!] osgrep is not installed. Install it with: npm install -g osgrep")
        print(f"[!] Falling back to grep for: {query}")
        result = subprocess.run(
            ["grep", "-r", "--include=*.ts", "--include=*.py", "--include=*.js",
             "--include=*.php", "-n", query, "."],
            capture_output=True, text=True
        )
        if result.stdout:
            print(result.stdout[:3000])
        return result.returncode

    # osgrep available
    try:
        result = subprocess.run(
            ["osgrep", "search", query],
            capture_output=True, text=True, timeout=30
        )
        print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        return result.returncode
    except subprocess.TimeoutExpired:
        print("[x] osgrep search timed out after 30s")
        return 1
    except FileNotFoundError:
        print("[x] osgrep not found in PATH")
        return 1

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python semantic-scan.py <query>")
        sys.exit(1)

    query = " ".join(sys.argv[1:])
    print(f"[+] Semantic search: {query}")
    sys.exit(run_semantic_search(query))
