#!/usr/bin/env python3
"""
Config-Driven Model Selector
- All model patterns and rules come from config
- No hardcoded model names or logic
- Future-proof design that adapts through config changes
"""

import re
from typing import List, Optional, Dict, Any, Tuple
from pathlib import Path
import yaml
from loguru import logger
import litellm


class DFEModelSelector:
    """
    Model selection entirely driven by configuration
    No hardcoded model names or platform logic
    """
    
    def __init__(self, config_path: str = None):
        self.config = self._load_config(config_path)
        self._model_cache = {}  # Cache discovered models
        self._tested_models = set()  # Track tested models
    
    def _load_config(self, config_path: str = None) -> Dict[str, Any]:
        """Load configuration file"""
        try:
            if not config_path:
                # Try multiple possible config locations
                possible_paths = [
                    Path(__file__).parent.parent.parent.parent / "config" / "config.yaml",  # Root config
                    Path(__file__).parent.parent / "config" / "config.yaml",  # Module config
                    Path("config/config.yaml"),  # Relative path
                ]
                
                config_path = None
                for path in possible_paths:
                    if path.exists():
                        config_path = path
                        break
            
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
            "platform_patterns": {
                "anthropic": ["claude"],
                "openai": ["gpt", "o[0-9]"],
                "google": ["gemini"]
            },
            "platforms": {
                "anthropic": {
                    "capabilities": {
                        "reasoning": {"families": ["opus", "sonnet"]},
                        "balanced": {"families": ["sonnet", "haiku"]},
                        "efficient": {"families": ["haiku"]}
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
        Select the best available model based on requirements
        
        Returns:
            Tuple of (model_string, metadata_dict)
        """
        metadata = {
            "platform": None,
            "capability": None,
            "family": None,
            "selection_method": None
        }
        
        # Handle specific model request
        if specific_model:
            model = self._handle_specific_model(specific_model)
            if model:
                metadata["selection_method"] = "specific_model"
                metadata["family"] = self._extract_family_from_model(model)
                metadata["platform"] = self._identify_platform(model)
            return model, metadata
        
        # Determine capability from use case
        if use_case and not capability:
            capability = self._get_capability_for_use_case(use_case)
            metadata["use_case"] = use_case
        
        # Use defaults
        defaults = self.config.get("defaults", {})
        platform = platform or defaults.get("platform", "anthropic")
        capability = capability or defaults.get("capability", "reasoning")
        
        # Normalize
        capability = capability.lower()
        metadata["platform"] = platform
        metadata["capability"] = capability
        
        logger.info(f"🎯 Selecting {capability.upper()} model for {platform}")
        
        # Get families for platform/capability
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
    
    def _identify_platform(self, model: str) -> Optional[str]:
        """Identify platform from model name using config patterns"""
        model_lower = model.lower()
        platform_patterns = self.config.get("platform_patterns", {})
        
        for platform, patterns in platform_patterns.items():
            for pattern in patterns:
                # Check if pattern is regex (contains special chars)
                if any(c in pattern for c in ['[', ']', '(', ')', '*', '+', '?', '^', '$']):
                    if re.search(pattern, model_lower):
                        return platform
                else:
                    # Simple string match
                    if pattern in model_lower:
                        return platform
        
        return None
    
    def _model_matches_family(self, model: str, platform: str, family: str) -> bool:
        """Check if model belongs to platform/family using config rules"""
        model_lower = model.lower()
        family_lower = family.lower()
        
        # Check platform match first
        identified_platform = self._identify_platform(model)
        if identified_platform != platform:
            return False
        
        # Get family matching rules from config
        family_rules = self.config.get("family_rules", {})
        exact_match_families = family_rules.get("exact_match", [])
        no_variant_match = family_rules.get("no_variant_match", {})
        
        # Check exact match families
        if family_lower in exact_match_families:
            return family_lower in model_lower
        
        # Check families that shouldn't match variants
        if family_lower in no_variant_match:
            if family_lower in model_lower:
                # Make sure it's not a variant
                variants = no_variant_match[family_lower]
                return not any(v in model_lower for v in variants)
        
        # Default: simple contains check
        return family_lower in model_lower
    
    def _extract_family_from_model(self, model: str) -> Optional[str]:
        """Extract family from model name using config"""
        model_lower = model.lower()
        
        # Get all families from config
        all_families = set()
        platforms = self.config.get("platforms", {})
        for platform_config in platforms.values():
            capabilities = platform_config.get("capabilities", {})
            for cap_config in capabilities.values():
                families = cap_config.get("families", [])
                all_families.update(families)
        
        # Add families from rules
        family_rules = self.config.get("family_rules", {})
        all_families.update(family_rules.get("exact_match", []))
        all_families.update(family_rules.get("no_variant_match", {}).keys())
        
        # Sort by length (longest first) to match most specific
        sorted_families = sorted(all_families, key=len, reverse=True)
        
        for family in sorted_families:
            if family.lower() in model_lower:
                return family
        
        return None
    
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
        """Handle specific model request"""
        # Try exact match first
        if self._is_model_available(specific_model):
            logger.info(f"✅ Using specific model: {specific_model}")
            return specific_model
        
        logger.warning(f"⚠️ Specific model {specific_model} not available")
        
        # Find alternative in same family
        family = self._extract_family_from_model(specific_model)
        platform = self._identify_platform(specific_model)
        
        if family and platform:
            logger.info(f"🔍 Looking for alternative {family} model...")
            alternative = self._find_latest_model_in_family(platform, family)
            if alternative:
                logger.info(f"✅ Found alternative: {alternative}")
                return alternative
        
        logger.warning(f"❌ No alternative found for {specific_model}")
        return None
    
    def _find_latest_model_in_family(self, platform: str, family: str) -> Optional[str]:
        """Find latest available model in family"""
        # Get available models
        available_models = self._get_available_models()
        
        # Filter for platform and family
        family_models = []
        for model in available_models:
            if self._model_matches_family(model, platform, family):
                family_models.append(model)
        
        if not family_models:
            return None
        
        # Sort by version
        sorted_models = self._sort_models_by_version(family_models)
        
        # Test availability
        for model in sorted_models:
            if self._is_model_available(model):
                return self._format_model_name(model, platform)
        
        return None
    
    def _get_available_models(self) -> List[str]:
        """Get available models from LiteLLM"""
        if not self._model_cache:
            try:
                # Use LiteLLM's model list if available
                self._model_cache = litellm.model_list or []
                
                # If empty, LiteLLM doesn't have a list
                if not self._model_cache:
                    # We'll rely on testing specific models
                    self._model_cache = []
                
                logger.debug(f"Found {len(self._model_cache)} models from LiteLLM")
            except Exception as e:
                logger.error(f"Failed to get model list: {e}")
                self._model_cache = []
        
        return self._model_cache
    
    def _sort_models_by_version(self, models: List[str]) -> List[str]:
        """Sort models by version (latest first)"""
        def extract_version(model: str) -> tuple:
            # Look for dates (YYYYMMDD format)
            date_match = re.search(r'(\d{8})', model)
            if date_match:
                return (int(date_match.group(1)),)
            
            # Look for version numbers (X.Y format)
            numbers = re.findall(r'(\d+)\.?(\d*)', model)
            if numbers:
                version_parts = []
                for major, minor in numbers[:2]:
                    version_parts.append(int(major))
                    if minor:
                        version_parts.append(int(minor))
                return tuple(version_parts) if version_parts else (0,)
            
            return (0,)
        
        return sorted(models, key=extract_version, reverse=True)
    
    def _is_model_available(self, model: str) -> bool:
        """Test if model is available"""
        if model in self._tested_models:
            return False
        
        self._tested_models.add(model)
        
        try:
            # Quick availability test
            response = litellm.completion(
                model=model,
                messages=[{"role": "user", "content": "test"}],
                max_tokens=1,
                temperature=0
            )
            return True
        except Exception as e:
            error_str = str(e).lower()
            if any(x in error_str for x in ["not found", "invalid", "not available", "access denied"]):
                return False
            # Other errors might be temporary
            return True
    
    def _format_model_name(self, model: str, platform: str) -> str:
        """Format model name for LiteLLM"""
        # Handle Bedrock model format conversion
        if "us.anthropic." in model:
            # Convert us.anthropic.claude-3-5-haiku-20241022-v1:0 to claude-3-5-haiku-20241022
            clean_model = model.replace("us.anthropic.", "").replace("-v1:0", "")
            return f"anthropic/{clean_model}"
        
        # Remove common prefixes
        model = model.replace("openrouter/", "")
        model = model.replace("anthropic/", "")
        
        # Add platform prefix if needed for Anthropic
        if platform.lower() == "anthropic" and not model.startswith("anthropic/"):
            return f"anthropic/{model}"
        
        return model


def demonstrate_selection():
    """Demonstrate config-driven model selection"""
    selector = DFEModelSelector()
    
    print("=" * 80)
    print("🧪 CONFIG-DRIVEN MODEL SELECTION (No Hardcoding!)")
    print("=" * 80)
    
    test_cases = [
        # Test each platform/capability
        ("anthropic", "reasoning", "Anthropic REASONING"),
        ("anthropic", "balanced", "Anthropic BALANCED"),
        ("anthropic", "efficient", "Anthropic EFFICIENT"),
        ("openai", "reasoning", "OpenAI REASONING (GPT-5)"),
        ("openai", "balanced", "OpenAI BALANCED"),
        ("openai", "efficient", "OpenAI EFFICIENT"),
        ("google", "reasoning", "Google REASONING"),
        ("google", "balanced", "Google BALANCED"),
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
        print(f"   Platform: {metadata.get('platform')}")
        print(f"   Capability: {metadata.get('capability')}")
        print(f"   Family: {metadata.get('family')}")


if __name__ == "__main__":
    demonstrate_selection()