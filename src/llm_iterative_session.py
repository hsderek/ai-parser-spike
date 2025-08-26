#!/usr/bin/env python3
"""
Iterative LLM Session Manager for VRL Generation

Maintains a full conversation session with external LLMs (Claude, GPT, Gemini)
to iteratively generate, test, and refine VRL code based on test results.
"""

import os
import json
import time
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from pathlib import Path
from loguru import logger
from enum import Enum
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import LLM clients
try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

try:
    import openai
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

try:
    import boto3
    BEDROCK_AVAILABLE = True
except ImportError:
    BEDROCK_AVAILABLE = False


class LLMProvider(Enum):
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    GEMINI = "gemini"
    BEDROCK = "bedrock"
    MOCK = "mock"


class ModelCapabilities:
    """Model capability and token information"""
    def __init__(self, 
                 max_input_tokens: int,
                 max_output_tokens: int,
                 context_window: int,
                 cost_per_input_token: float = 0.0,
                 cost_per_output_token: float = 0.0,
                 supports_system_messages: bool = True,
                 supports_function_calling: bool = False):
        self.max_input_tokens = max_input_tokens
        self.max_output_tokens = max_output_tokens
        self.context_window = context_window
        self.cost_per_input_token = cost_per_input_token
        self.cost_per_output_token = cost_per_output_token
        self.supports_system_messages = supports_system_messages
        self.supports_function_calling = supports_function_calling


