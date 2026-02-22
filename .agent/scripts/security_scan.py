#!/usr/bin/env python3
"""
Dasa Dharma: Secret Guardian (security_scan.py)
Scans git diffs or specific files for leaked API keys, tokens, and secrets.
"""

import os
import sys
import subprocess
import re

SECRET_PATTERNS = {
    "AWS Access Key": r"AKIA[0-9A-Z]{16}",
    "Stripe API Key": r"sk_(test|live)_[0-9a-zA-Z]{24}",
    "Google API Key": r"AIza[0-9A-Za-z-_]{35}",
    "Generic Bearer/Token": r"(?i)(bearer|token|api_key|secret)['\"\s:=]+[A-Za-z0-9\-_]{20,}",
    "Private Key": r"-----BEGIN (RSA|OPENSSH|DSA|EC|PGP) PRIVATE KEY-----"
}

def get_git_diff():
    """Get the current staged and unstaged git changes."""
    try:
        # Get staged changes
        staged = subprocess.check_output(["git", "diff", "--cached"]).decode('utf-8')
        # Get unstaged changes
        unstaged = subprocess.check_output(["git", "diff"]).decode('utf-8')
        return staged + "\n" + unstaged
    except subprocess.CalledProcessError:
        print("🟡 [Dharma Guardian] Not a git repository or no commits yet. Skipping diff scan.")
        return ""
    except Exception as e:
        print(f"🔴 [Dharma Guardian] Error executing git diff: {e}")
        return ""

def scan_diff(diff_text):
    """Scan the diff text for secret patterns."""
    leaks = []
    
    # Only scan added/modified lines in diff (+ but not +++)
    diff_lines = [line for line in diff_text.split('\n') if line.startswith('+') and not line.startswith('+++')]
    
    for line in diff_lines:
        for name, pattern in SECRET_PATTERNS.items():
            if re.search(pattern, line):
                leaks.append((name, line.strip()))
                
    return leaks

def main():
    print("🛡️  [Dasa Dharma] Initializing Secret Guardian Scan...")
    
    # 1. Scan .env files (preventing accidental .env commits)
    try:
        git_status = subprocess.check_output(["git", "status", "-s"]).decode('utf-8')
        status_lines = git_status.split('\n')
        for line in status_lines:
            if '.env' in line and not '.example' in line:
                 print(f"🔴 [Dharma Guardian] FATAL: You are attempting to commit a raw .env file!\nLine: {line.strip()}")
                 sys.exit(1)
    except subprocess.CalledProcessError:
        pass # Not a git repo

    # 2. Scan Git Diff for hardcoded secrets
    diff_text = get_git_diff()
    if not diff_text:
        print("🟢 [Dharma Guardian] No changes to scan. Pass.")
        sys.exit(0)
        
    leaks = scan_diff(diff_text)
    
    if leaks:
        print("\n🔴 [Dharma Guardian] FATAL: Potential Secret Leaks Detected in `git diff`:")
        for name, line in leaks:
            print(f"  - [{name}] Found in line: {line[:80]}...")
        print("\nHALTING COMMIT. Remove hardcoded secrets and use environment variables.")
        sys.exit(1)
        
    print("🟢 [Dharma Guardian] Security Audit Passed. No obvious secrets leaked.")
    sys.exit(0)

if __name__ == "__main__":
    main()
