#!/usr/bin/env python3
"""
Simple Model Selector
- Auto-detects latest model versions
- Works with model families (opus, sonnet, haiku)
- No hardcoded versions
"""

import re
from typing import List, Optional, Dict, Any
from pathlib import Path
import yaml
from loguru import logger
import litellm


class SimpleModelSelector:
    """
    Simple model selection based on families, not versions
    Always selects the latest available version automatically
    """
    
    def __init__(self):
        self.config = self._load_config()
        self._model_cache = {}  # Cache discovered models
    
    def _load_config(self) -> Dict[str, Any]:
        """Load simple priority configuration"""
        try:
            config_path = Path(__file__).parent.parent / "config" / "model_priorities.yaml"
            if config_path.exists():
                with open(config_path, 'r') as f:
                    return yaml.safe_load(f)
            else:
                # Minimal default if no config
                return {
                    "model_priorities": {
                        "anthropic": {
                            "families": ["opus", "sonnet", "haiku"]
                        }
                    },
                    "default_platform": "anthropic",
                    "default_family": "sonnet"
                }
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            return {"default_platform": "anthropic", "default_family": "sonnet"}
    
    def select_model(self, 
                    platform: str = None,
                    family: str = None,
                    specific_model: str = None) -> Optional[str]:
        """
        Select the best available model
        
        Args:
            platform: Platform name (anthropic, openai, etc.)
            family: Model family (opus, sonnet, haiku, etc.)
            specific_model: Specific model if user provided one
            
        Returns:
            Best available model string for LiteLLM
        """
        # If specific model provided, try to use it or find closest match
        if specific_model:
            return self._handle_specific_model(specific_model)
        
        # Use defaults if not specified
        platform = platform or self.config.get("default_platform", "anthropic")
        
        # Get family priorities for platform
        platform_config = self.config.get("model_priorities", {}).get(platform, {})
        families_to_try = platform_config.get("families", [])
        
        # If family specified, prioritize it
        if family and family in families_to_try:
            families_to_try = [family] + [f for f in families_to_try if f != family]
        elif family:
            # Family not in config, try it anyway
            families_to_try = [family] + families_to_try
        
        # Try each family in priority order
        for family_name in families_to_try:
            model = self._find_latest_model_in_family(platform, family_name)
            if model:
                logger.info(f"✅ Selected {platform}/{family_name}: {model}")
                return model
        
        logger.warning(f"⚠️ No models found for {platform}")
        return None
    
    def _handle_specific_model(self, specific_model: str) -> Optional[str]:
        """
        Handle when user provides a specific model
        If exact match not available, find closest in same family
        """
        # First try exact match
        if self._is_model_available(specific_model):
            logger.info(f"✅ Using specific model: {specific_model}")
            return specific_model
        
        logger.warning(f"⚠️ Specific model {specific_model} not available")
        
        # Extract family from model name
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
        """
        Find the latest available model in a family
        NO VERSION HARDCODING - discovers from API
        """
        # Get all available models
        available_models = self._get_available_models()
        
        # Filter for platform and family
        family_models = []
        for model in available_models:
            if self._model_matches_family(model, platform, family):
                family_models.append(model)
        
        if not family_models:
            return None
        
        # Sort to get latest version (highest version numbers/dates first)
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
                self._model_cache = litellm.model_list
                logger.debug(f"Discovered {len(self._model_cache)} models from LiteLLM")
            except Exception as e:
                logger.error(f"Failed to get model list: {e}")
                self._model_cache = []
        return self._model_cache
    
    def _model_matches_family(self, model: str, platform: str, family: str) -> bool:
        """Check if a model belongs to a platform/family"""
        model_lower = model.lower()
        platform_lower = platform.lower()
        family_lower = family.lower()
        
        # Platform check (handle various formats)
        platform_match = (
            platform_lower in model_lower or
            (platform_lower == "anthropic" and "claude" in model_lower) or
            (platform_lower == "openai" and any(x in model_lower for x in ["gpt", "o1", "o3"]))
        )
        
        if not platform_match:
            return False
        
        # Family check
        return family_lower in model_lower
    
    def _sort_models_by_version(self, models: List[str]) -> List[str]:
        """
        Sort models by version (latest first)
        Handles various version formats: 4.1, 3.5, dates, etc.
        """
        def extract_version(model: str) -> tuple:
            # Extract version numbers and dates
            numbers = re.findall(r'\d+\.?\d*', model)
            if not numbers:
                return (0,)  # No version found
            
            # Convert to tuple of floats for comparison
            version_parts = []
            for num in numbers[:3]:  # Look at first 3 numbers max
                try:
                    version_parts.append(float(num))
                except ValueError:
                    pass
            
            return tuple(version_parts) if version_parts else (0,)
        
        # Sort by version descending (latest first)
        return sorted(models, key=extract_version, reverse=True)
    
    def _is_model_available(self, model: str) -> bool:
        """Test if a model is actually available"""
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
            # Other errors (rate limits, etc.) don't mean unavailable
            return True
    
    def _format_model_name(self, model: str, platform: str) -> str:
        """Format model name for LiteLLM usage"""
        # Clean up various prefixes
        model = model.replace("openrouter/", "")
        model = model.replace("anthropic/", "")
        
        # Add platform prefix if needed
        if platform.lower() == "anthropic" and not model.startswith("anthropic/"):
            return f"anthropic/{model}"
        
        return model
    
    def _extract_family(self, model: str) -> Optional[str]:
        """Extract family from model name (opus, sonnet, haiku, etc.)"""
        model_lower = model.lower()
        
        # Common families
        families = ["opus", "sonnet", "haiku", "gpt", "gemini", "deepseek", "o1", "o3"]
        
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


# Global instance
model_selector = SimpleModelSelector()


def select_best_model(platform: str = None, 
                      family: str = None,
                      specific_model: str = None) -> Optional[str]:
    """
    Simple function interface for model selection
    
    Examples:
        select_best_model()  # Uses defaults
        select_best_model(family="opus")  # Get latest opus
        select_best_model(platform="anthropic", family="sonnet")  # Latest anthropic sonnet
        select_best_model(specific_model="claude-sonnet-4-20250514")  # Try specific or fallback
    """
    return model_selector.select_model(platform, family, specific_model)


if __name__ == "__main__":
    # Test the selector
    print("🧪 Testing Simple Model Selector")
    print()
    
    # Test default selection
    model = select_best_model()
    print(f"Default selection: {model}")
    
    # Test family selection
    model = select_best_model(family="opus")
    print(f"Opus family: {model}")
    
    model = select_best_model(family="sonnet")
    print(f"Sonnet family: {model}")
    
    # Test specific model with fallback
    model = select_best_model(specific_model="claude-sonnet-4-20250514")
    print(f"Specific model: {model}")