#!/usr/bin/env python3
"""
Dasa Sastra: JSON & OpenAPI Syntax Validator (api_validator.py)
Validates generated JSON, Swagger, and OpenAPI specs for syntax completeness.
Catches "LLM json cutoff" errors before they are committed.
"""

import os
import sys
import json
import glob

def find_json_files():
    """Find all .json files in common docs directories."""
    paths = [
        "docs/**/*.json",
        "api/**/*.json",
        "swagger.json",
        "openapi.json",
        "postman_collection.json"
    ]
    files = []
    for pattern in paths:
        files.extend(glob.glob(pattern, recursive=True))
    return list(set(files))

def validate_json(filepath):
    """Attempt to parse the JSON file to catch syntax errors."""
    try:
        with open(filepath, 'r') as f:
            content = f.read()
            # If the file is empty, it's not valid JSON
            if not content.strip():
                 return False, "File is completely empty."
                 
            json.loads(content)
            return True, "Valid"
    except json.JSONDecodeError as e:
        return False, f"Syntax Error: {str(e)}"
    except Exception as e:
        return False, f"Read Error: {str(e)}"

def main():
    print("🛡️  [Dasa Sastra] Initializing Documentation Validator...")
    
    files = find_json_files()
    if not files:
        print("🟢 [Sastra Validator] No JSON-based API documentation files found. Pass.")
        sys.exit(0)
        
    failures = []
    
    for filepath in files:
        is_valid, msg = validate_json(filepath)
        if not is_valid:
            failures.append((filepath, msg))
            
    if failures:
        print("\n🔴 [Sastra Validator] FATAL: JSON Malformation Detected!")
        print("This is usually caused by the LLM cutting off the generation mid-bracket.")
        for filepath, msg in failures:
            print(f"  - [{filepath}]: {msg}")
        print("\nHALTING OPERATION. Please ensure you generate the complete JSON structure.")
        sys.exit(1)
        
    print(f"🟢 [Sastra Validator] Validated {len(files)} JSON doc files successfully.")
    sys.exit(0)

if __name__ == "__main__":
    main()
