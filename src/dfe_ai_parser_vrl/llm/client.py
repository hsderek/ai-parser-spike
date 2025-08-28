"""
Unified LiteLLM client for DFE AI Parser VRL
Handles all LLM interactions with automatic model selection
"""

import os
import time
from typing import Dict, List, Optional, Any, Generator
import litellm
from loguru import logger
from .model_selector import DFEModelSelector


class DFELLMClient:
    """Unified LLM client using LiteLLM"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.model_selector = DFEModelSelector(config)
        self.current_model = None
        self.metadata = {}
        
        # Configure LiteLLM
        litellm.drop_params = True  # Drop unsupported params
        litellm.set_verbose = False  # Reduce verbosity
        
        # Initialize with best available model
        self._select_model()
    
    def _select_model(self, 
                     platform: str = None, 
                     capability: str = None,
                     use_case: str = None) -> str:
        """Select and set the model to use"""
        model, metadata = self.model_selector.select_model(
            platform=platform,
            capability=capability,
            use_case=use_case
        )
        
        if not model:
            # Fallback to any available model
            logger.warning("No preferred model found, trying fallback")
            model, metadata = self.model_selector.select_model(
                capability="efficient"
            )
        
        if not model:
            raise ValueError("No available models found")
        
        self.current_model = model
        self.metadata = metadata
        logger.info(f"Using model: {model} ({metadata.get('capability', 'unknown')} mode)")
        
        return model
    
    def completion(self, 
                  messages: List[Dict[str, str]], 
                  max_tokens: int = 4000,
                  temperature: float = 0.7,
                  stream: bool = False,
                  **kwargs) -> Any:
        """
        Generate completion using LiteLLM
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            stream: Whether to stream the response
            **kwargs: Additional parameters for LiteLLM
            
        Returns:
            Completion response or generator if streaming
        """
        if not self.current_model:
            self._select_model()
        
        try:
            response = litellm.completion(
                model=self.current_model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                stream=stream,
                **kwargs
            )
            
            if stream:
                return self._stream_response(response)
            else:
                return response
                
        except Exception as e:
            logger.error(f"LLM completion failed: {e}")
            
            # Try with a different model
            if "rate_limit" in str(e).lower():
                logger.info("Rate limited, switching to different model")
                self._select_model(capability="efficient")
                time.sleep(5)
                return self.completion(messages, max_tokens, temperature, stream, **kwargs)
            
            raise
    
    def _stream_response(self, response: Generator) -> Generator:
        """Handle streaming response"""
        for chunk in response:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
    
    def generate_vrl(self, 
                    sample_logs: str,
                    device_type: str = None,
                    stream: bool = True) -> str:
        """
        Generate VRL parser for sample logs
        
        Args:
            sample_logs: Sample log data
            device_type: Optional device type hint
            stream: Whether to stream the response
            
        Returns:
            Generated VRL code
        """
        # Select appropriate model for VRL generation
        self._select_model(use_case="vrl_generation")
        
        # Build messages
        messages = self._build_vrl_messages(sample_logs, device_type)
        
        # Generate completion
        if stream:
            vrl_code = ""
            for chunk in self.completion(messages, max_tokens=8000, temperature=0.3, stream=True):
                vrl_code += chunk
                print(chunk, end="", flush=True)
            print()
            return vrl_code
        else:
            response = self.completion(messages, max_tokens=8000, temperature=0.3)
            return response.choices[0].message.content
    
    def fix_vrl_error(self, 
                     vrl_code: str, 
                     error_message: str,
                     original_logs: str = None) -> str:
        """
        Fix VRL syntax error
        
        Args:
            vrl_code: VRL code with error
            error_message: Error message from validator
            original_logs: Optional original log samples
            
        Returns:
            Fixed VRL code
        """
        # Use efficient model for fixes
        self._select_model(capability="efficient")
        
        messages = [
            {
                "role": "system",
                "content": "You are a VRL (Vector Remap Language) expert. Fix the syntax error in the provided VRL code."
            },
            {
                "role": "user",
                "content": f"""Fix this VRL syntax error:

Error: {error_message}

VRL Code:
```vrl
{vrl_code}
```

Return only the fixed VRL code without explanation."""
            }
        ]
        
        response = self.completion(messages, max_tokens=8000, temperature=0.1)
        return self._extract_vrl_code(response.choices[0].message.content)
    
    def _build_vrl_messages(self, sample_logs: str, device_type: str = None) -> List[Dict[str, str]]:
        """Build messages for VRL generation"""
        system_prompt = """You are an expert in Vector Remap Language (VRL) for log parsing.
Generate a VRL parser that extracts all relevant fields from the provided logs.

Requirements:
1. Parse timestamps into proper timestamp format
2. Extract all meaningful fields
3. Handle errors gracefully with null coalescing
4. Use appropriate VRL functions
5. Return clean, working VRL code

Output only the VRL code without explanations."""
        
        user_prompt = f"""Generate a VRL parser for these logs:

{f'Device Type: {device_type}' if device_type else ''}

Sample Logs:
```
{sample_logs[:10000]}  # Limit sample size
```

Generate complete VRL code that parses these logs."""
        
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
    
    def _extract_vrl_code(self, content: str) -> str:
        """Extract VRL code from response"""
        # Remove markdown code blocks if present
        if "```vrl" in content:
            start = content.find("```vrl") + 6
            end = content.find("```", start)
            if end != -1:
                return content[start:end].strip()
        elif "```" in content:
            start = content.find("```") + 3
            end = content.find("```", start)
            if end != -1:
                return content[start:end].strip()
        
        return content.strip()
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get information about current model"""
        return {
            "model": self.current_model,
            "platform": self.metadata.get("platform"),
            "capability": self.metadata.get("capability"),
            "family": self.metadata.get("family")
        }