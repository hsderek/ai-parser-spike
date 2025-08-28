#!/usr/bin/env python3
"""
Test Automated LLM VRL Generation

Demonstrates the complete automated workflow:
1. Load sample data
2. Call external LLM API (Claude/GPT/Gemini) 
3. Generate VRL code
4. Test with PyVRL and Vector
5. Iterate with feedback if needed
6. Save successful results
"""

import os
import sys
sys.path.append('./src')

from vrl_testing_loop_clean import VRLTestingLoop
from loguru import logger

def main():
    print("=" * 80)
    print("AUTOMATED VRL GENERATION WITH EXTERNAL LLM")
    print("=" * 80)
    
    # Check for API key
    provider = "anthropic"  # Default to Claude
    
    if os.environ.get("ANTHROPIC_API_KEY"):
        print("✅ Anthropic API key found")
        provider = "anthropic"
    elif os.environ.get("OPENAI_API_KEY"):
        print("✅ OpenAI API key found")
        provider = "openai"
    elif os.environ.get("GOOGLE_API_KEY"):
        print("✅ Google API key found")
        provider = "gemini"
    else:
        print("⚠️  No API key found - using MOCK provider")
        print("   To use real LLM, set one of:")
        print("   - export ANTHROPIC_API_KEY=your-key")
        print("   - export OPENAI_API_KEY=your-key")
        print("   - export GOOGLE_API_KEY=your-key")
        provider = "mock"
    
    # Select sample file - use smaller one for faster testing
    sample_file = "samples/cisco-asa.ndjson"
    
    # Allow override from command line
    if len(sys.argv) > 1 and not sys.argv[1].startswith("--"):
        sample_file = sys.argv[1]
    
    if not os.path.exists(sample_file):
        print(f"❌ Sample file not found: {sample_file}")
        print("   Run: python generate_large_samples.py")
        return
        
    print(f"\n📊 Using sample file: {sample_file}")
    print(f"🤖 LLM Provider: {provider}")
    print("-" * 80)
    
    # Initialize VRL testing loop
    loop = VRLTestingLoop(sample_file)
    
    print("\n🚀 Starting automated VRL generation...")
    print("   This will:")
    print("   1. Call external LLM API with sample data")
    print("   2. Generate VRL code following performance rules")
    print("   3. Test with PyVRL and Vector CLI")
    print("   4. Iterate with feedback if errors occur")
    print("   5. Save successful VRL to samples-parsed/")
    print("-" * 80)
    
    # Check for model override from command line or env
    model_override = os.environ.get("MODEL_OVERRIDE")
    if len(sys.argv) > 1 and sys.argv[1].startswith("--model="):
        model_override = sys.argv[1].split("=")[1]
    
    if model_override:
        print(f"🎯 Model override: {model_override}")
    
    # Run the automated generation
    success = loop.run_automated_llm_generation(
        provider=provider,
        max_iterations=2,
        model_override=model_override
    )
    
    print("\n" + "=" * 80)
    if success:
        print("✅ SUCCESS! Valid VRL generated and tested")
        print(f"📁 Check samples-parsed/ for results:")
        print(f"   - cisco-asa-large.vrl (VRL code)")
        print(f"   - cisco-asa-large.json (transformed data)")
        print(f"   - cisco-asa-large-rest.json (API results)")
        
        # Show performance results
        if loop.best_candidate:
            c = loop.best_candidate
            print(f"\n📊 Performance Results:")
            print(f"   Events/CPU%: {getattr(c, 'events_per_cpu_percent', 0):.0f}")
            print(f"   VPI Score: {getattr(c, 'vpi', 0):.1f}")
            print(f"   Tier: {getattr(c, 'performance_tier', 'Unknown')}")
            print(f"   Fields extracted: {len(getattr(c, 'extracted_fields', []))}")
    else:
        print("❌ Failed to generate valid VRL")
        print("   Check logs/ directory for details")
        
        # Show last error
        if loop.candidates and loop.candidates[-1].errors:
            print(f"\n Last error: {loop.candidates[-1].errors[0][:200]}...")
    
    print("=" * 80)


if __name__ == "__main__":
    main()