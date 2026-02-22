#!/usr/bin/env python3
"""
Dasa Mpu: The Cartographer (arch_mapper.py)
Parses structural and dependency files (package.json, go.mod, requirements.txt)
and outputs a highly compressed TOON map of the backend architecture.
Saves Mpu from spending tokens reading massive dependency files line-by-line.
"""

import os
import sys
import json

def parse_package_json():
    """Extract dependencies and scripts from package.json."""
    if not os.path.exists("package.json"):
        return None
        
    try:
        with open("package.json", "r") as f:
            data = json.load(f)
            
        deps = list(data.get("dependencies", {}).keys())
        scripts = list(data.get("scripts", {}).keys())
        
        return {
            "type": "Node/JS",
            "name": data.get("name", "Unknown"),
            "core_deps": deps[:15], # Only take top 15 to save tokens
            "total_deps": len(deps),
            "scripts": scripts
        }
    except Exception:
        return None

def parse_go_mod():
    """Extract module info from go.mod."""
    if not os.path.exists("go.mod"):
        return None
        
    try:
        with open("go.mod", "r") as f:
            lines = f.readlines()
            
        mod_name = "Unknown"
        deps = []
        for line in lines:
            line = line.strip()
            if line.startswith("module "):
                mod_name = line.split()[1]
            elif line and not line.startswith("go ") and not line.startswith("require") and not line.startswith(")"):
                # Rough extraction of dependency names
                parts = line.split()
                if len(parts) > 0 and "." in parts[0]:
                    deps.append(parts[0])
                    
        return {
            "type": "Go Module",
            "name": mod_name,
            "core_deps": deps[:15],
            "total_deps": len(deps)
        }
    except Exception:
        return None

def main():
    print("🛡️  [Dasa Mpu] Initializing Architectural Cartographer...")
    
    arch_data = {}
    
    node_data = parse_package_json()
    if node_data:
         arch_data["Node"] = node_data
         
    go_data = parse_go_mod()
    if go_data:
         arch_data["Go"] = go_data
         
    if not arch_data:
        print("🟡 [Mpu Cartographer] No recognized architecture definitions found. Pass.")
        sys.exit(0)
        
    # Generate the highly compressed TOON map
    toon_map = "# Architectural Map\n"
    for ecosystem, data in arch_data.items():
        toon_map += f"\n## {ecosystem}: {data.get('name')}\n"
        toon_map += f"- **Total Dependencies:** {data.get('total_deps')}\n"
        toon_map += f"- **Core Tools:** {', '.join(data.get('core_deps', []))}\n"
        if "scripts" in data:
            toon_map += f"- **Available Scripts:** {', '.join(data.get('scripts', []))}\n"
            
    os.makedirs(".artifacts", exist_ok=True)
    out_path = ".artifacts/architecture_map.toon"
    
    with open(out_path, "w") as f:
        f.write(toon_map)
        
    print(f"🟢 [Mpu Cartographer] Architecture successfully compressed into {out_path}.")
    sys.exit(0)

if __name__ == "__main__":
    main()
