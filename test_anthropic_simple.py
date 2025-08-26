#!/usr/bin/env python3
"""
Simple test with REAL Anthropic API
Shows progress in real-time
"""

import os
import sys
from dotenv import load_dotenv
sys.path.append('./src')

from llm_iterative_session import IterativeLLMSession
from loguru import logger
import json

def main():
    print("=" * 60)
    print("SIMPLE ANTHROPIC API TEST")
    print("=" * 60)
    
    # Load .env file
    load_dotenv()
    
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("❌ No ANTHROPIC_API_KEY found in .env")
        return
    
    print("✅ API key loaded from .env\n")
    
    # Load sample data
    sample_file = "samples/cisco-asa-large.ndjson"
    with open(sample_file) as f:
        samples = [json.loads(line) for line in f.readlines()[:5]]
    
    print(f"📊 Loaded {len(samples)} samples")
    
    # Load external configs
    external_configs = {}
    with open("external/vector-vrl-system.md") as f:
        external_configs["vector_vrl_prompt"] = f.read()
    
    print("📋 Loaded external configs\n")
    
    # Initialize LLM session
    session = IterativeLLMSession(provider="anthropic")
    
    # Generate initial VRL
    print("🚀 Generating initial VRL via Anthropic API...")
    vrl_code, success = session.generate_initial_vrl(samples, external_configs)
    
    if success:
        print(f"✅ Received VRL ({len(vrl_code)} chars)")
        print("\n📝 Generated VRL preview:")
        print("-" * 40)
        lines = vrl_code.split('\n')
        for i, line in enumerate(lines[:10]):
            print(f"{i+1:3}: {line}")
        if len(lines) > 10:
            print(f"... ({len(lines)-10} more lines)")
        print("-" * 40)
        
        # Save to file
        output_file = ".tmp/anthropic_test.vrl"
        with open(output_file, 'w') as f:
            f.write(vrl_code)
        print(f"\n💾 Saved to {output_file}")
        
        # Check for common issues
        issues = []
        if "parse_regex" in vrl_code:
            issues.append("❌ Contains parse_regex (forbidden)")
        if "match(" in vrl_code:
            issues.append("❌ Contains match() (forbidden)")
        if "to_timestamp" in vrl_code:
            issues.append("⚠️  Uses to_timestamp (should be parse_timestamp)")
        if "index(" in vrl_code:
            issues.append("⚠️  Uses index() (not a VRL function)")
        
        if issues:
            print("\n🔍 Issues found:")
            for issue in issues:
                print(f"   {issue}")
        else:
            print("\n✅ No obvious issues found!")
            
    else:
        print("❌ Failed to generate VRL")
    
    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()