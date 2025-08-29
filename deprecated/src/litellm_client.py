#!/usr/bin/env python3
"""
LiteLLM-based unified LLM client
Replaces all custom LLM client code with LiteLLM's universal interface
"""

import os
import time
from typing import Dict, List, Optional, Any, Generator, Tuple
import json
from pathlib import Path
import yaml
from loguru import logger
import litellm

# Configure LiteLLM
litellm.set_verbose = False  # Reduce noise
litellm.drop_params = True   # Drop unsupported params instead of failing


class ModelPreferences:
    """Load and manage model preferences from configuration"""
    
    def __init__(self):
        self.config = self._load_model_config()
    
    def _load_model_config(self) -> Dict[str, Any]:
        """Load model preferences from YAML config"""
        try:
            config_path = Path(__file__).parent.parent / "config" / "model_preferences.yaml"
            if config_path.exists():
                with open(config_path, 'r') as f:
                    config = yaml.safe_load(f)
                logger.info(f"✅ Loaded model preferences from {config_path}")
                return config
            else:
                logger.warning(f"⚠️ Model config not found at {config_path}, using defaults")
                return self._get_default_config()
        except Exception as e:
            logger.error(f"❌ Failed to load model config: {e}")
            return self._get_default_config()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Fallback default configuration"""
        return {
            "providers": {
                "anthropic": {
                    "preference_order": [
                        {"model": "claude-opus-4-1-20250805", "capability": "highest"},
                        {"model": "claude-sonnet-4-20250514", "capability": "very_high"},
                        {"model": "claude-3-5-sonnet-20241022", "capability": "high"}
                    ]
                }
            },
            "selection_strategy": {"primary_preference": "capability"}
        }
    
    def get_preferred_models(self, provider: str, use_case: str = "general") -> List[str]:
        """Get preferred model list for a provider and use case"""
        try:
            provider_config = self.config.get("providers", {}).get(provider, {})
            preference_order = provider_config.get("preference_order", [])
            
            # Extract model names in preference order
            models = [item["model"] for item in preference_order]
            
            # Check for use-case specific preferences
            use_cases = self.config.get("use_cases", {})
            if use_case in use_cases:
                use_case_models = use_cases[use_case].get("preferred_models", [])
                # Prioritize use-case specific models
                models = use_case_models + [m for m in models if m not in use_case_models]
            
            logger.info(f"🎯 Model preference for {provider}/{use_case}: {models[:3]}")
            return models
            
        except Exception as e:
            logger.error(f"❌ Error getting preferences for {provider}: {e}")
            return ["claude-3-5-sonnet-20241022"]  # Safe fallback
    
    def get_best_model_alias(self, use_case: str) -> str:
        """Get the best model for a specific use case using aliases"""
        aliases = self.config.get("aliases", {})
        
        use_case_map = {
            "vrl_generation": "best_coding",
            "reasoning": "best_reasoning", 
            "fast": "best_speed",
            "cost_effective": "best_cost"
        }
        
        alias_key = use_case_map.get(use_case, "best_reasoning")
        return aliases.get(alias_key, "claude-opus-4-1-20250805")


# Global model preferences instance
model_prefs = ModelPreferences()


class UnifiedLLMClient:
    """
    Unified LLM client using LiteLLM
    Replaces all custom provider-specific clients with one universal interface
    """
    
    def __init__(self, api_key: str = None, provider: str = "anthropic", model_preference: str = "auto", use_case: str = "vrl_generation"):
        self.api_key = api_key or os.environ.get('ANTHROPIC_API_KEY')
        self.provider = provider
        self.model_preference = model_preference
        self.use_case = use_case
        self.current_model = None
        self.session_cost = 0.0
        self.session_tokens = {"input": 0, "output": 0}
        
        # Set API key in environment for LiteLLM
        if self.api_key:
            os.environ['ANTHROPIC_API_KEY'] = self.api_key
        
        logger.info(f"🔧 Initialized UnifiedLLMClient: {provider} provider, use_case: {use_case}")
        
        # Load preferred models from configuration
        self.preferred_models = model_prefs.get_preferred_models(provider, use_case)
    
    def get_best_available_model(self) -> str:
        """
        Get the best available model using configuration-based preferences
        Combines config preferences with LiteLLM availability checking
        """
        try:
            logger.info(f"🔍 Selecting best model for {self.provider}/{self.use_case}...")
            
            # Get available models from LiteLLM API
            available_models = self._get_anthropic_models_from_api()
            
            if not available_models:
                raise Exception("No Anthropic models found in LiteLLM API")
            
            # Try preferred models from configuration with comprehensive fallback
            for preferred_model in self.preferred_models:
                # Try primary model first
                result = self._try_model_with_fallbacks(preferred_model, available_models)
                if result:
                    self.current_model = result
                    logger.info(f"🎯 Selected model: {result} (for preferred: {preferred_model})")
                    return result
            
            # Fallback to any available model if none of the preferred ones work
            for model in available_models:
                if self._test_model_availability(model):
                    self.current_model = model
                    logger.warning(f"⚠️ No preferred models available, using fallback: {model}")
                    return model
            
            raise Exception("No available models work")
            
        except Exception as e:
            logger.error(f"❌ Model selection failed: {e}")
            # Ultimate emergency fallback
            fallback = "anthropic/claude-3-sonnet-20240229"
            self.current_model = fallback
            logger.warning(f"🆘 Emergency fallback: {fallback}")
            return fallback
    
    def _find_matching_model(self, preferred_model: str, available_models: List[str]) -> str:
        """Find the best matching available model for a preferred model"""
        # Direct match
        for available in available_models:
            if preferred_model in available or available.endswith(preferred_model):
                return available
        
        # Partial match on model name
        preferred_parts = preferred_model.lower().replace('-', '').replace('_', '')
        for available in available_models:
            available_parts = available.lower().replace('-', '').replace('_', '')
            if preferred_parts in available_parts:
                return available
        
        return None
    
    def _get_anthropic_models_from_api(self) -> List[str]:
        """Get Anthropic models from LiteLLM's model list API"""
        try:
            # Get all supported models from LiteLLM
            all_models = litellm.model_list
            
            # Filter for Anthropic/Claude models
            anthropic_models = []
            for model in all_models:
                model_lower = model.lower()
                if ('claude' in model_lower and 
                    ('opus' in model_lower or 'sonnet' in model_lower or 'haiku' in model_lower)):
                    # Clean up model name - remove duplicate prefixes
                    clean_model = model
                    if clean_model.startswith('openrouter/anthropic/'):
                        clean_model = clean_model.replace('openrouter/anthropic/', 'anthropic/')
                    elif clean_model.startswith('openrouter/'):
                        clean_model = clean_model.replace('openrouter/', '')
                    
                    # Add provider prefix if not present
                    if not clean_model.startswith('anthropic/'):
                        clean_model = f"anthropic/{clean_model}"
                    
                    anthropic_models.append(clean_model)
            
            logger.info(f"📋 Found {len(anthropic_models)} Anthropic models via API")
            return anthropic_models
            
        except Exception as e:
            logger.error(f"❌ Failed to get models from LiteLLM API: {e}")
            return []
    
    def _select_best_model(self, available_models: List[str]) -> str:
        """Select the best model from available list based on capability and preference"""
        def get_model_priority(model: str) -> int:
            """Assign priority score to models - higher is better"""
            model_lower = model.lower()
            
            # Claude 4+ models (highest priority)
            if ('claude-4' in model_lower or 'opus-4' in model_lower or 
                'sonnet-4' in model_lower or 'claude-sonnet-4' in model_lower or
                'claude-opus-4' in model_lower):
                if 'opus' in model_lower:
                    return 1000  # Opus 4 - highest capability
                elif 'sonnet' in model_lower:
                    return 950   # Sonnet 4 - latest performance
                else:
                    return 900   # Other Claude 4
            
            # Claude 3.5+ models (high priority)
            if ('3.5' in model_lower or '3-5' in model_lower):
                if 'sonnet' in model_lower:
                    return 800   # Sonnet 3.5 - excellent performance
                elif 'opus' in model_lower:
                    return 750   # Opus 3.5 (if exists)
                else:
                    return 700   # Other 3.5
            
            # Claude 3.0 models (medium priority)  
            if 'claude-3' in model_lower:
                if 'opus' in model_lower:
                    return 600   # Opus 3.0 - high capability
                elif 'sonnet' in model_lower:
                    return 500   # Sonnet 3.0 - balanced
                elif 'haiku' in model_lower:
                    return 400   # Haiku 3.0 - fast/cheap
                else:
                    return 350   # Other Claude 3
            
            # Older models (lower priority)
            return 100
        
        # Apply preference adjustments
        def adjusted_priority(model: str) -> int:
            base_priority = get_model_priority(model)
            model_lower = model.lower()
            
            if self.model_preference == "opus" and "opus" in model_lower:
                return base_priority + 100  # Boost opus preference
            elif self.model_preference == "sonnet" and "sonnet" in model_lower:
                return base_priority + 50   # Boost sonnet preference
            
            return base_priority
        
        # Sort by priority (highest first)
        sorted_models = sorted(available_models, key=adjusted_priority, reverse=True)
        
        if sorted_models:
            best_model = sorted_models[0]
            logger.info(f"🏆 Selected from {len(available_models)} models: {best_model}")
            return best_model
        else:
            raise Exception("No suitable models found in API list")
    
    def _test_model_availability(self, model: str) -> bool:
        """Test if a model is available by making a tiny completion call"""
        try:
            response = litellm.completion(
                model=model,
                messages=[{"role": "user", "content": "hi"}],
                max_tokens=1,
                temperature=0
            )
            return True
        except Exception as e:
            error_str = str(e).lower()
            
            # Check for specific "can't use that model" type errors
            model_unavailable_indicators = [
                "model not found", "invalid model", "not found", "invalid",
                "model not available", "not supported", "access denied",
                "forbidden", "unauthorized", "permission denied",
                "model disabled", "model deprecated", "unsupported model"
            ]
            
            if any(indicator in error_str for indicator in model_unavailable_indicators):
                logger.debug(f"❌ Model {model} explicitly unavailable: {e}")
                return False
            
            # Treat other errors (overloaded, rate limits, etc.) as potentially available
            logger.debug(f"⚠️ Model {model} test inconclusive (may be available): {e}")
            return True
    
    def completion(self, 
                  messages: List[Dict[str, str]], 
                  max_tokens: int = 4000,
                  temperature: float = 0.2,
                  stream: bool = False,
                  system_prompt: str = None) -> Dict[str, Any]:
        """
        Universal completion method using LiteLLM
        Works across all providers with automatic cost tracking
        """
        if not self.current_model:
            self.get_best_available_model()
        
        # Add system prompt if provided
        if system_prompt:
            messages = [{"role": "system", "content": system_prompt}] + messages
        
        try:
            start_time = time.time()
            
            # Use LiteLLM's universal completion
            response = litellm.completion(
                model=self.current_model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                stream=stream
            )
            
            end_time = time.time()
            duration = end_time - start_time
            
            if stream:
                # Return streaming generator
                return self._handle_streaming_response(response, duration)
            else:
                # Handle non-streaming response
                return self._handle_response(response, duration)
                
        except Exception as e:
            logger.error(f"❌ LiteLLM completion failed: {e}")
            raise
    
    def _handle_response(self, response, duration: float) -> Dict[str, Any]:
        """Handle non-streaming response with cost tracking"""
        try:
            # Extract content
            content = response.choices[0].message.content
            
            # Track usage and cost
            usage = response.usage
            input_tokens = usage.prompt_tokens
            output_tokens = usage.completion_tokens
            
            # Calculate cost using LiteLLM
            cost = litellm.completion_cost(response)
            
            # Update session tracking
            self.session_tokens["input"] += input_tokens
            self.session_tokens["output"] += output_tokens
            self.session_cost += cost
            
            logger.info(f"✅ LLM completion: {output_tokens} tokens, ${cost:.4f}, {duration:.1f}s")
            
            return {
                "content": content,
                "usage": {
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "total_tokens": input_tokens + output_tokens
                },
                "cost": cost,
                "duration": duration,
                "model": self.current_model
            }
            
        except Exception as e:
            logger.error(f"❌ Response handling failed: {e}")
            # Return basic response if cost calculation fails
            return {
                "content": response.choices[0].message.content,
                "model": self.current_model,
                "duration": duration
            }
    
    def _handle_streaming_response(self, stream, duration: float) -> Generator[Dict[str, Any], None, None]:
        """Handle streaming response with cost tracking"""
        content_chunks = []
        
        try:
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    chunk_content = chunk.choices[0].delta.content
                    content_chunks.append(chunk_content)
                    
                    yield {
                        "content": chunk_content,
                        "type": "chunk",
                        "model": self.current_model
                    }
            
            # Final summary
            full_content = "".join(content_chunks)
            yield {
                "content": full_content,
                "type": "complete",
                "model": self.current_model,
                "duration": duration
            }
            
        except Exception as e:
            logger.error(f"❌ Streaming handling failed: {e}")
            yield {
                "content": "",
                "type": "error",
                "error": str(e)
            }
    
    def get_session_metrics(self) -> Dict[str, Any]:
        """Get session-level metrics"""
        return {
            "total_cost": self.session_cost,
            "total_input_tokens": self.session_tokens["input"],
            "total_output_tokens": self.session_tokens["output"],
            "current_model": self.current_model,
            "provider": self.provider
        }
    
    def reset_session_metrics(self):
        """Reset session-level tracking"""
        self.session_cost = 0.0
        self.session_tokens = {"input": 0, "output": 0}
        logger.info("🔄 Reset session metrics")


