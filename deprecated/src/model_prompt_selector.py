#!/usr/bin/env python3
"""
Model-Specific Prompt Selector

Loads and manages model-specific VRL generation prompts and hints.
Different models need different guidance for VRL syntax.
"""

import os
from pathlib import Path
from typing import Dict, Optional
from loguru import logger


class ModelPromptSelector:
    """Select and load model-specific prompts"""
    
    def __init__(self, base_dir: str = "external"):
        self.base_dir = Path(base_dir)
        self.model_specific_dir = self.base_dir / "model-specific"
        self.cache = {}
        
    def get_model_specific_hints(self, provider: str, model: str) -> Optional[str]:
        """
        Get model-specific VRL hints
        
        Args:
            provider: LLM provider (anthropic, openai, google)
            model: Model name
            
        Returns:
            Model-specific hints or None
        """
        # Determine which hint file to use
        hint_file = self._determine_hint_file(provider, model)
        
        if not hint_file:
            return None
            
        # Check cache
        if hint_file in self.cache:
            return self.cache[hint_file]
            
        # Load from file
        hint_path = self.model_specific_dir / hint_file
        if hint_path.exists():
            hints = hint_path.read_text()
            self.cache[hint_file] = hints
            logger.info(f"📚 Loaded model-specific hints: {hint_file}")
            return hints
        else:
            logger.debug(f"No model-specific hints found: {hint_path}")
            return None
    
    def _determine_hint_file(self, provider: str, model: str) -> Optional[str]:
        """Determine which hint file to use based on provider and model"""
        
        provider = provider.lower()
        model = model.lower()
        
        # Claude models
        if provider == 'anthropic' or 'claude' in model:
            if 'opus' in model or '4-1' in model or '4.1' in model:
                return "claude-opus-vrl-hints.md"
            elif 'sonnet' in model:
                return "claude-sonnet-vrl-hints.md"
            elif 'haiku' in model:
                return "claude-haiku-vrl-hints.md"
        
        # OpenAI models
        elif provider == 'openai' or 'gpt' in model:
            return "gpt-vrl-hints.md"
        
        # Google models
        elif provider == 'google' or 'gemini' in model:
            return "gemini-vrl-hints.md"
        
        # Bedrock models
        elif provider == 'bedrock':
            if 'claude' in model:
                return self._determine_hint_file('anthropic', model)
            elif 'titan' in model:
                return "titan-vrl-hints.md"
        
        return None
    
    def build_complete_prompt(self, provider: str, model: str) -> str:
        """
        Build complete VRL prompt using core + model overlay approach
        
        Args:
            provider: LLM provider
            model: Model name
            
        Returns:
            Complete prompt with core rules + model-specific overlay
        """
        # Load core prompt (universal rules)
        core_path = self.base_dir / "vrl-core-prompt.md"
        if core_path.exists():
            core_prompt = core_path.read_text()
        else:
            logger.error(f"Core prompt not found: {core_path}")
            return ""
        
        # Load model overlay
        overlay = self.get_model_overlay(provider, model)
        
        if overlay:
            complete_prompt = f"""
{core_prompt}

{overlay}

CRITICAL REMINDER: The model-specific overlay above addresses YOUR known weaknesses.
Review your VRL code against these specific points before finalizing.
"""
            logger.info(f"✨ Built complete prompt: core + {self._determine_overlay_file(provider, model)}")
        else:
            complete_prompt = core_prompt
            logger.info("📝 Using core prompt only (no overlay found)")
        
        return complete_prompt
    
    def get_model_overlay(self, provider: str, model: str) -> Optional[str]:
        """Get model-specific overlay content"""
        overlay_file = self._determine_overlay_file(provider, model)
        
        if not overlay_file:
            return None
            
        # Check cache
        if overlay_file in self.cache:
            return self.cache[overlay_file]
            
        # Load from file
        overlay_path = self.base_dir / "model-overlays" / overlay_file
        if overlay_path.exists():
            overlay = overlay_path.read_text()
            self.cache[overlay_file] = overlay
            logger.debug(f"📚 Loaded model overlay: {overlay_file}")
            return overlay
        
        return None
    
    def _determine_overlay_file(self, provider: str, model: str) -> Optional[str]:
        """Determine which overlay file to use"""
        provider = provider.lower()
        model = model.lower()
        
        # Claude models
        if provider == 'anthropic' or 'claude' in model:
            if 'opus' in model or '4-1' in model or '4.1' in model:
                return "claude-opus-overlay.md"
            elif 'sonnet' in model:
                return "claude-sonnet-overlay.md"
            elif 'haiku' in model:
                return "claude-haiku-overlay.md"
        
        # OpenAI models  
        elif provider == 'openai' or 'gpt' in model:
            return "gpt-overlay.md"
        
        # Google models
        elif provider == 'google' or 'gemini' in model:
            return "gemini-overlay.md"
        
        return None
    
    def get_iteration_hints(self, errors: list, provider: str, model: str) -> str:
        """
        Get model-specific hints for iteration based on errors
        
        Args:
            errors: List of current errors
            provider: LLM provider
            model: Model name
            
        Returns:
            Targeted hints for fixing the errors
        """
        model_lower = model.lower()
        
        # Claude Opus specific
        if 'opus' in model_lower:
            if any('E103' in str(e) for e in errors):
                return """
CRITICAL FIX REQUIRED:
You forgot the ! operator on fallible functions. 
Add ! to ALL of these: split!, parse_json!, to_int!, to_float!, contains!
Example: parts = split!(msg, " ") NOT split(msg, " ")
"""
            if any('Identifier' in str(e) and 'integer literal' in str(e) for e in errors):
                return """
CRITICAL FIX REQUIRED:
VRL does NOT support variable array indexing like array[variable].
Use ONLY literal integers: array[0], array[1], etc.
For dynamic access, use conditionals.
"""
        
        # Claude Sonnet specific
        elif 'sonnet' in model_lower:
            if any('E651' in str(e) for e in errors):
                return """
FIX: Remove ?? operator after infallible functions.
If you use !, you don't need ??.
Example: value = to_int!(str) NOT to_int!(str) ?? 0
"""
        
        # GPT specific
        elif 'gpt' in provider.lower() or 'gpt' in model_lower:
            if any('str(' in str(e) or 'int(' in str(e) for e in errors):
                return """
FIX: Use VRL functions, not Python builtins!
- str() → to_string!()
- int() → to_int!()
- .split() → split!()
- .lower() → downcase!()
"""
        
        # Generic fallback
        return """
FIX: Ensure all fallible functions use ! operator.
Common ones: split!, parse_json!, to_int!, to_float!
"""


