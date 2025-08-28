#!/usr/bin/env python3
"""
Model-Specific VRL Syntax Fixer

Different LLM models have different patterns of VRL syntax errors.
This module provides model-specific fixes to address each model's weaknesses.
Uses the new factory-based error code system.
"""

import re
from typing import Tuple, List, Dict, Any, Optional
from loguru import logger
from vrl_error_fixes import fix_vrl_errors


class ModelSpecificVRLFixer:
    """Base class for model-specific VRL fixers"""
    
    def __init__(self, model_name: str):
        self.model_name = model_name
        self.fixes_applied = []
        
    def fix(self, vrl_code: str, errors: List[str]) -> Tuple[str, bool, Dict[str, Any]]:
        """Apply model-specific fixes"""
        raise NotImplementedError("Subclasses must implement fix()")
    
    def _make_functions_infallible(self, code: str, functions: List[str]) -> str:
        """Convert fallible functions to infallible with ! operator"""
        for func in functions:
            # Pattern: func( without preceding !
            pattern = rf'(?<![!])\b{func}\('
            replacement = f'{func}!('
            code = re.sub(pattern, replacement, code)
        return code


class ClaudeOpusFixer(ModelSpecificVRLFixer):
    """Fixer for Claude Opus models (4.1, 3.5, 3.0)"""
    
    def __init__(self):
        super().__init__("Claude Opus")
        
    def fix(self, vrl_code: str, errors: List[str]) -> Tuple[str, bool, Dict[str, Any]]:
        """
        Claude Opus specific fixes using factory-based error code system:
        - Consistently forgets ! operator for fallible functions (E103)
        - Invents non-existent functions (E105)  
        - Uses unnecessary error coalescing (E651)
        - Adds ! to infallible functions (E620)
        """
        original_code = vrl_code
        
        # Apply universal error-code-based fixes
        fixed_code, fixes_applied, fix_metadata = fix_vrl_errors(vrl_code, errors)
        
        # Claude Opus specific additional fixes
        additional_fixes = []
        
        # Claude-specific pattern: Often uses imperative loops (not VRL!)
        if 'for ' in fixed_code or 'while ' in fixed_code:
            # Remove any attempted loop constructs
            fixed_code = re.sub(r'\bfor\s+\w+\s+in\s+[^{]+\{[^}]*\}', '# Removed invalid for loop', fixed_code)
            fixed_code = re.sub(r'\bwhile\s+[^{]+\{[^}]*\}', '# Removed invalid while loop', fixed_code)
            if 'for ' not in fixed_code and 'while ' not in fixed_code:
                additional_fixes.append("Removed invalid imperative loop constructs")
        
        # Claude-specific: Sometimes uses return statements (VRL is expression-based)
        if re.search(r'^\s*return\b', fixed_code, re.MULTILINE):
            fixed_code = re.sub(r'^\s*return\s*;?\s*$', '', fixed_code, flags=re.MULTILINE)
            additional_fixes.append("Removed invalid return statements")
        
        was_fixed = fixed_code != original_code
        all_fixes = fixes_applied + additional_fixes
        
        metadata = {
            'model': self.model_name,
            'fixes_applied': all_fixes,
            'error_codes_fixed': fix_metadata.get('error_codes_fixed', []),
            'cost_saved': 0.50 if was_fixed else 0.0,
            'universal_fixes': len(fixes_applied),
            'claude_specific_fixes': len(additional_fixes)
        }
        
        if was_fixed:
            logger.info(f"🎯 Claude Opus: Applied {len(all_fixes)} total fixes ({len(fixes_applied)} universal + {len(additional_fixes)} Claude-specific)")
            if fix_metadata.get('error_codes_fixed'):
                logger.info(f"   Error codes fixed: {fix_metadata['error_codes_fixed']}")
        
        return fixed_code, was_fixed, metadata
    
    def _add_string_coercion(self, code: str, errors: List[str]) -> str:
        """Add string!() wrapper for variables used in string operations"""
        # Find variables mentioned in errors
        for error in errors:
            # Extract variable name from error
            var_match = re.search(r'`(\w+)` argument type is `string or null`', str(error))
            if var_match:
                var_name = var_match.group(1)
                # Wrap variable with string!() in function calls
                pattern = rf'(\w+!?\([^)]*){var_name}([^)]*\))'
                replacement = rf'\1string!({var_name})\2'
                code = re.sub(pattern, replacement, code)
        return code
    
    def _remove_unnecessary_abort(self, code: str, errors: List[str]) -> Tuple[str, bool]:
        """Remove ! from infallible functions (E620 errors)"""
        fixed = False
        
        # Functions that are infallible and don't need !
        infallible_funcs = [
            'contains',  # contains!(str, pattern) is always infallible when args are strings
            'starts_with', 'ends_with',
            'length', 'downcase', 'upcase',
            'trim', 'strip_whitespace'
        ]
        
        # Extract specific function from error
        for error in errors:
            if 'can\'t abort infallible' in str(error):
                # Look for function name in error
                for func in infallible_funcs:
                    if f'{func}!' in str(error):
                        # Remove ! from this function
                        pattern = rf'\b{func}!\('
                        replacement = f'{func}('
                        if pattern in code:
                            code = re.sub(pattern, replacement, code)
                            fixed = True
                            break
        
        # Also check for split! with simple string patterns (infallible)
        if 'split!' in code and 'can\'t abort infallible' in str(errors):
            # split! is infallible when splitting by simple string literals
            # Pattern: split!(variable, "literal_string")
            pattern = r'split!\(([^,]+),\s*"([^"]+)"\)'
            if re.search(pattern, code):
                code = re.sub(pattern, r'split(\1, "\2")', code)
                fixed = True
                
            # Also handle single quotes
            pattern2 = r"split!\(([^,]+),\s*'([^']+)'\)"
            if re.search(pattern2, code):
                code = re.sub(pattern2, r"split(\1, '\2')", code)
                fixed = True
        
        return code, fixed
    
    def _fix_undefined_functions(self, code: str, errors: List[str]) -> Tuple[str, bool]:
        """Fix undefined function calls (E105 errors)"""
        fixed = False
        
        # Common function name corrections Claude makes up
        function_corrections = {
            'string_fast!': 'string!',
            'string_low_cardinality!': 'string!', 
            'string_medium_cardinality!': 'string!',
            'string_high_cardinality!': 'string!',
            'text_search!': 'string!',
            'int32!': 'to_int!',
            'int64!': 'to_int!',
            'float32!': 'to_float!',
            'float64!': 'to_float!',
            'timestamp_iso8601!': 'parse_timestamp!',
            'ip_address!': 'string!',
            'hostname!': 'string!',
            'url!': 'string!',
        }
        
        for wrong_func, correct_func in function_corrections.items():
            if wrong_func in code:
                code = code.replace(wrong_func, correct_func)
                fixed = True
        
        # Also check errors for specific function names
        for error in errors:
            if 'undefined function' in str(error):
                # Extract function name from error  
                import re
                func_match = re.search(r'undefined function\s+"([^"]+)"', str(error))
                if func_match:
                    undefined_func = func_match.group(1)
                    # Map to correct VRL function
                    if 'string' in undefined_func:
                        code = code.replace(f'{undefined_func}(', 'string!(')
                        code = code.replace(f'{undefined_func}!', 'string!')
                        fixed = True
                    elif 'int' in undefined_func:
                        code = code.replace(f'{undefined_func}(', 'to_int!(')
                        code = code.replace(f'{undefined_func}!', 'to_int!')
                        fixed = True
                    elif 'float' in undefined_func:
                        code = code.replace(f'{undefined_func}(', 'to_float!(')
                        code = code.replace(f'{undefined_func}!', 'to_float!')
                        fixed = True
        
        return code, fixed
    
    def _remove_unnecessary_coalescing(self, code: str, errors: List[str]) -> Tuple[str, bool]:
        """Remove ?? from infallible operations (E651 errors)"""
        fixed = False
        
        # Fix the specific pattern: downcase(string!(...)) ?? field
        # This is the most common E651 error from Claude Opus
        pattern1 = r'(\w+\(string!\([^)]+\)\))\s*\?\?\s*[\w.]+'
        if re.search(pattern1, code):
            code = re.sub(pattern1, r'\1', code)
            fixed = True
            
        # Pattern: any_function!(something) ?? fallback  
        pattern2 = r'(\w+!\([^)]*\))\s*\?\?\s*[\w.]+'
        if re.search(pattern2, code):
            code = re.sub(pattern2, r'\1', code)
            fixed = True
        
        # Pattern: infallible_function(fallible_function!(...)) ?? fallback
        # Example: downcase(string!(.field)) ?? .field
        pattern3 = r'((?:downcase|upcase|length|trim|contains)\([^)]*string!\([^)]+\)[^)]*\))\s*\?\?\s*[\w.]+'
        if re.search(pattern3, code):
            code = re.sub(pattern3, r'\1', code)
            fixed = True
            
        # Also handle ?? null specifically 
        pattern4 = r'(\w+!\([^)]*\))\s*\?\?\s*null'
        if re.search(pattern4, code):
            code = re.sub(pattern4, r'\1', code)
            fixed = True
            
        # Handle nested infallible operations with ?? 
        pattern5 = r'(\w+\([^)]*string!\([^)]+\)[^)]*\))\s*\?\?\s*null'
        if re.search(pattern5, code):
            code = re.sub(pattern5, r'\1', code)
            fixed = True
        
        return code, fixed
    
    def _fix_dynamic_array_access(self, code: str, errors: List[str]) -> str:
        """Replace dynamic array access with conditional logic"""
        # Find array[variable] patterns
        pattern = r'(\w+)\[(\w+_(?:index|idx|i|pos|position))\]'
        
        def replace_dynamic_access(match):
            array_name = match.group(1)
            index_var = match.group(2)
            
            # Generate conditional access
            return f"""if {index_var} == 0 {{
                {array_name}[0]
            }} else if {index_var} == 1 {{
                {array_name}[1]
            }} else {{
                null
            }}"""
        
        code = re.sub(pattern, replace_dynamic_access, code)
        return code


