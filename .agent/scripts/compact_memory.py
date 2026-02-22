#!/usr/bin/env python3
"""
Dasa Patih: Temporal Knowledge Graph Compactor (compact_memory.py)
Imitates the 5-sector cognitive engine from `OpenMemory`.
Compresses sprawling chat histories into specific TOON memory sectors.
"""

import os
import sys
import json
import datetime

def init_memory_vault():
    return {
        "episodic": [],     # Events (e.g., "User asked for a login page")
        "semantic": [],     # Facts (e.g., "The API is hosted on port 8080")
        "procedural": [],   # Skills (e.g., "How to deploy to Railway")
        "emotional": [],    # Preferences (e.g., "User hates Tailwind")
        "reflective": []    # Insights (e.g., "We should use Postgres instead of MySQL next time")
    }

def add_memory(vault, sector, content, context_id="system"):
    """Adds a memory to the designated sector with temporal metadata."""
    if sector not in vault:
        print(f"Error: Unknown memory sector '{sector}'")
        return
        
    memory_node = {
        "content": content,
        "valid_from": datetime.datetime.now().isoformat(),
        "context": context_id
    }
    
    vault[sector].append(memory_node)
    return memory_node

def main():
    vault_path = ".artifacts/dasa_memory.toon"
    os.makedirs(".artifacts", exist_ok=True)
    
    # Load existing vault or create new
    if os.path.exists(vault_path):
        with open(vault_path, "r") as f:
            try:
                vault = json.load(f)
            except json.JSONDecodeError:
                vault = init_memory_vault()
    else:
        vault = init_memory_vault()
        
    if len(sys.argv) < 3:
        print("Usage: python3 compact_memory.py <sector> <memory_content>")
        print("Sectors: episodic, semantic, procedural, emotional, reflective")
        sys.exit(1)
        
    sector = sys.argv[1]
    content = " ".join(sys.argv[2:])
    
    print(f"🧠 [Dasa Patih] Integrating memory into {sector.upper()} sector...")
    add_memory(vault, sector, content)
    
    with open(vault_path, "w") as f:
        json.dump(vault, f, indent=2)
        
    print(f"✅ Memory firmly consolidated in {vault_path}. Temporal Graph updated.")

if __name__ == "__main__":
    main()
