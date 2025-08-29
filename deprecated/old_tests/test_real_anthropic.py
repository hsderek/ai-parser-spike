#!/usr/bin/env python3
"""
Test with REAL Anthropic API
Loads API key from .env file
"""

import os
import sys
from dotenv import load_dotenv
sys.path.append('./src')

from vrl_testing_loop_clean import VRLTestingLoop
from loguru import logger

def main():
    print("=" * 80)
    print("TESTING WITH REAL ANTHROPIC API")
    print("=" * 80)
    
    # Load .env file
    load_dotenv()
    
    # Check for API key
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("\n❌ ANTHROPIC_API_KEY not set!")
        print("\nTo test with real Anthropic API:")
        print("1. Get your API key from https://console.anthropic.com/")
        print("2. Run: export ANTHROPIC_API_KEY='your-api-key-here'")
        print("3. Run this script again: python test_real_anthropic.py")
        print("\nNote: Using the API will consume credits from your account.")
        print("      The test will make 1-5 API calls depending on iterations needed.")
        return
    
    print("✅ Anthropic API key found")
    print("\n⚠️  This will make REAL API calls and consume credits!")
    print("Proceeding with test...")
    
    # Use the large Cisco ASA sample
    sample_file = "samples/cisco-asa-large.ndjson"
    
    if not os.path.exists(sample_file):
        print(f"❌ Sample file not found: {sample_file}")
        return
        
    print(f"\n📊 Using sample file: {sample_file}")
    print("🤖 LLM Provider: anthropic (REAL API)")
    print("-" * 80)
    
    # Initialize VRL testing loop
    loop = VRLTestingLoop(sample_file)
    
    print("\n🚀 Starting REAL Anthropic API VRL generation...")
    print("   This will:")
    print("   1. Send sample data to Claude API")
    print("   2. Generate VRL code following no-regex rules")
    print("   3. Test with PyVRL and Vector")
    print("   4. Iterate with feedback if needed")
    print("-" * 80)
    
    # Run with real Anthropic API
    success = loop.run_automated_llm_generation(
        provider="anthropic",
        max_iterations=5
    )
    
    print("\n" + "=" * 80)
    if success:
        print("✅ SUCCESS! Valid VRL generated using REAL Anthropic API")
        print(f"\n📁 Results saved:")
        print(f"   - samples-parsed/cisco-asa-large.vrl")
        print(f"   - samples-parsed/cisco-asa-large.json")
        print(f"   - samples-parsed/cisco-asa-large-rest.json")
        
        # Show the generated VRL
        vrl_path = "samples-parsed/cisco-asa-large.vrl"
        if os.path.exists(vrl_path):
            print(f"\n📝 Generated VRL code:")
            print("-" * 40)
            with open(vrl_path, 'r') as f:
                print(f.read())
            print("-" * 40)
        
        # Show performance
        if loop.best_candidate:
            c = loop.best_candidate
            print(f"\n📊 Performance Results:")
            print(f"   Events/CPU%: {c.events_per_cpu_percent:.0f}")
            print(f"   VPI Score: {c.vpi:.1f}")
            print(f"   Tier: {c.performance_tier}")
            print(f"   Fields extracted: {len(c.extracted_fields)}")
    else:
        print("❌ Failed to generate valid VRL")
        if loop.candidates and loop.candidates[-1].errors:
            print(f"\nLast error: {loop.candidates[-1].errors[0]}")
    
    print("=" * 80)


if __name__ == "__main__":
    main()