class ClaudeSonnetFixer(ModelSpecificVRLFixer):
    """Fixer for Claude Sonnet models"""
    
    def __init__(self):
        super().__init__("Claude Sonnet")
        
    def fix(self, vrl_code: str, errors: List[str]) -> Tuple[str, bool, Dict[str, Any]]:
        """
        Claude Sonnet specific fixes:
        - Similar to Opus but slightly better with ! operators
        - Sometimes adds unnecessary error handling
        """
        original_code = vrl_code
        fixes = []
        
        # Sonnet is better but still forgets ! sometimes
        if any('E103' in str(e) for e in errors):
            # More targeted fix - only functions mentioned in errors
            for error in errors:
                func_match = re.search(r'`(\w+)\(', str(error))
                if func_match:
                    func = func_match.group(1)
                    pattern = rf'(?<![!])\b{func}\('
                    if re.search(pattern, vrl_code):
                        vrl_code = re.sub(pattern, f'{func}!(', vrl_code)
                        fixes.append(f"Made {func}() infallible")
        
        # Sonnet sometimes adds unnecessary ?? operators
        if 'E651' in str(errors):
            # Remove ?? from infallible operations
            vrl_code = re.sub(r'(\w+!\([^)]*\))\s*\?\?\s*[^,\n;]+', r'\1', vrl_code)
            fixes.append("Removed unnecessary ?? operators")
        
        was_fixed = vrl_code != original_code
        
        metadata = {
            'model': self.model_name,
            'fixes_applied': fixes,
            'cost_saved': 0.30 if was_fixed else 0.0  # Sonnet is cheaper
        }
        
        return vrl_code, was_fixed, metadata


