"""
Safe LLM Wrapper with Comprehensive Error Handling

Implements LiteLLM best practices for error handling, retry logic, and fallbacks.
Provides generic wrapper for all LLM operations with smart exception management.
"""

import time
from typing import Dict, List, Optional, Any, Union
import litellm
from loguru import logger
from .error_handler import handle_llm_error, validate_llm_response


class SafeLLMWrapper:
    """Generic LLM wrapper with comprehensive error handling"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.fallback_models = [
            "anthropic/claude-3-5-sonnet-20241022",
            "openai/gpt-4o-mini",
            "anthropic/claude-3-haiku-20240307"
        ]
        
        # Configure LiteLLM with retries
        litellm.num_retries = 2  # Built-in retry mechanism
        litellm.drop_params = True  # Drop unsupported params gracefully
        litellm.set_verbose = False  # Reduce noise
    
    def safe_completion(self, 
                       model: str,
                       messages: List[Dict[str, str]],
                       use_case: str = "production",
                       **kwargs) -> Any:
        """
        Safe LLM completion with comprehensive error handling
        
        Args:
            model: Primary model to use
            messages: Messages for completion
            use_case: Use case for hyperparameter lookup
            **kwargs: Additional parameters
            
        Returns:
            LiteLLM completion response
        """
        # Get hyperparameters from config
        hyperparams = self._get_hyperparameters(use_case)
        
        # Merge config hyperparams with kwargs
        final_params = {**hyperparams, **kwargs}
        
        # Build models list with fallbacks
        models_to_try = [model] + self.fallback_models
        models_to_try = list(dict.fromkeys(models_to_try))  # Remove duplicates
        
        last_error = None
        
        for attempt, current_model in enumerate(models_to_try, 1):
            try:
                logger.debug(f"🔄 Attempting LLM call {attempt}/{len(models_to_try)}: {current_model}")
                
                # Make the actual LiteLLM call
                response = litellm.completion(
                    model=current_model,
                    messages=messages,
                    **final_params
                )
                
                # Validate response content
                if hasattr(response, 'choices') and response.choices:
                    content = response.choices[0].message.content
                    is_valid, validation_error = validate_llm_response(content, f"{use_case} with {current_model}")
                    
                    if not is_valid:
                        logger.warning(f"📭 Invalid response from {current_model}: {validation_error}")
                        if attempt < len(models_to_try):
                            continue  # Try next model
                        else:
                            raise ValueError(f"All models returned invalid content: {validation_error}")
                
                # Success!
                logger.info(f"✅ LLM call successful with {current_model}")
                
                # Log usage info
                if hasattr(response, 'usage') and response.usage:
                    logger.debug(f"   Tokens: {response.usage.completion_tokens} completion, {response.usage.prompt_tokens} prompt")
                
                return response
                
            except Exception as e:
                last_error = e
                
                # Smart error classification
                error_info = handle_llm_error(e, operation=f"{use_case} with {current_model}")
                
                # Check if we should try next model
                if attempt < len(models_to_try):
                    if error_info["error_category"] in ["api", "network"]:
                        logger.info(f"🔄 Trying next model due to {error_info['error_category']} error")
                        
                        # Add delay based on error type
                        delay = self._get_error_delay(error_info["error_category"], attempt)
                        if delay > 0:
                            logger.info(f"   Waiting {delay}s before next attempt...")
                            time.sleep(delay)
                        
                        continue
                    elif error_info["is_infrastructure_issue"]:
                        logger.error(f"⚙️ Infrastructure issue - cannot retry: {e}")
                        break
                else:
                    logger.error(f"❌ All models failed, last error: {e}")
                    break
        
        # All models failed
        if last_error:
            raise last_error
        else:
            raise RuntimeError("LLM completion failed with no specific error")
    
    def _get_hyperparameters(self, use_case: str) -> Dict[str, Any]:
        """Get hyperparameters from config for use case"""
        use_cases = self.config.get("use_cases", {})
        use_case_config = use_cases.get(use_case, {})
        
        # Default hyperparameters
        defaults = {
            "max_tokens": 4000,
            "temperature": 0.3,
            "top_p": 0.9,
            "frequency_penalty": 0,
            "presence_penalty": 0
        }
        
        # Override with config values
        hyperparams = {**defaults}
        for key in ["max_tokens", "temperature", "top_p", "frequency_penalty", "presence_penalty"]:
            if key in use_case_config:
                hyperparams[key] = use_case_config[key]
        
        logger.debug(f"Hyperparameters for {use_case}: {hyperparams}")
        return hyperparams
    
    def _get_error_delay(self, error_category: str, attempt: int) -> float:
        """Get delay before retry based on error type and attempt"""
        
        delays = {
            "network": [1.0, 2.0, 4.0],  # Exponential backoff
            "api": [2.0, 5.0, 10.0],     # Longer delays for API issues
            "empty_response": [0.5, 1.0, 2.0]  # Shorter delays for empty responses
        }
        
        if error_category in delays:
            delay_list = delays[error_category]
            return delay_list[min(attempt - 1, len(delay_list) - 1)]
        
        return 1.0  # Default delay


# Global safe wrapper instance
_safe_wrapper = None

def get_safe_llm_wrapper(config: Dict[str, Any] = None):
    """Get or create global safe LLM wrapper"""
    global _safe_wrapper
    
    if _safe_wrapper is None:
        _safe_wrapper = SafeLLMWrapper(config)
    
    return _safe_wrapper

def safe_llm_call(model: str, messages: List[Dict[str, str]], use_case: str = "production", **kwargs):
    """Generic safe LLM call with error handling"""
    wrapper = get_safe_llm_wrapper()
    return wrapper.safe_completion(model, messages, use_case, **kwargs)