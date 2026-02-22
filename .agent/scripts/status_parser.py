#!/usr/bin/env python3
"""
Dasa Kala: The Reporter (status_parser.py)
Merges data from task.md and git diff --stat to output a 3-line JSON summary.
Prevents Kala from wasting context reading entire task checklists.
"""

import os
import sys
import subprocess
import json

def get_task_stats():
    """Read task.md and count checkboxes to determine progress."""
    task_path = ".artifacts/task.md"
    if not os.path.exists(task_path):
        # Fallback to older location
        task_path = ".agent/task.toon"
        if not os.path.exists(task_path):
             return {"total": 0, "completed": 0, "in_progress": 0}
             
    total = 0
    completed = 0
    in_progress = 0
    
    with open(task_path, "r") as f:
        for line in f.readlines():
            line = line.strip()
            if line.startswith("- [ ]"):
                total += 1
            elif line.startswith("- [x]") or line.startswith("- [X]"):
                total += 1
                completed += 1
            elif line.startswith("- [/]"):
                total += 1
                in_progress += 1
                
    return {"total": total, "completed": completed, "in_progress": in_progress}

def get_git_stats():
    """Get high-level git diff stats without the actual diff content."""
    try:
        # Get purely the stat line e.g., "3 files changed, 50 insertions(+), 10 deletions(-)"
        stat = subprocess.check_output(["git", "diff", "--shortstat"]).decode('utf-8').strip()
        if not stat:
             stat = subprocess.check_output(["git", "diff", "--cached", "--shortstat"]).decode('utf-8').strip()
        return stat if stat else "Working tree clean"
    except Exception:
        return "Unknown git status"

def main():
    print("🛡️  [Dasa Kala] Initializing Project Status Reporter...")
    
    tasks = get_task_stats()
    git_stat = get_git_stats()
    
    pct = 0
    if tasks["total"] > 0:
        pct = round((tasks["completed"] / tasks["total"]) * 100)
        
    summary = {
        "progress_percent": pct,
        "tasks": f"{tasks['completed']}/{tasks['total']} ({tasks['in_progress']} active)",
        "uncommitted_code": git_stat
    }
    
    # Write to a tiny file Kala can instantly parse
    os.makedirs(".artifacts", exist_ok=True)
    out_path = ".artifacts/status_summary.json"
    
    with open(out_path, "w") as f:
        json.dump(summary, f, indent=2)
        
    print(f"🟢 [Kala Reporter] Status parsed. JSON Summary generated at {out_path}.")
    sys.exit(0)

if __name__ == "__main__":
    main()