class GPTFixer(ModelSpecificVRLFixer):
    """Fixer for OpenAI GPT models"""
    
    def __init__(self, version: str = "4"):
        super().__init__(f"GPT-{version}")
        self.version = version
        
    def fix(self, vrl_code: str, errors: List[str]) -> Tuple[str, bool, Dict[str, Any]]:
        """
        GPT specific fixes:
        - Often uses wrong function names
        - May use Python-like syntax
        - Forgets VRL-specific constraints
        """
        original_code = vrl_code
        fixes = []
        
        # GPT often uses Python-like syntax
        # Fix: str() instead of to_string()
        if 'str(' in vrl_code:
            vrl_code = vrl_code.replace('str(', 'to_string!(')
            fixes.append("Fixed Python-like str() to to_string!()")
        
        # Fix: int() instead of to_int()
        if 'int(' in vrl_code:
            vrl_code = vrl_code.replace('int(', 'to_int!(')
            fixes.append("Fixed Python-like int() to to_int!()")
        
        # GPT sometimes uses .split() method syntax
        if '.split(' in vrl_code:
            # Convert method syntax to function syntax
            pattern = r'(\w+)\.split\(([^)]+)\)'
            replacement = r'split!(\1, \2)'
            vrl_code = re.sub(pattern, replacement, vrl_code)
            fixes.append("Fixed method syntax .split() to split!()")
        
        # Standard E103 fixes
        if any('E103' in str(e) for e in errors):
            fallible_funcs = ['split', 'parse_json', 'to_int', 'to_float']
            vrl_code = self._make_functions_infallible(vrl_code, fallible_funcs)
            fixes.append("Made fallible functions infallible")
        
        was_fixed = vrl_code != original_code
        
        metadata = {
            'model': self.model_name,
            'fixes_applied': fixes,
            'cost_saved': 0.20 if was_fixed else 0.0  # GPT is cheaper
        }
        
        return vrl_code, was_fixed, metadata


