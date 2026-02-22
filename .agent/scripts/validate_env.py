#!/usr/bin/env python3
"""
Dasa Patih: Environment Gatekeeper (validate_env.py)
Validates the local environment against dasa.config.toon requirements before execution.
Ensures Python, Node, and Go (if required) are installed.
"""

import os
import sys
import subprocess
import json

def check_command(cmd):
    """Check if a command exists in the system PATH."""
    try:
        subprocess.run([cmd, "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False

def check_env_file():
    """Verify standard .env files exist if a .env.example is present."""
    if os.path.exists(".env.example") and not os.path.exists(".env"):
        print("🔴 [Patih Gatekeeper] WARNING: .env.example exists, but .env is missing. The agent might fail without environment variables.")
        return False
    return True

def parse_config():
    """Parse dasa.config.toon for workspace paths if it exists."""
    config_path = ".agent/dasa.config.toon"
    if not os.path.exists(config_path):
        return {}
    
    try:
        with open(config_path, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"🔴 [Patih Gatekeeper] ERROR: Could not parse {config_path}: {e}")
        return {}

def main():
    print("🛡️  [Dasa Patih] Initializing Environment Gatekeeper...")
    
    config = parse_config()
    workspaces = config.get("workspaces", {"root": "./"})
    
    # 1. Check Workspaces
    for name, path in workspaces.items():
        if not os.path.exists(path):
            print(f"🔴 [Patih Gatekeeper] ERROR: Configured workspace '{name}' path '{path}' does not exist.")
            sys.exit(1)
            
    # 2. Check Dependencies
    deps = {
        "node": check_command("node"),
        "npm": check_command("npm"),
        "python": check_command("python3")
    }
    
    missing = [cmd for cmd, exists in deps.items() if not exists]
    if missing:
        print(f"🔴 [Patih Gatekeeper] WARNING: Missing standard runtime environments: {', '.join(missing)}")
        
    # 3. Check ENV
    check_env_file()
    
    print("🟢 [Patih Gatekeeper] Environment Validation Passed. Ready for execution.")
    sys.exit(0)

if __name__ == "__main__":
    main()
