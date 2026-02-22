#!/usr/bin/env python3
"""
Dasa Dwipa: The Local Skill Indexer (skill_search.py)
A zero-dependency semantic search to find skills locally without any cloud services.
Scans both `.agent/skills/` and `~/.gemini/antigravity/skills/`.
"""

import sys
import os
import re
from pathlib import Path

def extract_yaml_frontmatter(content):
    match = re.search(r"^---\n(.*?)\n---", content, re.DOTALL)
    if not match:
        return {}
    
    yaml_text = match.group(1)
    metadata = {}
    for line in yaml_text.split("\n"):
        if ":" in line:
            key, val = line.split(":", 1)
            metadata[key.strip()] = val.strip().strip("'\"")
    return metadata

def parse_skills_in_directory(dir_path: Path):
    skills = []
    if not dir_path.exists() or not dir_path.is_dir():
        return skills
    
    for root, _, files in os.walk(dir_path):
        for file in files:
            if file == "SKILL.md":
                skill_path = Path(root) / file
                try:
                    content = skill_path.read_text(encoding="utf-8")
                    meta = extract_yaml_frontmatter(content)
                    if "name" in meta and "description" in meta:
                        skills.append({
                            "name": meta["name"],
                            "description": meta["description"],
                            "path": str(skill_path.parent)
                        })
                except Exception:
                    pass
    return skills

def score_skill(skill, query_words):
    text_corpus = (skill["name"] + " " + skill["description"]).lower()
    score = 0
    for word in query_words:
        if word in text_corpus:
            score += 1
    return score

def main():
    if len(sys.argv) < 2:
        print("Usage: skill_search.py <query>")
        sys.exit(1)
    
    query = " ".join(sys.argv[1:]).lower()
    query_words = set(re.findall(r'\w+', query))
    
    global_dir = Path.home() / ".gemini" / "antigravity" / "skills"
    local_dir = Path(os.getcwd()) / ".agent" / "skills"
    
    all_skills = parse_skills_in_directory(global_dir) + parse_skills_in_directory(local_dir)
    
    if not all_skills:
        print("No skills found on the local machine.")
        sys.exit(0)
    
    for skill in all_skills:
        skill["score"] = score_skill(skill, query_words)
    
    ranked_skills = sorted(all_skills, key=lambda x: x["score"], reverse=True)
    
    print(f"🔍 Dasa Dwipa: Ranked Skills for '{query}'\n")
    found_any = False
    for skill in ranked_skills[:3]:
        if skill["score"] > 0:
            found_any = True
            print(f"✨ {skill['name']} (Score: {skill['score']})")
            print(f"   Desc: {skill['description']}")
            print(f"   Path: {skill['path']}\n")
            
    if not found_any:
        print("No relevant skills matched your query. Try broadening your terms.")

if __name__ == "__main__":
    main()
