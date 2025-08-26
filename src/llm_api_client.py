#!/usr/bin/env python3
"""
External LLM API Client for VRL Generation

This module provides the actual integration with external LLM services
(Anthropic Claude, OpenAI GPT, etc.) to generate VRL code based on
sample data and external configuration rules.
"""

import os
import json
from typing import Dict, List, Any, Optional
from datetime import datetime
from pathlib import Path
from loguru import logger

# Import API clients (install with: pip install anthropic openai)
try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False
    logger.warning("Anthropic client not available. Install with: pip install anthropic")

try:
    import openai
    OPENAI_AVAILABLE = True  
except ImportError:
    OPENAI_AVAILABLE = False
    logger.warning("OpenAI client not available. Install with: pip install openai")


class LLMAPIClient:
    """Client for calling external LLM APIs to generate VRL code"""
    
    def __init__(self, provider: str = "anthropic", api_key: Optional[str] = None):
        """
        Initialize LLM API client
        
        Args:
            provider: LLM provider - "anthropic", "openai", or "mock"
            api_key: API key for the provider (or from env var)
        """
        self.provider = provider.lower()
        
        # Get API key from environment or parameter
        if provider == "anthropic":
            self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
            if not self.api_key:
                logger.warning("No Anthropic API key found. Set ANTHROPIC_API_KEY env var.")
                self.provider = "mock"
            elif ANTHROPIC_AVAILABLE:
                self.client = anthropic.Anthropic(api_key=self.api_key)
        
        elif provider == "openai":
            self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
            if not self.api_key:
                logger.warning("No OpenAI API key found. Set OPENAI_API_KEY env var.")
                self.provider = "mock"
            elif OPENAI_AVAILABLE:
                openai.api_key = self.api_key
                self.client = openai
                
        logger.info(f"🤖 LLM API Client initialized with provider: {self.provider}")
        
    def generate_vrl(self, 
                     sample_data: List[Dict[str, Any]], 
                     external_configs: Dict[str, str],
                     iteration: int = 1,
                     previous_errors: Optional[List[str]] = None) -> str:
        """
        Call external LLM API to generate VRL code
        
        Args:
            sample_data: Sample log records to analyze
            external_configs: External configuration rules (vector-vrl-system.md, etc.)
            iteration: Current iteration number
            previous_errors: Errors from previous attempt (for iteration)
            
        Returns:
            Generated VRL code string
        """
        # Build the prompt for the LLM
        prompt = self._build_vrl_generation_prompt(
            sample_data, external_configs, iteration, previous_errors
        )
        
        logger.info(f"📤 Calling {self.provider} API for VRL generation (iteration {iteration})")
        logger.info(f"   Prompt length: {len(prompt)} chars")
        
        # Call the appropriate API
        if self.provider == "anthropic":
            vrl_code = self._call_anthropic(prompt)
        elif self.provider == "openai":
            vrl_code = self._call_openai(prompt)
        else:
            vrl_code = self._generate_mock_vrl(sample_data)
            
        logger.info(f"📥 Received VRL code: {len(vrl_code)} chars")
        
        # Save for debugging
        debug_file = f".tmp/llm_generated_vrl_iter{iteration}.vrl"
        Path(debug_file).parent.mkdir(exist_ok=True)
        with open(debug_file, 'w') as f:
            f.write(vrl_code)
        logger.info(f"💾 Saved LLM response to {debug_file}")
        
        return vrl_code
        
    def _build_vrl_generation_prompt(self, 
                                    sample_data: List[Dict[str, Any]],
                                    external_configs: Dict[str, str],
                                    iteration: int,
                                    previous_errors: Optional[List[str]]) -> str:
        """Build the prompt to send to the external LLM"""
        
        prompt_parts = []
        
        # Add system instructions from external configs
        if 'vector_vrl_prompt' in external_configs:
            prompt_parts.append(external_configs['vector_vrl_prompt'])
            
        if 'parser_prompts' in external_configs:
            prompt_parts.append("\n# PROJECT SPECIFIC REQUIREMENTS:")
            prompt_parts.append(external_configs['parser_prompts'])
            
        # Add sample data analysis
        prompt_parts.append("\n# SAMPLE LOG DATA TO PARSE:")
        for i, sample in enumerate(sample_data[:3], 1):
            prompt_parts.append(f"\nSample {i}:")
            prompt_parts.append(json.dumps(sample, indent=2))
            
        # Add iteration feedback if this is a retry
        if iteration > 1 and previous_errors:
            prompt_parts.append(f"\n# ITERATION {iteration} - PREVIOUS ERRORS:")
            prompt_parts.append("The previous VRL had these issues:")
            for error in previous_errors[:5]:  # Limit to first 5 errors
                prompt_parts.append(f"- {error}")
            prompt_parts.append("\nPlease fix these errors in the new VRL.")
            
        # Add specific generation request
        prompt_parts.append("\n# TASK:")
        prompt_parts.append("Generate VRL code to parse the sample log data above.")
        prompt_parts.append("CRITICAL REQUIREMENTS:")
        prompt_parts.append("1. Use ONLY string operations (contains, split, slice, index)")
        prompt_parts.append("2. NO regex, NO match(), NO parse_regex() - they are 50-100x slower")
        prompt_parts.append("3. Follow the performance tiers from the configuration")
        prompt_parts.append("4. Extract fields FIRST, normalize AFTER")
        prompt_parts.append("5. Return ONLY the VRL code, no explanation")
        
        return '\n'.join(prompt_parts)
        
    def _call_anthropic(self, prompt: str) -> str:
        """Call Anthropic Claude API"""
        if not ANTHROPIC_AVAILABLE or not hasattr(self, 'client'):
            logger.error("Anthropic client not available")
            return self._generate_mock_vrl([])
            
        try:
            message = self.client.messages.create(
                model="claude-3-opus-20240229",  # or claude-3-sonnet for faster/cheaper
                max_tokens=4000,
                temperature=0.2,  # Lower temperature for more consistent code
                system="You are an expert VRL (Vector Remap Language) developer. Generate only valid VRL code.",
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            
            # Extract VRL code from response
            vrl_code = message.content[0].text
            
            # Clean up - remove markdown code blocks if present
            if "```vrl" in vrl_code:
                vrl_code = vrl_code.split("```vrl")[1].split("```")[0]
            elif "```" in vrl_code:
                vrl_code = vrl_code.split("```")[1].split("```")[0]
                
            return vrl_code.strip()
            
        except Exception as e:
            logger.error(f"Anthropic API call failed: {e}")
            return self._generate_mock_vrl([])
            
    def _call_openai(self, prompt: str) -> str:
        """Call OpenAI GPT API"""
        if not OPENAI_AVAILABLE or not hasattr(self, 'client'):
            logger.error("OpenAI client not available")
            return self._generate_mock_vrl([])
            
        try:
            response = self.client.ChatCompletion.create(
                model="gpt-4-turbo-preview",  # or gpt-3.5-turbo for faster/cheaper
                messages=[
                    {"role": "system", "content": "You are an expert VRL (Vector Remap Language) developer. Generate only valid VRL code."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,
                max_tokens=4000
            )
            
            vrl_code = response.choices[0].message.content
            
            # Clean up - remove markdown code blocks if present
            if "```vrl" in vrl_code:
                vrl_code = vrl_code.split("```vrl")[1].split("```")[0]
            elif "```" in vrl_code:
                vrl_code = vrl_code.split("```")[1].split("```")[0]
                
            return vrl_code.strip()
            
        except Exception as e:
            logger.error(f"OpenAI API call failed: {e}")
            return self._generate_mock_vrl([])
            
    def _generate_mock_vrl(self, sample_data: List[Dict[str, Any]]) -> str:
        """Generate mock VRL for testing when no API is available"""
        logger.warning("Using MOCK VRL generation (no API configured)")
        
        # Return a basic but valid VRL that follows the rules
        return """
# Mock VRL - String Operations Only
. = parse_json!(string!(.message))

if exists(.message) {
    msg = string!(.message)
    
    # Extract basic patterns using string operations
    if contains(msg, "%ASA-") {
        .source_type = "cisco_asa"
    } else if contains(msg, "%SEC-") {
        .source_type = "cisco_ios"
    } else {
        .source_type = "unknown"
    }
    
    # Extract action
    if contains(downcase(msg), "deny") {
        .action = "deny"
    } else if contains(downcase(msg), "allow") {
        .action = "allow"
    }
    
    # Extract protocol
    if contains(msg, " tcp ") {
        .protocol = "tcp"
    } else if contains(msg, " udp ") {
        .protocol = "udp"
    }
}

._parser_metadata = {
    "version": "mock-1.0.0",
    "generator": "mock_llm",
    "timestamp": now()
}

.
"""


def integrate_with_testing_loop():
    """
    Show how to integrate the LLM API client with VRLTestingLoop
    
    This method should be added to vrl_testing_loop_clean.py
    """
    integration_code = '''
    def generate_and_test_vrl_with_external_llm(self, max_iterations: int = 3) -> bool:
        """
        Generate VRL using external LLM API and test it
        
        This is the COMPLETE automation:
        1. Call external LLM API with samples + configs
        2. Test the generated VRL
        3. Iterate if needed with error feedback
        
        Args:
            max_iterations: Maximum number of generation attempts
            
        Returns:
            True if successful VRL was generated and tested
        """
        from llm_api_client import LLMAPIClient
        
        # Initialize LLM client (uses ANTHROPIC_API_KEY or OPENAI_API_KEY env var)
        llm_client = LLMAPIClient(provider="anthropic")  # or "openai"
        
        previous_errors = None
        
        for iteration in range(1, max_iterations + 1):
            self._log_with_timestamp(f"LLM VRL Generation - Iteration {iteration}/{max_iterations}")
            
            # Generate VRL using external LLM
            vrl_code = llm_client.generate_vrl(
                sample_data=self.samples[:10],  # Send first 10 samples
                external_configs=self.external_configs,
                iteration=iteration,
                previous_errors=previous_errors
            )
            
            # Test the generated VRL
            success = self.run_with_llm_generated_vrl(vrl_code, iteration)
            
            if success:
                self._log_with_timestamp(f"✅ SUCCESS! LLM generated valid VRL on iteration {iteration}")
                return True
            
            # Collect errors for next iteration
            if self.candidates and self.candidates[-1].errors:
                previous_errors = self.candidates[-1].errors
                self._log_with_timestamp(f"❌ Iteration {iteration} failed with {len(previous_errors)} errors")
            
        self._log_with_timestamp(f"❌ Failed to generate valid VRL after {max_iterations} iterations")
        return False
    '''
    return integration_code


if __name__ == "__main__":
    print("=" * 70)
    print("EXTERNAL LLM API CLIENT FOR VRL GENERATION")
    print("=" * 70)
    print("\nThis module provides the actual external LLM API integration:")
    print("✅ Anthropic Claude API support")
    print("✅ OpenAI GPT API support")
    print("✅ Automatic iteration with error feedback")
    print("✅ Mock generation for testing")
    print("\nUsage:")
    print("1. Set API key: export ANTHROPIC_API_KEY=your-key-here")
    print("2. In VRLTestingLoop: loop.generate_and_test_vrl_with_external_llm()")
    print("\nThe external LLM will:")
    print("- Analyze your sample data")
    print("- Apply the external config rules")
    print("- Generate optimized VRL")
    print("- Iterate if errors occur")
    print("=" * 70)