class IterativeLLMSession:
    """Manages iterative conversation with external LLM for VRL generation"""
    
    def __init__(self, 
                 provider: str = "anthropic",
                 api_key: Optional[str] = None,
                 model: Optional[str] = None,
                 fast_iteration_mode: bool = False):
        """
        Initialize iterative LLM session
        
        Args:
            provider: "anthropic", "openai", "gemini", "bedrock", or "mock"
            api_key: API key (or from env var)
            model: Specific model to use (or defaults)
            fast_iteration_mode: Use fastest/cheapest models for rapid iteration
        """
        self.provider = LLMProvider(provider.lower())
        self.conversation_history = []
        self.iteration_count = 0
        self.session_id = f"llm_session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.fast_iteration_mode = fast_iteration_mode
        
        # Support for multiple API keys (round-robin to distribute load)
        self.api_keys = []
        if api_key and ',' in api_key:
            self.api_keys = [key.strip() for key in api_key.split(',')]
            self.current_key_index = 0
        
        # Model capabilities - will be set after initialization
        self.model_capabilities: Optional[ModelCapabilities] = None
        
        # Initialize the appropriate client
        if self.provider == LLMProvider.ANTHROPIC:
            self._init_anthropic(api_key, model)
        elif self.provider == LLMProvider.OPENAI:
            self._init_openai(api_key, model)
        elif self.provider == LLMProvider.GEMINI:
            self._init_gemini(api_key, model)
        elif self.provider == LLMProvider.BEDROCK:
            self._init_bedrock(api_key, model)
        else:
            logger.warning("Using MOCK provider - no real LLM API calls")
            self.provider = LLMProvider.MOCK
            self.model = "mock-model"
            # Set mock capabilities
            self.model_capabilities = self._get_model_capabilities(self.model, "mock")
            
        logger.info(f"🤖 Iterative LLM Session initialized")
        logger.info(f"   Provider: {self.provider.value}")
        logger.info(f"   Model: {getattr(self, 'model', 'none')}")
        logger.info(f"   Session: {self.session_id}")
        
        # Log model capabilities for optimization reference
        if self.model_capabilities:
            logger.info(f"📊 Model Capabilities:")
            logger.info(f"   Context Window: {self.model_capabilities.context_window:,} tokens")
            logger.info(f"   Max Input: {self.model_capabilities.max_input_tokens:,} tokens")
            logger.info(f"   Max Output: {self.model_capabilities.max_output_tokens:,} tokens")
            if self.model_capabilities.cost_per_input_token > 0:
                logger.info(f"   Cost: ${self.model_capabilities.cost_per_input_token:.6f}/input, ${self.model_capabilities.cost_per_output_token:.6f}/output per token")
        
    def _detect_best_anthropic_model(self) -> str:
        """Query Anthropic API to find the most advanced available model"""
        logger.info("🔍 Querying Anthropic API for available models...")
        
        try:
            import requests
            
            # Use Anthropic's models list endpoint
            headers = {
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            }
            
            response = requests.get(
                "https://api.anthropic.com/v1/models",
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                models_data = response.json()
                models = models_data.get('data', [])
                
                # Sort by created_at timestamp (newest first)
                models.sort(key=lambda x: x.get('created_at', 0), reverse=True)
                
                model_ids = [m.get('id', '') for m in models]
                logger.info(f"Available Anthropic models: {model_ids[:5]}...")  # Show first 5
                
                # Store fallback models for later use
                self._fallback_models = model_ids[:5]  # Keep top 5 for fallbacks
                
                # In fast iteration mode, prioritize speed over capability
                if self.fast_iteration_mode:
                    # Find fastest models first (Haiku > Sonnet > Opus)
                    for model_id in model_ids:
                        if 'haiku' in model_id.lower():
                            logger.info(f"🚀 Fast mode - Selected Haiku model: {model_id}")
                            return model_id
                    
                    for model_id in model_ids:
                        if 'sonnet' in model_id.lower():
                            logger.info(f"🚀 Fast mode - Selected Sonnet model: {model_id}")
                            return model_id
                
                # Find best Opus model (most advanced family)
                for model_id in model_ids:
                    if 'opus' in model_id.lower():
                        logger.info(f"✅ Selected best Opus model: {model_id}")
                        return model_id
                
                # Find best Sonnet model
                for model_id in model_ids:
                    if 'sonnet' in model_id.lower():
                        logger.info(f"✅ Selected best Sonnet model: {model_id}")
                        return model_id
                
                # Use first available (most recent)
                if model_ids:
                    selected = model_ids[0]
                    logger.info(f"✅ Using most recent model: {selected}")
                    return selected
            else:
                logger.warning(f"Models API returned {response.status_code}: {response.text}")
                
        except Exception as e:
            logger.warning(f"Anthropic model detection failed: {e}")
        
        # Fallback
        logger.info("🎯 Using fallback model for Anthropic")
        return "claude-3-opus-20240229"
        
    def _get_model_capabilities(self, model_name: str, provider: str) -> ModelCapabilities:
        """Get capabilities for the specified model dynamically"""
        
        if provider == "anthropic":
            try:
                import requests
                
                # Try to get model details from Anthropic API
                headers = {
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json"
                }
                
                response = requests.get(
                    f"https://api.anthropic.com/v1/models/{model_name}",
                    headers=headers,
                    timeout=10
                )
                
                if response.status_code == 200:
                    model_data = response.json()
                    
                    # Extract capabilities from API response
                    return ModelCapabilities(
                        max_input_tokens=model_data.get('max_input_tokens', 200000),
                        max_output_tokens=model_data.get('max_output_tokens', 4096),
                        context_window=model_data.get('context_window', 200000),
                        cost_per_input_token=model_data.get('cost_per_input_token', 0.000015),
                        cost_per_output_token=model_data.get('cost_per_output_token', 0.000075),
                        supports_system_messages=True,
                        supports_function_calling=True
                    )
                    
            except Exception as e:
                logger.debug(f"Failed to get dynamic model capabilities: {e}")
            
            # Fallback to basic capabilities based on model family
            if 'opus' in model_name.lower():
                return ModelCapabilities(
                    max_input_tokens=200000,
                    max_output_tokens=4096,
                    context_window=200000,
                    cost_per_input_token=0.000015,
                    cost_per_output_token=0.000075,
                    supports_system_messages=True,
                    supports_function_calling=True
                )
            elif 'sonnet' in model_name.lower():
                return ModelCapabilities(
                    max_input_tokens=200000,
                    max_output_tokens=8192,
                    context_window=200000,
                    cost_per_input_token=0.000003,
                    cost_per_output_token=0.000015,
                    supports_system_messages=True,
                    supports_function_calling=True
                )
            elif 'haiku' in model_name.lower():
                return ModelCapabilities(
                    max_input_tokens=200000,
                    max_output_tokens=4096,
                    context_window=200000,
                    cost_per_input_token=0.00000025,
                    cost_per_output_token=0.00000125,
                    supports_system_messages=True,
                    supports_function_calling=True
                )
            else:
                # Default Claude capabilities
                return ModelCapabilities(
                    max_input_tokens=200000,
                    max_output_tokens=4096,
                    context_window=200000,
                    cost_per_input_token=0.000015,
                    cost_per_output_token=0.000075,
                    supports_system_messages=True,
                    supports_function_calling=True
                )
            
        elif provider == "openai":
            # GPT model capabilities  
            gpt_capabilities = {
                "gpt-4-turbo": ModelCapabilities(
                    max_input_tokens=128000,
                    max_output_tokens=4096,
                    context_window=128000,
                    cost_per_input_token=0.00001,   # $10 per 1M tokens
                    cost_per_output_token=0.00003,  # $30 per 1M tokens
                    supports_system_messages=True,
                    supports_function_calling=True
                ),
                "gpt-4": ModelCapabilities(
                    max_input_tokens=8192,
                    max_output_tokens=4096,
                    context_window=8192,
                    cost_per_input_token=0.00003,   # $30 per 1M tokens
                    cost_per_output_token=0.00006,  # $60 per 1M tokens
                    supports_system_messages=True,
                    supports_function_calling=True
                ),
                "gpt-3.5-turbo": ModelCapabilities(
                    max_input_tokens=16385,
                    max_output_tokens=4096,
                    context_window=16385,
                    cost_per_input_token=0.0000005,  # $0.50 per 1M tokens
                    cost_per_output_token=0.0000015,  # $1.50 per 1M tokens
                    supports_system_messages=True,
                    supports_function_calling=True
                )
            }
            return gpt_capabilities.get(model_name, gpt_capabilities["gpt-4-turbo"])
            
        elif provider == "gemini":
            # Gemini model capabilities - use dynamic detection or fallback based on model family
            if 'pro' in model_name.lower():
                return ModelCapabilities(
                    max_input_tokens=2000000,  # 2M tokens for Pro models
                    max_output_tokens=8192,
                    context_window=2000000,
                    cost_per_input_token=0.00000125,  # $1.25 per 1M tokens
                    cost_per_output_token=0.000005,   # $5 per 1M tokens
                    supports_system_messages=True,
                    supports_function_calling=True
                )
            elif 'flash' in model_name.lower():
                return ModelCapabilities(
                    max_input_tokens=1000000,  # 1M tokens for Flash models
                    max_output_tokens=8192,
                    context_window=1000000,
                    cost_per_input_token=0.00000037,  # $0.37 per 1M tokens
                    cost_per_output_token=0.0000011,  # $1.10 per 1M tokens
                    supports_system_messages=True,
                    supports_function_calling=True
                )
            else:
                # Default Gemini capabilities
                return ModelCapabilities(
                    max_input_tokens=32000,
                    max_output_tokens=8192,
                    context_window=32000,
                    cost_per_input_token=0.0000005,
                    cost_per_output_token=0.0000015,
                    supports_system_messages=False,
                    supports_function_calling=True
                )
        
        elif provider == "bedrock":
            # AWS Bedrock model capabilities - infer from model ID
            if 'claude' in model_name.lower():
                if 'opus' in model_name.lower():
                    return ModelCapabilities(
                        max_input_tokens=200000,
                        max_output_tokens=4096,
                        context_window=200000,
                        cost_per_input_token=0.000015,  # Bedrock pricing for Claude Opus
                        cost_per_output_token=0.000075,
                        supports_system_messages=True,
                        supports_function_calling=True
                    )
                elif 'sonnet' in model_name.lower():
                    return ModelCapabilities(
                        max_input_tokens=200000,
                        max_output_tokens=8192,
                        context_window=200000,
                        cost_per_input_token=0.000003,  # Bedrock pricing for Claude Sonnet
                        cost_per_output_token=0.000015,
                        supports_system_messages=True,
                        supports_function_calling=True
                    )
                elif 'haiku' in model_name.lower():
                    return ModelCapabilities(
                        max_input_tokens=200000,
                        max_output_tokens=4096,
                        context_window=200000,
                        cost_per_input_token=0.00000025,  # Bedrock pricing for Claude Haiku
                        cost_per_output_token=0.00000125,
                        supports_system_messages=True,
                        supports_function_calling=True
                    )
            
            # Default Bedrock capabilities
            return ModelCapabilities(
                max_input_tokens=100000,
                max_output_tokens=4096,
                context_window=100000,
                cost_per_input_token=0.000003,
                cost_per_output_token=0.000015,
                supports_system_messages=True,
                supports_function_calling=True
            )
            
        else:
            # Mock or unknown provider
            return ModelCapabilities(
                max_input_tokens=100000,
                max_output_tokens=4096,
                context_window=100000,
                supports_system_messages=True,
                supports_function_calling=False
            )
    
    def _init_anthropic(self, api_key: Optional[str], model: Optional[str]):
        """Initialize Anthropic Claude client"""
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        
        if not self.api_key:
            logger.error("No Anthropic API key found. Set ANTHROPIC_API_KEY env var.")
            self.provider = LLMProvider.MOCK
            return
            
        if not ANTHROPIC_AVAILABLE:
            logger.error("Anthropic package not installed. Run: pip install anthropic")
            self.provider = LLMProvider.MOCK
            return
            
        self.client = anthropic.Anthropic(api_key=self.api_key)
        
        if model:
            self.model = model
            logger.info(f"Using specified Anthropic model: {model}")
        else:
            logger.info("🔍 Auto-detecting latest Anthropic model...")
            self.model = self._detect_best_anthropic_model()
            logger.info(f"🎯 Selected model: {self.model}")
            
        # Set model capabilities
        self.model_capabilities = self._get_model_capabilities(self.model, "anthropic")
        
    def _detect_best_openai_model(self) -> str:
        """Query OpenAI API to find the most advanced available model"""
        try:
            # Get available models from OpenAI API
            models_response = self.client.models.list()
            
            # Extract models and sort by created timestamp (newest first)
            models = [(model.id, getattr(model, 'created', 0)) for model in models_response.data]
            models.sort(key=lambda x: x[1], reverse=True)
            
            model_ids = [m[0] for m in models]
            logger.info(f"Available OpenAI models (newest first): {model_ids[:10]}...")  # Show first 10
            
            # Find the best o1 model (most advanced reasoning family)
            for model_id, _ in models:
                if model_id.startswith('o1') and 'preview' not in model_id:
                    logger.info(f"✅ Selected best o1 model: {model_id}")
                    return model_id
            
            # Find o1 preview models
            for model_id, _ in models:
                if model_id.startswith('o1'):
                    logger.info(f"✅ Selected o1 preview model: {model_id}")
                    return model_id
            
            # Find best GPT-4 model
            for model_id, _ in models:
                if model_id.startswith('gpt-4') and 'turbo' in model_id:
                    logger.info(f"✅ Selected GPT-4 Turbo model: {model_id}")
                    return model_id
            
            # Any GPT-4 model
            for model_id, _ in models:
                if model_id.startswith('gpt-4'):
                    logger.info(f"✅ Selected GPT-4 model: {model_id}")
                    return model_id
            
            # Fallback to GPT-3.5
            for model_id, _ in models:
                if model_id.startswith('gpt-3.5-turbo'):
                    logger.info(f"✅ Selected GPT-3.5 model: {model_id}")
                    return model_id
                    
            # Use first available (most recent)
            if model_ids:
                selected = model_ids[0]
                logger.info(f"✅ Using most recent model: {selected}")
                return selected
                
            # Ultimate fallback
            return "gpt-4-turbo"
            
        except Exception as e:
            logger.warning(f"OpenAI model detection failed: {e}")
            return "gpt-4-turbo"
    
    def _init_openai(self, api_key: Optional[str], model: Optional[str]):
        """Initialize OpenAI GPT client"""
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        
        if not self.api_key:
            logger.error("No OpenAI API key found. Set OPENAI_API_KEY env var.")
            self.provider = LLMProvider.MOCK
            return
            
        if not OPENAI_AVAILABLE:
            logger.error("OpenAI package not installed. Run: pip install openai")
            self.provider = LLMProvider.MOCK
            return
            
        self.client = OpenAI(api_key=self.api_key)
        
        if model:
            self.model = model
            logger.info(f"Using specified OpenAI model: {model}")
        else:
            logger.info("🔍 Auto-detecting latest OpenAI model...")
            self.model = self._detect_best_openai_model()
            logger.info(f"🎯 Selected model: {self.model}")
            
        # Set model capabilities
        self.model_capabilities = self._get_model_capabilities(self.model, "openai")
        
    def _detect_best_gemini_model(self) -> str:
        """Detect the latest and most advanced Gemini model"""
        try:
            # Get available models from Gemini API
            available_models = []
            for model in genai.list_models():
                available_models.append(model.name.replace("models/", ""))
            
            # Define model hierarchy (best to fallback)
            advanced_models = [
                # Gemini 1.5 series (latest)
                "gemini-1.5-pro-latest",
                "gemini-1.5-pro",
                "gemini-1.5-flash-latest",
                "gemini-1.5-flash",
                
                # Gemini 1.0 Pro series
                "gemini-pro",
                "gemini-1.0-pro",
            ]
            
            # Find the best available model
            for model in advanced_models:
                if model in available_models:
                    logger.info(f"✅ Detected available Gemini model: {model}")
                    return model
                    
            # Ultimate fallback
            return "gemini-pro"
            
        except Exception as e:
            logger.warning(f"Gemini model detection failed, using fallback: {e}")
            return "gemini-1.5-pro"
    
    def _init_gemini(self, api_key: Optional[str], model: Optional[str]):
        """Initialize Google Gemini client"""
        self.api_key = api_key or os.environ.get("GOOGLE_API_KEY")
        
        if not self.api_key:
            logger.error("No Google API key found. Set GOOGLE_API_KEY env var.")
            self.provider = LLMProvider.MOCK
            return
            
        if not GEMINI_AVAILABLE:
            logger.error("Google GenAI package not installed. Run: pip install google-generativeai")
            self.provider = LLMProvider.MOCK
            return
            
        genai.configure(api_key=self.api_key)
        
        if model:
            self.model = model
            logger.info(f"Using specified Gemini model: {model}")
        else:
            logger.info("🔍 Auto-detecting latest Gemini model...")
            self.model = self._detect_best_gemini_model()
            logger.info(f"🎯 Selected model: {self.model}")
            
        # Set model capabilities
        self.model_capabilities = self._get_model_capabilities(self.model, "gemini")
            
        self.client = genai.GenerativeModel(self.model)
        self.chat_session = None  # Will be initialized on first message

    def _init_bedrock(self, api_key: Optional[str], model: Optional[str]):
        """Initialize AWS Bedrock client"""
        
        if not BEDROCK_AVAILABLE:
            logger.error("Boto3 package not installed. Run: pip install boto3")
            self.provider = LLMProvider.MOCK
            return
            
        # Initialize Bedrock client
        try:
            self.client = boto3.client(
                'bedrock-runtime',
                region_name=os.environ.get('AWS_DEFAULT_REGION', 'us-east-1')
            )
        except Exception as e:
            logger.error(f"Failed to initialize Bedrock client: {e}")
            logger.error("Ensure AWS credentials are configured")
            self.provider = LLMProvider.MOCK
            return
        
        if model:
            self.model = model
            logger.info(f"Using specified Bedrock model: {model}")
        else:
            logger.info("🔍 Auto-detecting latest Bedrock model...")
            self.model = self._detect_best_bedrock_model()
            logger.info(f"🎯 Selected model: {self.model}")
            
        # Set model capabilities
        self.model_capabilities = self._get_model_capabilities(self.model, "bedrock")

    def _detect_best_bedrock_model(self) -> str:
        """Query AWS Bedrock to find the most advanced available model"""
        try:
            # Get available foundation models from Bedrock
            bedrock_client = boto3.client(
                'bedrock',
                region_name=os.environ.get('AWS_DEFAULT_REGION', 'us-east-1')
            )
            
            response = bedrock_client.list_foundation_models()
            models = response.get('modelSummaries', [])
            
            # Filter for active models and sort by model name (newer versions typically have higher numbers)
            active_models = [m for m in models if m.get('modelLifecycle', {}).get('status') == 'ACTIVE']
            active_models.sort(key=lambda x: x.get('modelName', ''), reverse=True)
            
            model_ids = [m.get('modelId', '') for m in active_models]
            logger.info(f"Available Bedrock models: {model_ids[:10]}...")  # Show first 10
            
            # Find best Claude models on Bedrock (most advanced family)
            for model_id in model_ids:
                if 'claude' in model_id.lower() and 'opus' in model_id.lower():
                    logger.info(f"✅ Selected best Claude Opus on Bedrock: {model_id}")
                    return model_id
            
            # Find Claude Sonnet models
            for model_id in model_ids:
                if 'claude' in model_id.lower() and 'sonnet' in model_id.lower():
                    logger.info(f"✅ Selected Claude Sonnet on Bedrock: {model_id}")
                    return model_id
            
            # Find any Claude model
            for model_id in model_ids:
                if 'claude' in model_id.lower():
                    logger.info(f"✅ Selected Claude model on Bedrock: {model_id}")
                    return model_id
            
            # Use first available model
            if model_ids:
                selected = model_ids[0]
                logger.info(f"✅ Using most recent Bedrock model: {selected}")
                return selected
                
        except Exception as e:
            logger.warning(f"Bedrock model detection failed: {e}")
        
        # Fallback to known Claude model
        return "anthropic.claude-3-opus-20240229-v1:0"
        
    def generate_initial_vrl(self,
                            sample_data: List[Dict[str, Any]],
                            external_configs: Dict[str, str]) -> Tuple[str, bool]:
        """
        Generate initial VRL code from samples and configs
        
        Returns:
            Tuple of (vrl_code, success)
        """
        self.iteration_count = 1
        logger.info(f"🚀 Starting VRL generation session (iteration 1)")
        
        # Build initial prompt with all context
        prompt = self._build_initial_prompt(sample_data, external_configs)
        
        # Save prompt for debugging
        self._save_conversation("user", prompt, 1)
        
        # Call LLM
        vrl_code = self._call_llm(prompt, is_initial=True)
        
        # Save response
        self._save_conversation("assistant", vrl_code, 1)
        
        return vrl_code, vrl_code != ""
        
    def iterate_with_feedback(self,
                             test_results: Dict[str, Any],
                             max_iterations: int = 5) -> Tuple[str, bool]:
        """
        Iterate VRL generation based on test feedback
        
        Args:
            test_results: Results from testing including errors
            max_iterations: Maximum iterations to attempt
            
        Returns:
            Tuple of (improved_vrl_code, success)
        """
        if self.iteration_count >= max_iterations:
            logger.warning(f"Max iterations ({max_iterations}) reached")
            return "", False
            
        self.iteration_count += 1
        logger.info(f"🔄 Iterating VRL generation (iteration {self.iteration_count})")
        
        # Build feedback prompt
        prompt = self._build_feedback_prompt(test_results)
        
        # Save prompt
        self._save_conversation("user", prompt, self.iteration_count)
        
        # Call LLM with feedback
        vrl_code = self._call_llm(prompt, is_initial=False)
        
        # Save response
        self._save_conversation("assistant", vrl_code, self.iteration_count)
        
        return vrl_code, vrl_code != ""
        
    def _get_vrl_syntax_examples(self):
        """Provide valid VRL syntax examples"""
        return """
## CRITICAL VRL SYNTAX RULES:

```vrl
# Parse JSON (MUST use ! for infallible or handle error)
.event = parse_json!(string!(.message))

# String operations (NO regex allowed!)
msg = string!(.message)
parts = split(msg, " ")
.field = parts[0] ?? "default"

# Contains check (use this instead of regex)
if contains(msg, "pattern") {
    .found = true
}

# Slice string (start, end)
.extracted = slice(msg, 0, 10) ?? ""

# Parse timestamp (use parse_timestamp!, not to_timestamp)
.ts = parse_timestamp!(parts[0], "%Y-%m-%d") ?? now()

# Type conversions
.num = to_int(parts[1]) ?? 0
.str = to_string(.field) ?? ""

# Case conversion
.upper = upcase(msg) ?? ""
.lower = downcase(msg) ?? ""
```

FORBIDDEN (will be rejected):
- parse_regex() or r"pattern" - use string ops
- match() - use contains()
- index() or index_of() - use split/slice
- to_timestamp() - use parse_timestamp!()
"""

    def _build_initial_prompt(self,
                             sample_data: List[Dict[str, Any]],
                             external_configs: Dict[str, str]) -> str:
        """Build the initial prompt with full context"""
        
        prompt_parts = []
        
        # Add external configuration rules
        if 'vector_vrl_prompt' in external_configs:
            prompt_parts.append("# VRL GENERATION RULES AND REQUIREMENTS:")
            prompt_parts.append(external_configs['vector_vrl_prompt'])
            
        if 'parser_prompts' in external_configs:
            prompt_parts.append("\n# PROJECT-SPECIFIC REQUIREMENTS:")
            prompt_parts.append(external_configs['parser_prompts'])
            
        # Analyze and add sample data
        prompt_parts.append("\n# SAMPLE LOG DATA ANALYSIS:")
        prompt_parts.append(f"Total samples: {len(sample_data)}")
        
        # Detect patterns
        patterns_found = set()
        for sample in sample_data[:10]:
            if 'message' in sample:
                msg = sample['message']
                if '%ASA-' in msg:
                    patterns_found.add('Cisco ASA')
                elif '%SEC-' in msg or '%LINK-' in msg:
                    patterns_found.add('Cisco IOS')
                elif 'devname=' in msg:
                    patterns_found.add('FortiGate')
                    
        prompt_parts.append(f"Detected patterns: {', '.join(patterns_found)}")
        
        # Add representative samples
        prompt_parts.append("\n# REPRESENTATIVE SAMPLES:")
        for i, sample in enumerate(sample_data[:5], 1):
            prompt_parts.append(f"\nSample {i}:")
            prompt_parts.append(json.dumps(sample, indent=2))
            
        # Add VRL syntax examples
        prompt_parts.append(self._get_vrl_syntax_examples())
        
        # Add specific instructions
        prompt_parts.append("\n# TASK:")
        prompt_parts.append("Generate VRL (Vector Remap Language) code to parse these log records.")
        prompt_parts.append("\n# CRITICAL REQUIREMENTS:")
        prompt_parts.append("1. NO regex, match(), or parse_regex() - they are 50-100x slower")
        prompt_parts.append("2. Use ONLY string operations: contains(), split(), slice()")
        prompt_parts.append("3. NO index() or index_of() functions - use split/slice instead")
        prompt_parts.append("4. Use parse_timestamp!() not to_timestamp()")
        prompt_parts.append("5. Use parse_json!() with ! for infallible")
        prompt_parts.append("6. Follow performance tiers: Tier 1 (300-400 events/CPU%) with string ops")
        prompt_parts.append("7. Extract fields FIRST, normalize AFTER (at the end)")
        prompt_parts.append("8. Handle errors with ?? operator")
        prompt_parts.append("9. Return ONLY valid VRL code, no explanations")
        
        return '\n'.join(prompt_parts)
        
    def _build_feedback_prompt(self, test_results: Dict[str, Any]) -> str:
        """Build iteration prompt with test feedback"""
        
        prompt_parts = []
        
        prompt_parts.append(f"# ITERATION {self.iteration_count} - TEST RESULTS:")
        
        # Add test outcome
        if test_results.get('pyvrl_valid'):
            prompt_parts.append("✅ PyVRL validation: PASSED")
        else:
            prompt_parts.append("❌ PyVRL validation: FAILED")
            
        if test_results.get('vector_valid'):
            prompt_parts.append("✅ Vector CLI test: PASSED")
        else:
            prompt_parts.append("❌ Vector CLI test: FAILED")
            
        # Add specific errors
        if test_results.get('errors'):
            prompt_parts.append("\n# ERRORS TO FIX:")
            for error in test_results['errors'][:10]:  # Limit to 10 errors
                # Clean up error messages
                if len(error) > 200:
                    error = error[:200] + "..."
                prompt_parts.append(f"- {error}")
                
        # Add performance feedback if available
        if test_results.get('events_per_cpu_percent'):
            events = test_results['events_per_cpu_percent']
            prompt_parts.append(f"\n# PERFORMANCE:")
            prompt_parts.append(f"Current: {events:.0f} events/CPU%")
            
            if events < 300:
                prompt_parts.append("⚠️ Performance too low! Need 300+ events/CPU%")
                prompt_parts.append("Remove any regex patterns and use only string operations")
                
        # Add extracted fields feedback
        if test_results.get('extracted_fields'):
            prompt_parts.append(f"\n# FIELDS EXTRACTED:")
            prompt_parts.append(f"Successfully extracted: {', '.join(test_results['extracted_fields'])}")
            
        # Request fixes
        prompt_parts.append("\n# TASK:")
        prompt_parts.append("Fix the errors above and generate improved VRL code.")
        prompt_parts.append("Remember: NO regex, only string operations!")
        prompt_parts.append("Return ONLY the complete fixed VRL code.")
        
        return '\n'.join(prompt_parts)
        
    def _call_llm(self, prompt: str, is_initial: bool = False, retry_count: int = 0, max_retries: int = 3) -> str:
        """Call the appropriate LLM API"""
        
        # Intelligent rate limiting based on provider, iteration count, and previous rate limit experience
        if not is_initial and retry_count == 0:
            # Base delay calculation: exponential backoff for iterations
            delay = min(2 + (self.iteration_count * 0.5) + (self.iteration_count ** 1.2), 12)
            
            # Different delays per provider (based on their rate limits)
            if self.provider == LLMProvider.ANTHROPIC:
                delay *= 1.0  # Anthropic has generous rate limits
            elif self.provider == LLMProvider.OPENAI:
                delay *= 1.5  # OpenAI can be more restrictive
            elif self.provider == LLMProvider.GEMINI:
                delay *= 0.8  # Gemini is usually faster
            elif self.provider == LLMProvider.BEDROCK:
                delay *= 1.2  # AWS Bedrock varies by region
            
            # Adaptive delay based on recent rate limiting
            if hasattr(self, '_last_rate_limit_time') and hasattr(self, '_rate_limit_delay'):
                time_since_limit = time.time() - self._last_rate_limit_time
                if time_since_limit < 600:  # Within 10 minutes of last rate limit
                    delay = max(delay, self._rate_limit_delay * 0.5)  # Use half of previous delay
                    logger.debug(f"Adaptive delay due to recent rate limiting: {delay:.1f}s")
            
            logger.debug(f"Adding {delay:.1f}s delay for iteration {self.iteration_count} to avoid rate limits")
            time.sleep(delay)
        
        logger.info(f"📤 Calling {self.provider.value} API")
        logger.debug(f"   Prompt length: {len(prompt)} chars")
        
        start_time = time.time()
        
        try:
            if self.provider == LLMProvider.ANTHROPIC:
                response = self._call_anthropic(prompt, is_initial)
            elif self.provider == LLMProvider.OPENAI:
                response = self._call_openai(prompt, is_initial)
            elif self.provider == LLMProvider.GEMINI:
                response = self._call_gemini(prompt, is_initial)
            else:
                response = self._generate_mock_vrl()
                
            elapsed = time.time() - start_time
            logger.info(f"📥 Response received in {elapsed:.1f}s ({len(response)} chars)")
            
            # Extract VRL code if wrapped in markdown
            response = self._extract_vrl_from_response(response)
            
            return response
            
        except Exception as e:
            error_msg = str(e)
            
            # Check for rate limit or quota error
            if any(term in error_msg.lower() for term in ['rate limit', 'too many requests', '429', 'quota', 'billing', 'usage']):
                if retry_count < max_retries:
                    # Intelligent backoff based on error type
                    if 'billing' in error_msg.lower() or 'quota' in error_msg.lower():
                        backoff_delay = 300  # 5 minutes for billing/quota issues
                        logger.error(f"💰 Billing/quota issue detected. Waiting {backoff_delay}s before retry")
                    elif '429' in error_msg or 'rate limit' in error_msg.lower():
                        backoff_delay = (2 ** retry_count) * 15  # 15s, 30s, 60s for rate limits
                        logger.warning(f"⏳ Rate limited. Retrying in {backoff_delay}s (attempt {retry_count + 1}/{max_retries})")
                    else:
                        backoff_delay = (2 ** retry_count) * 10  # 10s, 20s, 40s for other limits
                        
                    # Store rate limit info for future calls
                    self._last_rate_limit_time = time.time()
                    self._rate_limit_delay = backoff_delay
                    
                    time.sleep(backoff_delay)
                    return self._call_llm(prompt, is_initial, retry_count + 1, max_retries)
                else:
                    logger.error(f"❌ Max retries ({max_retries}) exceeded for rate limiting")
                    # Try falling back to a different model if available
                    if hasattr(self, '_fallback_models') and len(self._fallback_models) > 1:
                        original_model = self.model
                        for fallback_model in self._fallback_models[1:]:  # Skip current model
                            try:
                                logger.warning(f"🔄 Trying fallback model {fallback_model} due to rate limits")
                                self.model = fallback_model
                                return self._call_llm(prompt, is_initial, 0, max_retries)  # Reset retry count
                            except Exception:
                                continue
                        self.model = original_model  # Restore original
                    return ""
            else:
                logger.error(f"LLM API call failed: {e}")
                return ""
            
    def _call_anthropic(self, prompt: str, is_initial: bool) -> str:
        """Call Anthropic Claude API with conversation context and model fallback"""
        
        if is_initial:
            # Start new conversation
            self.conversation_history = []
            
        # Build messages including history (with compression for long conversations)
        messages = []
        
        # Compress conversation history if too long (save tokens and avoid rate limits)
        if len(self.conversation_history) > 6:  # More than 3 iterations
            # Keep first 2 exchanges and last 2 exchanges, compress middle
            compressed_history = []
            compressed_history.extend(self.conversation_history[:4])  # First 2 exchanges
            
            # Add compression summary for middle iterations
            middle_count = len(self.conversation_history) - 8
            if middle_count > 0:
                compressed_history.append({
                    "role": "user", 
                    "content": f"[Previous {middle_count//2} iterations attempted various VRL approaches with feedback]"
                })
                compressed_history.append({
                    "role": "assistant", 
                    "content": "[Previous attempts used regex/prohibited patterns, refined based on string operations feedback]"
                })
            
            compressed_history.extend(self.conversation_history[-4:])  # Last 2 exchanges
            history_to_use = compressed_history
        else:
            history_to_use = self.conversation_history
            
        for entry in history_to_use:
            messages.append({
                "role": entry["role"],
                "content": entry["content"]
            })
            
        # Add current prompt
        messages.append({
            "role": "user",
            "content": prompt
        })
        
        # Try with current model first, then dynamic fallbacks based on available models
        fallback_models = [self.model]  # Start with selected model
        
        # Add dynamic fallbacks if we have them (from model detection)
        if hasattr(self, '_fallback_models') and self._fallback_models:
            fallback_models.extend([m for m in self._fallback_models if m != self.model][:3])
        else:
            # Static fallbacks as last resort
            fallback_models.extend([
                "claude-3-5-sonnet-20240620",
                "claude-3-opus-20240229", 
                "claude-3-sonnet-20240229"
            ])
        
        for model in fallback_models:
            try:
                response = self.client.messages.create(
                    model=model,
                    max_tokens=4000,
                    temperature=0.2,
                    system="You are an expert VRL (Vector Remap Language) developer. Generate only valid VRL code. Follow performance requirements strictly.",
                    messages=messages
                )
                
                # If we had to fall back, update the stored model
                if model != self.model:
                    logger.warning(f"Fell back from {self.model} to {model}")
                    self.model = model
                
                vrl_code = response.content[0].text
                
                # Update conversation history
                self.conversation_history.append({"role": "user", "content": prompt})
                self.conversation_history.append({"role": "assistant", "content": vrl_code})
                
                return vrl_code
                
            except Exception as e:
                logger.debug(f"Model {model} failed: {e}")
                if model == fallback_models[-1]:  # Last fallback
                    raise e  # Re-raise the last error
                continue
                
        return ""  # Should never reach here
        
    def _call_openai(self, prompt: str, is_initial: bool) -> str:
        """Call OpenAI GPT API with conversation context"""
        
        if is_initial:
            self.conversation_history = []
            
        # Build messages including history
        messages = [
            {"role": "system", "content": "You are an expert VRL (Vector Remap Language) developer. Generate only valid VRL code. Follow performance requirements strictly."}
        ]
        
        for entry in self.conversation_history:
            messages.append({
                "role": entry["role"],
                "content": entry["content"]
            })
            
        messages.append({
            "role": "user",
            "content": prompt
        })
        
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.2,
            max_tokens=4000
        )
        
        vrl_code = response.choices[0].message.content
        
        # Update conversation history
        self.conversation_history.append({"role": "user", "content": prompt})
        self.conversation_history.append({"role": "assistant", "content": vrl_code})
        
        return vrl_code
        
    def _call_gemini(self, prompt: str, is_initial: bool) -> str:
        """Call Google Gemini API with conversation context"""
        
        if is_initial or not self.chat_session:
            # Start new chat session
            self.chat_session = self.client.start_chat(history=[])
            self.conversation_history = []
            
        # Send message in ongoing chat
        response = self.chat_session.send_message(prompt)
        
        vrl_code = response.text
        
        # Update conversation history
        self.conversation_history.append({"role": "user", "content": prompt})
        self.conversation_history.append({"role": "model", "content": vrl_code})
        
        return vrl_code
        
    def _generate_mock_vrl(self) -> str:
        """Generate mock VRL for testing"""
        
        if self.iteration_count == 1:
            # Initial attempt - has deliberate issues
            return """
# Mock VRL - Iteration 1
. = parse_json!(string!(.message))

if exists(.message) {
    msg = string!(.message)
    
    # This uses regex (will be rejected)
    pattern = parse_regex!(msg, r'%ASA-\\d+-\\d+')
    
    .source = "mock"
}

.
"""
        else:
            # Fixed version
            return """
# Mock VRL - Fixed
. = parse_json!(string!(.message))

if exists(.message) {
    msg = string!(.message)
    
    # Fixed: using string operations
    if contains(msg, "%ASA-") {
        .source = "cisco_asa"
    }
    
    if contains(downcase(msg), "deny") {
        .action = "deny"
    }
}

.
"""
            
    def _extract_vrl_from_response(self, response: str) -> str:
        """Extract VRL code from LLM response"""
        
        # Remove markdown code blocks
        if "```vrl" in response:
            response = response.split("```vrl")[1].split("```")[0]
        elif "```" in response:
            # Try to extract from generic code block
            parts = response.split("```")
            if len(parts) >= 3:
                response = parts[1]
                
        return response.strip()
        
    def _save_conversation(self, role: str, content: str, iteration: int):
        """Save conversation to file for debugging"""
        
        session_dir = Path(f".tmp/llm_sessions/{self.session_id}")
        session_dir.mkdir(parents=True, exist_ok=True)
        
        filename = session_dir / f"iter{iteration}_{role}.txt"
        with open(filename, 'w') as f:
            f.write(content)
            
        logger.debug(f"💾 Saved {role} message to {filename}")
        
    def get_session_summary(self) -> Dict[str, Any]:
        """Get summary of the session"""
        
        summary = {
            "session_id": self.session_id,
            "provider": self.provider.value,
            "model": self.model,
            "iterations": self.iteration_count,
            "conversation_length": len(self.conversation_history),
            "timestamp": datetime.now().isoformat()
        }
        
        # Add model capabilities for optimization reference
        if self.model_capabilities:
            summary["model_capabilities"] = {
                "max_input_tokens": self.model_capabilities.max_input_tokens,
                "max_output_tokens": self.model_capabilities.max_output_tokens,
                "context_window": self.model_capabilities.context_window,
                "cost_per_input_token": self.model_capabilities.cost_per_input_token,
                "cost_per_output_token": self.model_capabilities.cost_per_output_token,
                "supports_system_messages": self.model_capabilities.supports_system_messages,
                "supports_function_calling": self.model_capabilities.supports_function_calling
            }
            
        return summary
    
    def get_optimization_info(self) -> Dict[str, Any]:
        """Get key information for prompt and context optimization"""
        if not self.model_capabilities:
            return {}
            
        return {
            "model_name": getattr(self, 'model', 'unknown'),
            "provider": self.provider.value,
            "max_context_tokens": self.model_capabilities.context_window,
            "max_input_tokens": self.model_capabilities.max_input_tokens,
            "max_output_tokens": self.model_capabilities.max_output_tokens,
            "cost_per_input_token": self.model_capabilities.cost_per_input_token,
            "cost_per_output_token": self.model_capabilities.cost_per_output_token,
            "recommended_input_limit": int(self.model_capabilities.max_input_tokens * 0.8),  # 80% of max for safety
            "supports_system_messages": self.model_capabilities.supports_system_messages,
            "supports_function_calling": self.model_capabilities.supports_function_calling,
            "total_cost_estimate": self._estimate_session_cost()
        }
    
    def _estimate_session_cost(self) -> float:
        """Estimate total cost of the current session"""
        if not self.model_capabilities or self.model_capabilities.cost_per_input_token == 0:
            return 0.0
            
        # Rough estimate based on conversation history
        total_input_tokens = 0
        total_output_tokens = 0
        
        for entry in self.conversation_history:
            content_length = len(entry["content"])
            # Rough token estimation: ~4 chars per token
            tokens = content_length // 4
            
            if entry["role"] == "user":
                total_input_tokens += tokens
            else:
                total_output_tokens += tokens
                
        input_cost = total_input_tokens * self.model_capabilities.cost_per_input_token
        output_cost = total_output_tokens * self.model_capabilities.cost_per_output_token
        
        return input_cost + output_cost


if __name__ == "__main__":
    print("=" * 70)
    print("ITERATIVE LLM SESSION MANAGER")
    print("=" * 70)
    print("\nSupported LLM Providers:")
    print("✅ Anthropic Claude (claude-3-opus, sonnet, haiku)")
    print("✅ OpenAI GPT (gpt-4-turbo, gpt-4, gpt-3.5-turbo)")
    print("✅ Google Gemini (gemini-pro)")
    print("\nFeatures:")
    print("- Maintains conversation context across iterations")
    print("- Passes test results back for improvement")
    print("- Automatic error analysis and fixing")
    print("- Performance feedback integration")
    print("\nEnvironment Variables:")
    print("- ANTHROPIC_API_KEY for Claude")
    print("- OPENAI_API_KEY for GPT")
    print("- GOOGLE_API_KEY for Gemini")
    print("=" * 70)