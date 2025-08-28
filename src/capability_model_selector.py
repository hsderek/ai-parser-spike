#!/usr/bin/env python3
"""
Capability-Based Model Selector
- Groups models by REASONING/BALANCED/EFFICIENT capabilities
- Auto-detects latest model versions
- No hardcoded versions
"""

import re
from typing import List, Optional, Dict, Any, Tuple
from pathlib import Path
import yaml
from loguru import logger
import litellm


class CapabilityModelSelector:
    """
    Model selection based on platform and capability requirements
    Always selects the latest available version automatically
    """
    
    def __init__(self, config_path: str = None):
        self.config = self._load_config(config_path)
        self._model_cache = {}  # Cache discovered models
        self._tested_models = set()  # Track tested models to avoid retesting
    
    def _load_config(self, config_path: str = None) -> Dict[str, Any]:
        """Load capability-based configuration"""
        try:
            if not config_path:
                config_path = Path(__file__).parent.parent / "config" / "model_capabilities.yaml"
            
            if Path(config_path).exists():
                with open(config_path, 'r') as f:
                    return yaml.safe_load(f)
            else:
                logger.warning("Config file not found, using minimal defaults")
                return self._get_minimal_config()
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            return self._get_minimal_config()
    
    def _get_minimal_config(self) -> Dict[str, Any]:
        """Minimal config if file not found"""
        return {
            "defaults": {
                "platform": "anthropic",
                "capability": "reasoning"
            },
            "platforms": {
                "anthropic": {
                    "capabilities": {
                        "reasoning": {"families": ["opus", "sonnet"]},
                        "balanced": {"families": ["sonnet", "haiku"]},
                        "efficient": {"families": ["haiku", "sonnet"]}
                    }
                }
            }
        }
    
    def select_model(self, 
                    platform: str = None,
                    capability: str = None,
                    specific_model: str = None,
                    use_case: str = None) -> Tuple[Optional[str], Dict[str, Any]]:
        """
        Select the best available model based on capability requirements
        
        Args:
            platform: Platform name (anthropic, openai, google, etc.)
            capability: REASONING, BALANCED, or EFFICIENT
            specific_model: Specific model if user provided one
            use_case: Optional use case to determine capability
            
        Returns:
            Tuple of (model_string, metadata_dict)
        """
        metadata = {
            "platform": None,
            "capability": None,
            "family": None,
            "selection_method": None
        }
        
        # If specific model provided, try to use it or find closest match
        if specific_model:
            model = self._handle_specific_model(specific_model)
            if model:
                metadata["selection_method"] = "specific_model"
                metadata["family"] = self._extract_family(model)
                metadata["platform"] = self._extract_platform(model)
            return model, metadata
        
        # Determine capability from use case if provided
        if use_case and not capability:
            capability = self._get_capability_for_use_case(use_case)
            metadata["use_case"] = use_case
        
        # Use defaults if not specified
        defaults = self.config.get("defaults", {})
        platform = platform or defaults.get("platform", "anthropic")
        capability = capability or defaults.get("capability", "reasoning")
        
        # Normalize capability
        capability = capability.lower()
        metadata["platform"] = platform
        metadata["capability"] = capability
        
        logger.info(f"🎯 Selecting {capability.upper()} model for {platform}")
        
        # Get families for platform/capability combination
        families = self._get_families_for_capability(platform, capability)
        
        if not families:
            logger.warning(f"No configuration for {platform}/{capability}")
            return None, metadata
        
        # Try each family in priority order
        for family_name in families:
            model = self._find_latest_model_in_family(platform, family_name)
            if model:
                logger.info(f"✅ Selected {capability.upper()} model: {model}")
                metadata["family"] = family_name
                metadata["selection_method"] = "capability_based"
                return model, metadata
        
        logger.warning(f"❌ No models found for {platform}/{capability}")
        return None, metadata
    
    def _get_capability_for_use_case(self, use_case: str) -> str:
        """Map use case to capability preference"""
        use_cases = self.config.get("use_cases", {})
        use_case_config = use_cases.get(use_case, {})
        return use_case_config.get("capability", "balanced")
    
    def _get_families_for_capability(self, platform: str, capability: str) -> List[str]:
        """Get family priority list for platform/capability"""
        platforms = self.config.get("platforms", {})
        platform_config = platforms.get(platform, {})
        capabilities = platform_config.get("capabilities", {})
        capability_config = capabilities.get(capability, {})
        return capability_config.get("families", [])
    
    def _handle_specific_model(self, specific_model: str) -> Optional[str]:
        """Handle when user provides a specific model"""
        # First try exact match
        if self._is_model_available(specific_model):
            logger.info(f"✅ Using specific model: {specific_model}")
            return specific_model
        
        logger.warning(f"⚠️ Specific model {specific_model} not available")
        
        # Extract family and find alternative
        family = self._extract_family(specific_model)
        platform = self._extract_platform(specific_model)
        
        if family:
            logger.info(f"🔍 Looking for alternative {family} model...")
            alternative = self._find_latest_model_in_family(platform, family)
            if alternative:
                logger.info(f"✅ Found alternative: {alternative}")
                return alternative
        
        logger.warning(f"❌ No alternative found for {specific_model}")
        return None
    
    def _find_latest_model_in_family(self, platform: str, family: str) -> Optional[str]:
        """Find the latest available model in a family"""
        # Get all available models
        available_models = self._get_available_models()
        
        # Filter for platform and family
        family_models = []
        for model in available_models:
            if self._model_matches_family(model, platform, family):
                family_models.append(model)
        
        if not family_models:
            return None
        
        # Sort to get latest version
        sorted_models = self._sort_models_by_version(family_models)
        
        # Test availability starting from latest
        for model in sorted_models:
            if self._is_model_available(model):
                return self._format_model_name(model, platform)
        
        return None
    
    def _get_available_models(self) -> List[str]:
        """Get all available models from LiteLLM"""
        if not self._model_cache:
            try:
                # Try to get from LiteLLM's model list
                self._model_cache = litellm.model_list or []
                
                # If empty, try common models
                if not self._model_cache:
                    self._model_cache = self._get_common_models()
                
                logger.debug(f"Discovered {len(self._model_cache)} models")
            except Exception as e:
                logger.error(f"Failed to get model list: {e}")
                self._model_cache = self._get_common_models()
        
        return self._model_cache
    
    def _get_common_models(self) -> List[str]:
        """Common models as fallback"""
        return [
            # Anthropic
            "claude-opus-4-1-20250805",
            "claude-sonnet-4-20250514", 
            "claude-haiku-3-5",
            "claude-opus-3",
            "claude-sonnet-3-7",
            "claude-sonnet-3-5",
            
            # OpenAI - GPT-5 family first (best coding)
            "gpt-5",
            "gpt-5-mini",
            "gpt-5-nano",
            "gpt-4.1",
            "gpt-4.1-mini",
            "gpt-4o",
            "gpt-4",
            "gpt-3.5-turbo",
            "o3",
            "o3-mini", 
            "o4-mini",
            "o1-preview",
            
            # Google
            "gemini-2.0-flash-exp",
            "gemini-1.5-pro",
            "gemini-1.5-flash",
            
            # DeepSeek
            "deepseek-chat",
            "deepseek-coder"
        ]
    
    def _model_matches_family(self, model: str, platform: str, family: str) -> bool:
        """Check if a model belongs to a platform/family"""
        model_lower = model.lower()
        platform_lower = platform.lower()
        family_lower = family.lower()
        
        # Platform check
        platform_match = False
        if platform_lower == "anthropic":
            platform_match = "claude" in model_lower
        elif platform_lower == "openai":
            platform_match = any(x in model_lower for x in ["gpt", "o1", "o3", "o4"])
        elif platform_lower == "google":
            platform_match = "gemini" in model_lower
        elif platform_lower == "deepseek":
            platform_match = "deepseek" in model_lower
        else:
            platform_match = platform_lower in model_lower
        
        if not platform_match:
            return False
        
        # Family check - exact match for compound names
        # Handle GPT-5 variants carefully
        if family_lower == "gpt-5" and "gpt-5" in model_lower:
            # Don't match gpt-5-mini or gpt-5-nano with base gpt-5
            return not any(x in model_lower for x in ["gpt-5-mini", "gpt-5-nano"])
        elif family_lower in ["gpt-5-mini", "gpt-5-nano", "gpt-4.1", "gpt-4.1-mini", "o4-mini", "o3-mini"]:
            return family_lower in model_lower
        elif family_lower.startswith("gpt") or family_lower.startswith("o"):
            return family_lower in model_lower
        else:
            return family_lower in model_lower
    
    def _sort_models_by_version(self, models: List[str]) -> List[str]:
        """Sort models by version (latest first)"""
        def extract_version(model: str) -> tuple:
            # Look for version patterns
            # Dates: 20250805
            date_match = re.search(r'(\d{8})', model)
            if date_match:
                return (int(date_match.group(1)),)
            
            # Version numbers: 4.1, 3.5, etc
            numbers = re.findall(r'(\d+)\.?(\d*)', model)
            if numbers:
                version_parts = []
                for major, minor in numbers[:2]:  # Look at first 2 version parts
                    version_parts.append(int(major))
                    if minor:
                        version_parts.append(int(minor))
                return tuple(version_parts) if version_parts else (0,)
            
            return (0,)
        
        return sorted(models, key=extract_version, reverse=True)
    
    def _is_model_available(self, model: str) -> bool:
        """Test if a model is actually available"""
        # Don't retest models we've already checked
        if model in self._tested_models:
            return False
        
        self._tested_models.add(model)
        
        try:
            # Quick test with minimal API call
            response = litellm.completion(
                model=model,
                messages=[{"role": "user", "content": "test"}],
                max_tokens=1,
                temperature=0
            )
            return True
        except Exception as e:
            error_str = str(e).lower()
            # Only consider it unavailable for specific errors
            if any(x in error_str for x in ["not found", "invalid", "not available", "access denied"]):
                return False
            # Other errors might be rate limits, API key issues, etc.
            # Consider available but may fail later
            return True
    
    def _format_model_name(self, model: str, platform: str) -> str:
        """Format model name for LiteLLM usage"""
        # Clean up various prefixes
        model = model.replace("openrouter/", "")
        model = model.replace("anthropic/", "")
        
        # Add platform prefix if needed for Anthropic
        if platform.lower() == "anthropic" and not model.startswith("anthropic/"):
            return f"anthropic/{model}"
        
        return model
    
    def _extract_family(self, model: str) -> Optional[str]:
        """Extract family from model name"""
        model_lower = model.lower()
        
        # Check for specific model patterns (order matters for compound names)
        families = [
            "gpt-5-nano", "gpt-5-mini", "gpt-5",  # GPT-5 family (check variants first)
            "gpt-4.1-mini", "gpt-4.1", "gpt-4-mini", "gpt-4",  # GPT-4 family
            "gpt-3.5",  # GPT-3.5
            "o4-mini", "o4", "o3-mini", "o3", "o1",  # O-series
            "opus", "sonnet", "haiku",  # Anthropic
            "gemini-ultra", "gemini-pro", "gemini-flash", "gemini-nano",  # Google
            "deepseek-v3", "deepseek-r1", "deepseek-v2", "deepseek-coder",  # DeepSeek
        ]
        
        for family in families:
            if family in model_lower:
                return family
        
        return None
    
    def _extract_platform(self, model: str) -> str:
        """Extract platform from model name"""
        model_lower = model.lower()
        
        if "claude" in model_lower:
            return "anthropic"
        elif any(x in model_lower for x in ["gpt", "o1", "o3"]):
            return "openai"
        elif "gemini" in model_lower:
            return "google"
        elif "deepseek" in model_lower:
            return "deepseek"
        
        return "anthropic"  # Default