class LiteLLMVRLGenerator:
    """
    VRL-specific LLM generator using LiteLLM
    Replaces the complex LLM session management code
    """
    
    def __init__(self, provider: str = "anthropic", model_preference: str = "opus"):
        self.client = UnifiedLLMClient(provider=provider, model_preference=model_preference)
        self.iteration_history = []
    
    def generate_vrl(self, 
                    samples: List[str], 
                    system_prompt: str,
                    context_prompt: str,
                    max_iterations: int = 10) -> Dict[str, Any]:
        """
        Generate VRL using LiteLLM with iterative refinement
        """
        messages = [
            {"role": "user", "content": f"{context_prompt}\n\nSamples:\n{json.dumps(samples, indent=2)}"}
        ]
        
        try:
            result = self.client.completion(
                messages=messages,
                system_prompt=system_prompt,
                max_tokens=8000,
                temperature=0.1
            )
            
            self.iteration_history.append({
                "iteration": len(self.iteration_history) + 1,
                "content": result["content"],
                "cost": result.get("cost", 0),
                "tokens": result.get("usage", {}).get("total_tokens", 0),
                "model": result.get("model")
            })
            
            return {
                "vrl_code": result["content"],
                "metadata": {
                    "model": result.get("model"),
                    "cost": result.get("cost", 0),
                    "tokens": result.get("usage", {}),
                    "iteration": len(self.iteration_history)
                }
            }
            
        except Exception as e:
            logger.error(f"❌ VRL generation failed: {e}")
            raise
    
    def iterate_with_feedback(self, 
                            feedback: str, 
                            previous_vrl: str) -> Dict[str, Any]:
        """
        Iterate VRL generation with error feedback
        """
        messages = [
            {"role": "user", "content": f"Previous VRL:\n```vrl\n{previous_vrl}\n```\n\nFeedback:\n{feedback}\n\nPlease fix the issues and provide improved VRL."}
        ]
        
        try:
            result = self.client.completion(
                messages=messages,
                system_prompt="You are a VRL expert. Fix the provided VRL code based on the feedback.",
                max_tokens=8000,
                temperature=0.1
            )
            
            self.iteration_history.append({
                "iteration": len(self.iteration_history) + 1,
                "content": result["content"],
                "cost": result.get("cost", 0),
                "tokens": result.get("usage", {}).get("total_tokens", 0),
                "model": result.get("model"),
                "feedback": feedback
            })
            
            return {
                "vrl_code": result["content"],
                "metadata": {
                    "model": result.get("model"),
                    "cost": result.get("cost", 0),
                    "tokens": result.get("usage", {}),
                    "iteration": len(self.iteration_history)
                }
            }
            
        except Exception as e:
            logger.error(f"❌ VRL iteration failed: {e}")
            raise
    
    def get_total_cost(self) -> float:
        """Get total cost for all iterations"""
        return sum(item.get("cost", 0) for item in self.iteration_history)
    
    def get_session_summary(self) -> Dict[str, Any]:
        """Get complete session summary"""
        return {
            "total_iterations": len(self.iteration_history),
            "total_cost": self.get_total_cost(),
            "models_used": list(set(item.get("model") for item in self.iteration_history)),
            "client_metrics": self.client.get_session_metrics(),
            "history": self.iteration_history
        }


# Global instance for easy import
litellm_client = UnifiedLLMClient()


if __name__ == "__main__":
    # Quick test of the client
    print("🧪 Testing UnifiedLLMClient...")
    
    client = UnifiedLLMClient(provider='anthropic', model_preference='sonnet')
    
    # Test model selection
    print("\n🎯 Testing model selection...")
    try:
        best_model = client.get_best_available_model()
        print(f"Selected model: {best_model}")
    except Exception as e:
        print(f"❌ Model selection failed: {e}")
    
    print("\n✅ Basic client test completed!")