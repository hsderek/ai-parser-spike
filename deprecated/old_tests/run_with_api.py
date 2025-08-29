#!/usr/bin/env python3
"""
Run test with proper API key from .env file
"""
import os
import subprocess
import sys
from pathlib import Path

def load_env_file():
    """Load environment variables from .env file"""
    env_file = Path('.env')
    if not env_file.exists():
        print("No .env file found")
        return {}
    
    env_vars = {}
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                env_vars[key] = value
    return env_vars

def main():
    # Load environment variables
    env_vars = load_env_file()
    
    # Update current environment
    current_env = os.environ.copy()
    current_env.update(env_vars)
    
    # Show API key status
    if 'ANTHROPIC_API_KEY' in env_vars:
        print(f"✅ Anthropic API key loaded: {env_vars['ANTHROPIC_API_KEY'][:20]}...")
    else:
        print("⚠️  No Anthropic API key found in .env")
    
    print("🚀 Running automated VRL generation with real Claude API...")
    print()
    
    # Run the test with proper environment - use smaller sample for faster testing
    cmd = ["uv", "run", "python", "test_automated_llm_vrl.py"]
    # You can override the sample file by modifying the script or using environment variable
    result = subprocess.run(cmd, env=current_env, timeout=600)  # 10 minute timeout
    
    return result.returncode

if __name__ == "__main__":
    sys.exit(main())