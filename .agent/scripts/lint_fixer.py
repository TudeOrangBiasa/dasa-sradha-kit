#!/usr/bin/env python3
"""
Dasa Nala: Auto-Formatter (lint_fixer.py)
Detects installed linting/formatting tools and automatically fixes fixable syntax.
Prevents the AI from wasting LLM tokens manually inserting missing semicolons or spaces.
"""

import os
import sys
import subprocess

def detect_and_run_formatters():
    """Detect formatters in the project and run their auto-fix commands."""
    fixed_something = False
    
    # 1. Javascript / Typescript (Prettier/ESLint)
    if os.path.exists("package.json"):
        with open("package.json", "r") as f:
            content = f.read()
            
        if '"prettier"' in content or '"prettier:' in content:
            print("⚡ [Nala Formatter] Prettier detected. Running `npx prettier --write .`")
            try:
                subprocess.run(["npx", "prettier", "--write", "."], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                fixed_something = True
            except Exception:
                pass
                
        if '"eslint"' in content:
            print("⚡ [Nala Formatter] ESLint detected. Running `npx eslint --fix .`")
            try:
                subprocess.run(["npx", "eslint", "--fix", "."], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                fixed_something = True
            except Exception:
                pass

    # 2. Python (Ruff / Black)
    if os.path.exists("pyproject.toml") or os.path.exists("requirements.txt"):
        try:
            # Check if ruff is available
            subprocess.run(["ruff", "--version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            print("⚡ [Nala Formatter] Ruff detected. Running `ruff check --fix .` and `ruff format .`")
            subprocess.run(["ruff", "check", "--fix", "."], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run(["ruff", "format", "."], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            fixed_something = True
        except (subprocess.CalledProcessError, FileNotFoundError):
             try:
                 subprocess.run(["black", "--version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
                 print("⚡ [Nala Formatter] Black detected. Running `black .`")
                 subprocess.run(["black", "."], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                 fixed_something = True
             except (subprocess.CalledProcessError, FileNotFoundError):
                 pass

    # 3. Go (gofmt)
    if os.path.exists("go.mod"):
        print("⚡ [Nala Formatter] Go module detected. Running `gofmt -w .`")
        try:
             subprocess.run(["gofmt", "-w", "."], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
             fixed_something = True
        except Exception:
             pass

    return fixed_something

def main():
    print("🛡️  [Dasa Nala] Initializing Auto-Formatter...")
    
    ran_formatters = detect_and_run_formatters()
    
    if ran_formatters:
        print("🟢 [Nala Formatter] Code styling automatically fixed where possible. AI tokens saved.")
    else:
        print("🟡 [Nala Formatter] No supported formatters detected in project root. Skipping.")
        
    sys.exit(0)

if __name__ == "__main__":
    main()
