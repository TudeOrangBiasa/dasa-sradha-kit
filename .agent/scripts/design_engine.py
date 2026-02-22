#!/usr/bin/env python3
"""
Dasa Mpu / Dasa Nala: The Design Engine (design_engine.py)
Assimilates logic from `ui-ux-pro-max` and `design-rules-ai`.
Prevents AI hallucination by programmatically generating a strict `MASTER.md` 
design system with hardcoded spacing, radiuses, and industry-specific palettes.
"""

import os
import sys
import json

# Statically enforce design-rules-ai constraints
ANTI_AI_CONSTRAINTS = [
    "NEVER use generic placeholder names like 'Acme Corp' or 'John Doe'. Use realistic data.",
    "NEVER generate raw SVG code. You MUST use standard libraries like Lucide or Heroicons.",
    "NEVER use random spacing like 7px or 13px. You MUST adhere to the [4, 8, 12, 16, 24, 32, 48, 64] scale.",
    "NEVER use random border-radiuses. 4px for inputs, 8px for cards, 12px for modals, 9999px for pills.",
    "NEVER use rainbow colors. Limit to 1 primary, 1 secondary, and neutral grays."
]

# Basic industry reasoning matrix (inspired by ui-ux-pro-max)
INDUSTRY_MATRIX = {
    "saas": {
        "style": "Glassmorphism / Minimal",
        "colors": {"primary": "#0F172A", "secondary": "#3B82F6", "accent": "#10B981"},
        "fonts": "Inter / Roboto Mono",
        "radius": "8px cards, 4px inputs"
    },
    "fintech": {
        "style": "High-Contrast / Trust-focused",
        "colors": {"primary": "#000000", "secondary": "#111827", "accent": "#059669"},
        "fonts": "Plus Jakarta Sans",
        "radius": "4px universal"
    },
    "healthcare": {
        "style": "Clean / Accessible (WCAG AA)",
        "colors": {"primary": "#FFFFFF", "secondary": "#0284C7", "accent": "#14B8A6"},
        "fonts": "Open Sans",
        "radius": "12px soft"
    },
    "ecommerce": {
        "style": "Hero-Centric / Conversion Focused",
        "colors": {"primary": "#18181B", "secondary": "#F43F5E", "accent": "#F59E0B"},
        "fonts": "Outfit / Playfair Display",
        "radius": "0px sharp or 9999px pills"
    }
}

def generate_design_system(industry):
    """Generate a highly constrained MASTER.md design TOON."""
    target = industry.lower()
    
    # Default to SaaS if unknown
    if target not in INDUSTRY_MATRIX:
        target = "saas"
        
    specs = INDUSTRY_MATRIX[target]
    
    toon = f"""# MASTER DESIGN SYSTEM: {industry.upper()}

> **CRITICAL**: This document overrides all LLM design instincts. Do not hallucinate styles outside of this spec.

## 1. Visual Identity
- **Design Style:** {specs['style']}
- **Primary Font:** {specs['fonts']}
- **Border Radius Rule:** {specs['radius']}

## 2. Color Palette (Strict Limit)
- **Primary:** `{specs['colors']['primary']}`
- **Secondary:** `{specs['colors']['secondary']}`
- **Accent/CTA:** `{specs['colors']['accent']}`

## 3. The 'Anti-AI' Constraints (MANDATORY)
"""
    for rule in ANTI_AI_CONSTRAINTS:
        toon += f"- {rule}\n"
        
    toon += "\n## 4. Spacing Scale (Strict)\n"
    toon += "You are ONLY allowed to use these sizing steps (rem/px):\n"
    toon += "`[0.25rem/4px, 0.5rem/8px, 0.75rem/12px, 1rem/16px, 1.5rem/24px, 2rem/32px, 3rem/48px, 4rem/64px]`\n"

    return toon

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 design_engine.py <industry_type>")
        print("Options: saas, fintech, healthcare, ecommerce")
        sys.exit(1)
        
    industry = sys.argv[1]
    
    print(f"🛡️  [Dasa Mpu] Booting Design Engine for industry: {industry}...")
    
    toon_content = generate_design_system(industry)
    
    os.makedirs(".design-memory", exist_ok=True)
    out_path = ".design-memory/MASTER.md"
    
    with open(out_path, "w") as f:
        f.write(toon_content)
        
    print(f"🟢 [Mpu Architect] Strict Design System generated at {out_path}.")
    print("Dasa Nala is now bound by these cognitive constraints.")
    sys.exit(0)

if __name__ == "__main__":
    main()
