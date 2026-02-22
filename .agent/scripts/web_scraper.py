#!/usr/bin/env python3
"""
Dasa Widya: The Extractor (web_scraper.py)
Natively fetches URL content and strips all HTML, inline CSS, and JavaScript.
Outputs pure markdown text to prevent massive token waste when Widya researchers.
Zero extra dependencies required.
"""

import urllib.request
import re
import sys

def fetch_html(url):
    """Fetch raw HTML from a URL."""
    try:
        req = urllib.request.Request(
            url, 
            data=None, 
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            return response.read().decode('utf-8', errors='ignore')
    except Exception as e:
        print(f"🔴 [Widya Extractor] Error fetching {url}: {e}")
        return None

def extract_text(html):
    """Strip all HTML tags and noise, returning clean text."""
    if not html:
        return ""
        
    # 1. Remove script and style blocks completely
    text = re.sub(r'<script.*?</script>', '', html, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r'<style.*?</style>', '', text, flags=re.IGNORECASE | re.DOTALL)
    
    # 2. Replace common block elements with newlines for formatting
    text = re.sub(r'</?(p|div|br|h[1-6]|li|tr|table|ul|ol|header|footer|nav)[^>]*>', '\n', text, flags=re.IGNORECASE)
    
    # 3. Strip all remaining HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    
    # 4. Clean up whitespace and empty lines
    lines = [line.strip() for line in text.split('\n')]
    cleaned_lines = [line for line in lines if line]
    
    return '\n\n'.join(cleaned_lines)

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 web_scraper.py <URL>")
        sys.exit(1)
        
    url = sys.argv[1]
    
    # Basic validation
    if not url.startswith('http'):
         url = 'https://' + url
         
    print(f"🛡️  [Dasa Widya] Extracting clean text from: {url}")
    
    html = fetch_html(url)
    if not html:
         sys.exit(1)
         
    clean_text = extract_text(html)
    
    # Ensure artifacts directory exists
    import os
    os.makedirs(".artifacts", exist_ok=True)
    out_path = ".artifacts/research_extraction.toon"
    
    with open(out_path, "w") as f:
        # Truncate to roughly 15,000 chars to ensure we don't blow out context
        content = clean_text[:15000]
        if len(clean_text) > 15000:
             content += "\n\n... [CONTENT TRUNCATED FOR TOKEN SAFETY] ..."
        f.write(content)
        
    print(f"🟢 [Widya Extractor] Successfully stripped HTML noise.")
    print(f"Clean markdown saved to {out_path} ({len(clean_text)} chars).")
    sys.exit(0)

if __name__ == "__main__":
    main()
