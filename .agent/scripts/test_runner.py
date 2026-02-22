#!/usr/bin/env python3
"""
Dasa Indra: Universal Test Watcher (test_runner.py)
A lightweight wrapper that detects the framework, runs tests, and compresses 
massive test console outputs into a concise TOON summary to save tokens.
"""

import os
import sys
import subprocess
import json
from datetime import datetime

def detect_framework():
    """Detect the testing framework based on workspace files."""
    if os.path.exists("package.json"):
        with open("package.json", "r") as f:
            content = f.read()
            if '"jest"' in content:
                return "npm test", "Jest"
            if '"vitest"' in content:
                return "npm run test", "Vitest"
    
    if os.path.exists("pytest.ini") or os.path.exists("setup.py") or os.path.exists("requirements.txt"):
        return "pytest", "PyTest"
        
    if os.path.exists("go.mod"):
        return "go test ./...", "Go Test"
        
    return None, None

def generate_toon_report(framework, output, code):
    """Compress the raw test output into a clean TOON structure."""
    lines = output.split('\n')
    errors = [line for line in lines if 'FAIL' in line or 'Error' in line or 'ERR!' in line]
    
    # We only take the last 50 lines to prevent token bloat
    tail = "\n".join(lines[-50:])
    
    status = "SUCCESS" if code == 0 else "FAILED"
    
    report = f"""# Test Execution Report
Framework: {framework}
Status: {status}
Timestamp: {datetime.now().isoformat()}

## Summary Tail
```text
{tail}
```
"""
    if errors and code != 0:
        report += "\n## Detected Failures\n```text\n" + "\n".join(errors[:20]) + "\n```\n"

    return report

def main():
    print("🛡️  [Dasa Indra] Initializing Universal Test Watcher...")
    
    cmd, framework = detect_framework()
    
    if not cmd:
        print("🟡 [Indra Watcher] No recognized testing framework found in root. Skipping tests.")
        sys.exit(0)
        
    print(f"⚡ [Indra Watcher] Detected {framework}. Running: `{cmd}`")
    
    try:
        # Run tests and capture both stdout and stderr
        result = subprocess.run(cmd.split(), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        output = result.stdout
        code = result.returncode
    except FileNotFoundError:
        print(f"🔴 [Indra Watcher] Testing executable for '{cmd}' not found.")
        sys.exit(1)
    except Exception as e:
         print(f"🔴 [Indra Watcher] Unexpected error executing tests: {e}")
         sys.exit(1)
         
    # Generate the highly compressed TOON output
    report = generate_toon_report(framework, output, code)
    
    # We write this compressed report to a file so the AI can read it efficiently
    # instead of bloating the chat context with 10,000 lines of Jest output.
    os.makedirs(".artifacts", exist_ok=True)
    report_path = ".artifacts/test_report.toon"
    with open(report_path, "w") as f:
        f.write(report)
        
    if code != 0:
        print(f"🔴 [Indra Watcher] Tests FAILED. Details written to {report_path}")
        sys.exit(1)
    else:
        print(f"🟢 [Indra Watcher] All tests passed! Summary written to {report_path}")
        sys.exit(0)

if __name__ == "__main__":
    main()
