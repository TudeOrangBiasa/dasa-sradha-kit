#!/usr/bin/env python3

# extract-design.py
# Native execution script for Dasa Widya (The Researcher)
# Extracts a basic Design Memory CSS token dictionary from a target URL purely via HTTP requests.

import sys
import re
import json
import urllib.request
import os

def print_help():
    print("Usage: python3 extract-design.py <URL>")
    print("Fetches a web page and extracts primary colors and font families to generate a .design-memory vault.")

def extract_tokens(html_content):
    tokens = {
        "colors": {
            "primary": [],
            "secondary": []
        },
        "typography": {
            "families": []
        }
    }
    
    # Very crude regex to find hex colors in inline styles or raw css blocks
    hex_colors = re.findall(r'#([A-Fa-f0-9]{6}|[A-Fa-f0-9]{3})\b', html_content)
    
    # Deduplicate and sort by frequency (crudely)
    if hex_colors:
        color_counts = {}
        for c in hex_colors:
            color = "#" + c.lower()
            color_counts[color] = color_counts.get(color, 0) + 1
            
        sorted_colors = sorted(color_counts.items(), key=lambda item: item[1], reverse=True)
        
        # Take top 3 as primary
        for c, count in sorted_colors[:3]:
            tokens["colors"]["primary"].append(c)
            
        # Take next 5 as secondary
        for c, count in sorted_colors[3:8]:
            tokens["colors"]["secondary"].append(c)
            
    # Crude regex to find font-families
    fonts = re.findall(r'font-family:\s*([^;>]+)', html_content)
    if fonts:
        for f in fonts[:3]: # grab first 3 mentions
            clean_font = f.strip().replace("'", "").replace('"', '')
            if clean_font not in tokens["typography"]["families"]:
                tokens["typography"]["families"].append(clean_font)
                
    return tokens

def main():
    if len(sys.argv) < 2:
        print_help()
        sys.exit(1)

    url = sys.argv[1]
    
    print(f"[Widya Researcher] Target acquired: {url}. Initiating Native CSS Token Extraction...")
    
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as response:
            html = response.read().decode('utf-8', errors='ignore')
            
            tokens = extract_tokens(html)
            
            # Create .design-memory directory if it doesn't exist
            if not os.path.exists('.design-memory'):
                os.makedirs('.design-memory')
                
            # Write tokens.json
            with open('.design-memory/tokens.json', 'w') as f:
                json.dump(tokens, f, indent=4)
                
            print("[Widya Researcher] Extraction Complete.")
            print(f"Tokens saved to .design-memory/tokens.json")
            print(json.dumps(tokens, indent=2))
            
    except Exception as e:
        print(f"[Widya Researcher] Native Extraction Failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
