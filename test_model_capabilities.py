#!/usr/bin/env python3
"""
Test Model Capabilities Detection
Shows how the system captures model information for optimization
"""

import sys
sys.path.append('./src')

from llm_iterative_session import IterativeLLMSession
import json

def test_capabilities():
    print("=" * 70)
    print("MODEL CAPABILITIES TEST")
    print("=" * 70)
    
    # Test each provider (mock mode since no API keys needed)
    providers = ["anthropic", "openai", "gemini", "mock"]
    
    for provider in providers:
        print(f"\n🔍 Testing {provider.upper()} provider:")
        print("-" * 50)
        
        try:
            session = IterativeLLMSession(provider=provider)
            
            # Get optimization info
            opt_info = session.get_optimization_info()
            
            if opt_info:
                print(f"Model: {opt_info['model_name']}")
                print(f"Context Window: {opt_info['max_context_tokens']:,} tokens")
                print(f"Max Input: {opt_info['max_input_tokens']:,} tokens")
                print(f"Max Output: {opt_info['max_output_tokens']:,} tokens")
                print(f"Recommended Input Limit: {opt_info['recommended_input_limit']:,} tokens")
                
                if opt_info['cost_per_input_token'] > 0:
                    print(f"Cost per 1M input tokens: ${opt_info['cost_per_input_token'] * 1000000:.2f}")
                    print(f"Cost per 1M output tokens: ${opt_info['cost_per_output_token'] * 1000000:.2f}")
                
                print(f"System Messages: {'✅' if opt_info['supports_system_messages'] else '❌'}")
                print(f"Function Calling: {'✅' if opt_info['supports_function_calling'] else '❌'}")
                
                # Show session summary
                summary = session.get_session_summary()
                if "model_capabilities" in summary:
                    caps = summary["model_capabilities"]
                    print(f"\n📊 Full Capabilities Available for Optimization:")
                    print(json.dumps(caps, indent=2))
            else:
                print("No capabilities detected")
                
        except Exception as e:
            print(f"❌ Error: {e}")
    
    print("\n" + "=" * 70)
    print("✅ Model capabilities system ready for optimization!")
    print("💡 These variables will be used for:")
    print("   - Context window management")
    print("   - Token-aware prompt optimization") 
    print("   - Cost estimation")
    print("   - Feature compatibility checks")
    print("=" * 70)


if __name__ == "__main__":
    test_capabilities()