class GeminiFixer(ModelSpecificVRLFixer):
    """Fixer for Google Gemini models"""
    
    def __init__(self):
        super().__init__("Gemini")
        
    def fix(self, vrl_code: str, errors: List[str]) -> Tuple[str, bool, Dict[str, Any]]:
        """
        Gemini specific fixes:
        - May use JavaScript-like syntax
        - Different error patterns than Claude
        """
        original_code = vrl_code
        fixes = []
        
        # Gemini might use JS-like syntax
        if 'substring(' in vrl_code:
            vrl_code = vrl_code.replace('substring(', 'slice!(')
            fixes.append("Fixed JS-like substring() to slice!()")
        
        # Standard fallible fixes
        if any('E103' in str(e) for e in errors):
            vrl_code = self._make_functions_infallible(vrl_code, 
                ['split', 'parse_json', 'to_int', 'slice'])
            fixes.append("Made fallible functions infallible")
        
        was_fixed = vrl_code != original_code
        
        metadata = {
            'model': self.model_name,
            'fixes_applied': fixes,
            'cost_saved': 0.10 if was_fixed else 0.0  # Gemini is cheapest
        }
        
        return vrl_code, was_fixed, metadata


def get_model_specific_fixer(model_info: Dict[str, Any]) -> ModelSpecificVRLFixer:
    """
    Get the appropriate fixer based on model information
    
    Args:
        model_info: Dict with 'provider' and 'model' keys
        
    Returns:
        Appropriate ModelSpecificVRLFixer instance
    """
    provider = model_info.get('provider', '').lower()
    model = model_info.get('model', '').lower()
    
    # Claude models
    if provider == 'anthropic' or 'claude' in model:
        if 'opus' in model or '4-1' in model or '4.1' in model:
            logger.debug("Using Claude Opus fixer")
            return ClaudeOpusFixer()
        elif 'sonnet' in model or '3-5' in model or '3.5' in model:
            logger.debug("Using Claude Sonnet fixer")
            return ClaudeSonnetFixer()
        else:
            # Default to Opus fixer for unknown Claude models
            logger.debug("Using Claude Opus fixer (default)")
            return ClaudeOpusFixer()
    
    # OpenAI models
    elif provider == 'openai' or 'gpt' in model:
        if 'gpt-4' in model or 'gpt4' in model:
            logger.debug("Using GPT-4 fixer")
            return GPTFixer("4")
        elif 'gpt-5' in model or 'gpt5' in model:
            logger.debug("Using GPT-5 fixer")
            return GPTFixer("5")
        else:
            logger.debug("Using GPT-4 fixer (default)")
            return GPTFixer("4")
    
    # Google models
    elif provider == 'google' or 'gemini' in model:
        logger.debug("Using Gemini fixer")
        return GeminiFixer()
    
    # Default to Claude Opus fixer (most comprehensive)
    else:
        logger.debug(f"Unknown model {model}, using Claude Opus fixer")
        return ClaudeOpusFixer()


def apply_model_specific_fixes(vrl_code: str, errors: List[str], 
                               model_info: Dict[str, Any]) -> Tuple[str, bool, Dict[str, Any]]:
    """
    Main entry point for model-specific VRL fixing
    
    Args:
        vrl_code: The VRL code to fix
        errors: List of error messages
        model_info: Information about the model that generated the code
        
    Returns:
        Tuple of (fixed_code, was_fixed, metadata)
    """
    fixer = get_model_specific_fixer(model_info)
    
    logger.info(f"🔧 Applying {fixer.model_name} specific fixes...")
    
    return fixer.fix(vrl_code, errors)