def demonstrate_selection():
    """Demonstrate capability-based model selection"""
    selector = CapabilityModelSelector()
    
    print("=" * 80)
    print("🧪 CAPABILITY-BASED MODEL SELECTION DEMONSTRATION")
    print("=" * 80)
    
    # Test cases for each platform and capability
    test_cases = [
        # Anthropic tests
        ("anthropic", "reasoning", "Anthropic REASONING"),
        ("anthropic", "balanced", "Anthropic BALANCED"),
        ("anthropic", "efficient", "Anthropic EFFICIENT"),
        
        # OpenAI tests  
        ("openai", "reasoning", "OpenAI REASONING"),
        ("openai", "balanced", "OpenAI BALANCED"),
        ("openai", "efficient", "OpenAI EFFICIENT"),
        
        # Google tests
        ("google", "reasoning", "Google REASONING"),
        ("google", "balanced", "Google BALANCED"),
        ("google", "efficient", "Google EFFICIENT"),
    ]
    
    for platform, capability, label in test_cases:
        print(f"\n{label}:")
        print("-" * 40)
        
        model, metadata = selector.select_model(
            platform=platform,
            capability=capability
        )
        
        if model:
            print(f"✅ Selected: {model}")
            print(f"   Family: {metadata.get('family', 'unknown')}")
            print(f"   Method: {metadata.get('selection_method', 'unknown')}")
        else:
            print(f"❌ No model found")
    
    # Test defaults
    print("\n" + "=" * 80)
    print("DEFAULT SELECTION (no parameters):")
    print("-" * 40)
    model, metadata = selector.select_model()
    if model:
        print(f"✅ Selected: {model}")
        print(f"   Platform: {metadata.get('platform', 'unknown')}")
        print(f"   Capability: {metadata.get('capability', 'unknown')}")
        print(f"   Family: {metadata.get('family', 'unknown')}")
    
    # Test use case
    print("\n" + "=" * 80)
    print("USE CASE SELECTION (vrl_generation):")
    print("-" * 40)
    model, metadata = selector.select_model(use_case="vrl_generation")
    if model:
        print(f"✅ Selected: {model}")
        print(f"   Use Case: {metadata.get('use_case', 'none')}")
        print(f"   Capability: {metadata.get('capability', 'unknown')}")
        print(f"   Family: {metadata.get('family', 'unknown')}")
    
    # Test specific model with fallback
    print("\n" + "=" * 80)
    print("SPECIFIC MODEL WITH FALLBACK:")
    print("-" * 40)
    model, metadata = selector.select_model(specific_model="claude-opus-99-future")
    if model:
        print(f"✅ Selected: {model}")
        print(f"   Method: {metadata.get('selection_method', 'unknown')}")
        print(f"   Family: {metadata.get('family', 'unknown')}")


if __name__ == "__main__":
    demonstrate_selection()