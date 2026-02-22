#!/usr/bin/env python3
"""
Dasa Rsi: The Oracle's Lens (complexity_scorer.py)
Performs static analysis on source code files to calculate cyclomatic complexity.
Outputs only the specific 'hotspot' functions and line numbers, preventing Rsi 
from having to read the entire file line-by-line.
"""

import sys
import os
import re

def compute_complexity(code_chunk):
    """
    Very naive cyclomatic complexity estimator wrapper.
    Counts branching keywords as a rough heuristics.
    """
    keywords = [
        r'\bif\b', r'\belse\b', r'\bfor\b', r'\bwhile\b', 
        r'\bswitch\b', r'\bcase\b', r'\bcatch\b', r'\b\?\b', r'&&', r'\|\|'
    ]
    complexity = 1
    for kw in keywords:
        complexity += len(re.findall(kw, code_chunk))
    return complexity

def analyze_file(filepath):
    """Roughly chunks a file into blocks and scores them."""
    if not os.path.exists(filepath):
        return None
        
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
        
    hotspots = []
    chunk_size = 20 # Lines
    
    for i in range(0, len(lines), chunk_size):
        chunk = "".join(lines[i:i+chunk_size])
        score = compute_complexity(chunk)
        
        # Arbitrary threshold to define a "hotspot" (high branching logic)
        if score >= 10:
            hotspots.append({
                "line_start": i + 1,
                "line_end": min(i + chunk_size, len(lines)),
                "score": score,
                "preview": lines[i].strip()
            })
            
    return hotspots

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 complexity_scorer.py <file_path>")
        sys.exit(1)
        
    target_file = sys.argv[1]
    print(f"🛡️  [Dasa Rsi] Analyzing structural complexity of {target_file}...")
    
    hotspots = analyze_file(target_file)
    
    if hotspots is None:
        print(f"🔴 [Rsi Lens] File {target_file} not found.")
        sys.exit(1)
        
    if not hotspots:
        print(f"🟢 [Rsi Lens] No significant structural hotspots detected in {os.path.basename(target_file)}.")
        sys.exit(0)
        
    # Sort by highest complexity
    hotspots.sort(key=lambda x: x["score"], reverse=True)
    
    print("\n🔍 HIGH COMPLEXITY HOTSPOTS DETECTED:")
    for h in hotspots[:5]: # Only show top 5 worst offenders
        print(f"  - Lines {h['line_start']}-{h['line_end']} | Complexity Score: {h['score']} | Context: `{h['preview'][:40]}...`")
        
    print("\n[Rsi Lens] Recommend running `view_file` exclusively on these line ranges.")
    sys.exit(0)

if __name__ == "__main__":
    main()