def load_model_specific_config(provider: str, model: str) -> Dict:
    """
    Load complete model-specific configuration
    
    Returns dict with:
    - hints: Model-specific VRL hints
    - common_errors: List of common errors for this model
    - fix_patterns: Patterns to fix automatically
    - cost: Cost per token for this model
    """
    config = {
        'provider': provider,
        'model': model,
        'hints': None,
        'common_errors': [],
        'fix_patterns': [],
        'cost': {'input': 0.00001, 'output': 0.00005}  # defaults
    }
    
    selector = ModelPromptSelector()
    config['hints'] = selector.get_model_specific_hints(provider, model)
    
    # Model-specific error patterns
    if 'opus' in model.lower():
        config['common_errors'] = [
            'E103: unhandled fallible assignment',
            'E203: unexpected Identifier for array index',
            'Empty return statements'
        ]
        config['fix_patterns'] = [
            ('split(', 'split!('),
            ('parse_json(', 'parse_json!('),
            ('to_int(', 'to_int!('),
        ]
        config['cost'] = {'input': 0.000015, 'output': 0.000075}
        
    elif 'sonnet' in model.lower():
        config['common_errors'] = [
            'E651: unnecessary error coalescing',
            'E103: occasional fallible issues'
        ]
        config['cost'] = {'input': 0.000003, 'output': 0.000015}
        
    elif 'gpt' in model.lower():
        config['common_errors'] = [
            'Python-like syntax',
            'Method calls instead of functions',
            'Wrong function names'
        ]
        config['fix_patterns'] = [
            ('str(', 'to_string!('),
            ('int(', 'to_int!('),
            ('.split(', 'split!('),
            ('.lower()', 'downcase!()'),
        ]
        
    return config