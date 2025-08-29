#!/usr/bin/env python3
"""
Test Model Selection: Auto-Detection vs Override
Verifies that model selection works correctly with both auto-detection and manual override
"""

import sys
sys.path.append('./src')

from llm_iterative_session import IterativeLLMSession
import json

def test_model_selection():
    print("=" * 80)
    print("MODEL SELECTION TEST - AUTO-DETECTION VS OVERRIDE")
    print("=" * 80)
    
    test_cases = [
        {
            "name": "Anthropic Auto-Detection",
            "provider": "anthropic",
            "model": None,
            "description": "Let system auto-detect latest Claude model"
        },
        {
            "name": "Anthropic Override - Claude 3 Opus",
            "provider": "anthropic", 
            "model": "claude-3-opus-20240229",
            "description": "Force use of Claude 3 Opus"
        },
        {
            "name": "Anthropic Override - Claude 3.5 Sonnet (June)",
            "provider": "anthropic",
            "model": "claude-3-5-sonnet-20240620", 
            "description": "Force use of earlier Claude 3.5 Sonnet"
        },
        {
            "name": "Anthropic Override - Claude 3 Haiku",
            "provider": "anthropic",
            "model": "claude-3-haiku-20240307",
            "description": "Force use of fastest/cheapest model"
        },
        {
            "name": "OpenAI Auto-Detection",
            "provider": "openai",
            "model": None,
            "description": "Let system auto-detect latest GPT model"
        },
        {
            "name": "OpenAI Override - GPT-4",
            "provider": "openai",
            "model": "gpt-4",
            "description": "Force use of GPT-4"
        },
        {
            "name": "Gemini Auto-Detection", 
            "provider": "gemini",
            "model": None,
            "description": "Let system auto-detect latest Gemini model"
        },
        {
            "name": "Gemini Override - Gemini Pro",
            "provider": "gemini",
            "model": "gemini-pro",
            "description": "Force use of Gemini Pro"
        }
    ]
    
    results = []
    
    for test_case in test_cases:
        print(f"\n🧪 {test_case['name']}")
        print(f"   {test_case['description']}")
        print("-" * 60)
        
        try:
            # Initialize session with or without model override
            session = IterativeLLMSession(
                provider=test_case["provider"],
                model=test_case["model"]
            )
            
            # Get the selected model and capabilities
            selected_model = getattr(session, 'model', 'none')
            capabilities = session.get_optimization_info()
            
            result = {
                "test_name": test_case["name"],
                "provider": test_case["provider"],
                "requested_model": test_case["model"],
                "selected_model": selected_model,
                "auto_detected": test_case["model"] is None,
                "override_successful": test_case["model"] == selected_model if test_case["model"] else True,
                "context_tokens": capabilities.get("max_context_tokens", 0),
                "cost_per_input": capabilities.get("cost_per_input_token", 0),
                "cost_per_output": capabilities.get("cost_per_output_token", 0)
            }
            
            results.append(result)
            
            # Display results
            if test_case["model"]:
                if selected_model == test_case["model"]:
                    print(f"✅ Override successful: {selected_model}")
                else:
                    print(f"⚠️  Override failed: requested {test_case['model']}, got {selected_model}")
            else:
                print(f"🔍 Auto-detected: {selected_model}")
            
            print(f"📊 Context: {capabilities.get('max_context_tokens', 0):,} tokens")
            if capabilities.get('cost_per_input_token', 0) > 0:
                cost_1m_input = capabilities['cost_per_input_token'] * 1000000
                cost_1m_output = capabilities['cost_per_output_token'] * 1000000
                print(f"💰 Cost: ${cost_1m_input:.2f}/${cost_1m_output:.2f} per 1M tokens (input/output)")
            
        except Exception as e:
            print(f"❌ Error: {e}")
            result = {
                "test_name": test_case["name"],
                "error": str(e)
            }
            results.append(result)
    
    # Summary
    print(f"\n" + "=" * 80)
    print("SUMMARY - MODEL SELECTION RESULTS")
    print("=" * 80)
    
    successful_auto = 0
    successful_override = 0
    failed_tests = 0
    
    for result in results:
        if "error" in result:
            failed_tests += 1
            print(f"❌ {result['test_name']}: {result['error']}")
        else:
            if result["auto_detected"]:
                successful_auto += 1
                print(f"🔍 {result['test_name']}: Auto-detected {result['selected_model']}")
            else:
                if result["override_successful"]:
                    successful_override += 1
                    print(f"✅ {result['test_name']}: Override to {result['selected_model']}")
                else:
                    failed_tests += 1
                    print(f"⚠️  {result['test_name']}: Override failed")
    
    print(f"\n📊 Results:")
    print(f"   Auto-detection tests: {successful_auto} successful")
    print(f"   Override tests: {successful_override} successful") 
    print(f"   Failed tests: {failed_tests}")
    
    # Save detailed results
    with open('.tmp/model_selection_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n💾 Detailed results saved to .tmp/model_selection_results.json")
    print("=" * 80)


if __name__ == "__main__":
    test_model_selection()