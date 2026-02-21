#!/usr/bin/env python3

# web-search.py
# Native execution script for Dasa Widya (The Researcher)
# Lightweight script to fetch markdown from a URL using curl and basic parsing.
# Note: Designed to run natively without external MCPs.

import sys
import subprocess
import urllib.request
import re

def print_help():
    print("Usage: python3 web-search.py <URL>")
    print("Fetches a web page and attempts to strip HTML to return crude markdown for the AI context.")

def clean_html(raw_html):
    # Extremely crude HTML to text for Zero-Dependency environments
    text = re.sub('<style.*?>.*?</style>', '', raw_html, flags=re.DOTALL)
    text = re.sub('<script.*?>.*?</script>', '', text, flags=re.DOTALL)
    text = re.sub('<[^>]+>', ' ', text)
    text = re.sub('\s+', ' ', text).strip()
    return text

def main():
    if len(sys.argv) < 2:
        print_help()
        sys.exit(1)

    url = sys.argv[1]
    
    # Try using native python urllib first
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as response:
            html = response.read().decode('utf-8', errors='ignore')
            text = clean_html(html)
            print(f"[Widya Researcher] Successfully fetched {url}:\n")
            print(text[:2000]) # Cap at 2000 chars to prevent token overflow
            if len(text) > 2000:
                print("\n... [Truncated for Context Window limit]")
    except Exception as e:
        print(f"[Widya Researcher] Failed to fetch via python native. Error: {e}")
        # Fallback to curl
        try:
            print("Trying curl fallback...")
            result = subprocess.run(['curl', '-sIL', url], capture_output=True, text=True, timeout=10)
            print("Headers:")
            print(result.stdout)
        except Exception as curl_e:
            print(f"Curl fallback also failed: {curl_e}")

if __name__ == "__main__":
    main()
