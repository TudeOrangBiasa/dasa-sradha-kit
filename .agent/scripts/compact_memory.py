#!/usr/bin/env python3
"""
Dasa Patih: Temporal Knowledge Graph Compactor (compact_memory.py)
Imitates the 5-sector cognitive engine from `OpenMemory` and `memU`.
Compresses sprawling chat histories into specific TOON memory sectors.
Adopts Continuous Active Learning: heavily indexes Emotional/Procedural 
sectors with weights to make agents proactive in future sessions.
"""

import os
import sys
import json
import datetime
from typing import Dict, Any

def init_memory_vault() -> Dict[str, Any]:
    return {
        "episodic": [],     # Events (e.g., "User asked for a login page")
        "semantic": [],     # Facts (e.g., "The API is hosted on port 8080")
        "procedural": [],   # Skills (e.g., "How to deploy to Railway") -> Indexed for quick reuse
        "emotional": [],    # Preferences (e.g., "User hates Tailwind") -> Highly weighted
        "reflective": []    # Insights (e.g., "We should use Postgres instead of MySQL next time")
    }

def calculate_weight(sector: str) -> int:
    """Assigns proactive weights to memU-inspired continuous learning sectors."""
    if sector == "emotional":
        return 10 # Highest priority (User preferences)
    elif sector == "procedural":
        return 8  # High priority (Learned skills/fixes)
    elif sector == "reflective":
        return 5
    return 1

def deduplicate_memory(vault_sector: list, content: str) -> bool:
    """Basic memU deduplication: if exact content exists, boost its weight instead of duplicating."""
    for node in vault_sector:
        if node.get("content") == content:
            node["weight"] = node.get("weight", 1) + 1
            node["last_accessed"] = datetime.datetime.now().isoformat()
            return True
    return False

def add_memory(vault: Dict[str, Any], sector: str, content: str, context_id: str = "system"):
    """Adds or updates a memory in the designated sector with memU continuous learning metadata."""
    if sector not in vault:
        print(f"Error: Unknown memory sector '{sector}'")
        return
        
    if deduplicate_memory(vault[sector], content):
        print(f"🔄 Memory already exists in {sector}. Boosting its proactive weight.")
        return

    weight = calculate_weight(sector)
    memory_node = {
        "content": content,
        "valid_from": datetime.datetime.now().isoformat(),
        "last_accessed": datetime.datetime.now().isoformat(),
        "context": context_id,
        "weight": weight,
        "tags": [sector, context_id]
    }
    
    # Sort procedural and emotional by weight descending to ensure agents see top rules first
    vault[sector].append(memory_node)
    if sector in ["emotional", "procedural"]:
        vault[sector] = sorted(vault[sector], key=lambda x: x.get("weight", 0), reverse=True)
        
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
        
    sector = sys.argv[1].lower()
    content = " ".join(sys.argv[2:])
    
    print(f"🧠 [Dasa Patih] Integrating memory into {sector.upper()} sector...")
    add_memory(vault, sector, content)
    
    with open(vault_path, "w") as f:
        json.dump(vault, f, indent=2)
        
    print(f"✅ Memory firmly consolidated in {vault_path}. Continuous Active Learning applied.")

if __name__ == "__main__":
    main()
