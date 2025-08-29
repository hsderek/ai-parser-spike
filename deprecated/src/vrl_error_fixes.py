#!/usr/bin/env python3
"""
VRL Error Code Based Fixer Factory
Clean architecture organized by Vector VRL error codes
"""

import re
from abc import ABC, abstractmethod
from typing import Tuple, List, Dict, Any, Optional
from loguru import logger


class VRLErrorFix(ABC):
    """Base class for VRL error code fixes"""
    
    def __init__(self, error_code: str, description: str):
        self.error_code = error_code
        self.description = description
        
    @abstractmethod
    def can_fix(self, code: str, errors: List[str]) -> bool:
        """Check if this fix can handle the given errors"""
        pass
    
    @abstractmethod
    def apply_fix(self, code: str, errors: List[str]) -> Tuple[str, List[str]]:
        """Apply the fix and return (fixed_code, list_of_applied_fixes)"""
        pass


class E103_UnhandledFallibleFix(VRLErrorFix):
    """Fix E103: unhandled fallible assignment"""
    
    def __init__(self):
        super().__init__("E103", "unhandled fallible assignment - function can fail but no error handling")
        
    def can_fix(self, code: str, errors: List[str]) -> bool:
        return any('E103' in str(e) or 'unhandled fallible' in str(e) for e in errors)
    
    def apply_fix(self, code: str, errors: List[str]) -> Tuple[str, List[str]]:
        fixes = []
        
        # Map of functions that need ! to be infallible
        fallible_functions = {
            'split', 'parse_json', 'parse_regex', 'parse_timestamp',
            'to_int', 'to_float', 'to_bool', 'to_string',
            'find', 'match', 'strip_whitespace', 'replace'
        }
        
        for func in fallible_functions:
            # Pattern: function( without preceding !
            pattern = rf'(?<![!])\b{func}\('
            if re.search(pattern, code):
                code = re.sub(pattern, f'{func}!(', code)
                fixes.append(f"Made {func}() infallible with !")
        
        return code, fixes


class E110_FalliblePredicateFix(VRLErrorFix):
    """Fix E110: fallible predicate - variable might be null in if condition"""
    
    def __init__(self):
        super().__init__("E110", "fallible predicate - variable can be null")
    
    def can_fix(self, code: str, errors: List[str]) -> bool:
        return any('E110' in str(e) or 'fallible predicate' in str(e) for e in errors)
    
    def apply_fix(self, code: str, errors: List[str]) -> Tuple[str, List[str]]:
        fixes = []
        
        # Common pattern: if contains(nullable_var, "pattern")
        # Fix: if exists(.field) && contains(string!(.field), "pattern")
        
        # Find variables mentioned in E110 errors
        for error in errors:
            if 'fallible predicate' in str(error):
                # Extract variable patterns from error
                var_match = re.search(r'this expression resolves to.*`(\w+)`', str(error))
                if var_match:
                    var_name = var_match.group(1)
                    
                    # Fix contains() with potentially null variable
                    pattern = rf'if\s+contains\({var_name},'
                    if re.search(pattern, code):
                        # Add exists check and string coercion
                        replacement = rf'if exists({var_name}) && contains(string!({var_name}),'
                        code = re.sub(pattern, replacement, code)
                        fixes.append(f"Added exists() check and string coercion for {var_name}")
        
        return code, fixes


class E105_UndefinedFunctionFix(VRLErrorFix):
    """Fix E105: call to undefined function"""
    
    def __init__(self):
        super().__init__("E105", "call to undefined function - function doesn't exist in VRL")
    
    def can_fix(self, code: str, errors: List[str]) -> bool:
        return any('E105' in str(e) or 'call to undefined function' in str(e) for e in errors)
    
    def apply_fix(self, code: str, errors: List[str]) -> Tuple[str, List[str]]:
        fixes = []
        
        # Common function name corrections (LLMs invent these)
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
            'trim': 'strip_whitespace',  # trim doesn't exist, strip_whitespace does
        }
        
        for wrong_func, correct_func in function_corrections.items():
            if wrong_func in code:
                code = code.replace(wrong_func, correct_func)
                fixes.append(f"Replaced {wrong_func} with {correct_func}")
        
        # Extract specific undefined functions from errors
        for error in errors:
            if 'undefined function' in str(error):
                func_match = re.search(r'undefined function\s+"([^"]+)"', str(error))
                if func_match:
                    undefined_func = func_match.group(1)
                    
                    # Map to correct VRL function based on name patterns
                    if 'string' in undefined_func.lower():
                        code = code.replace(f'{undefined_func}(', 'string!(')
                        fixes.append(f"Mapped {undefined_func} to string!()")
                    elif 'int' in undefined_func.lower():
                        code = code.replace(f'{undefined_func}(', 'to_int!(')
                        fixes.append(f"Mapped {undefined_func} to to_int!()")
                    elif 'float' in undefined_func.lower():
                        code = code.replace(f'{undefined_func}(', 'to_float!(')
                        fixes.append(f"Mapped {undefined_func} to to_float!()")
        
        return code, fixes


class E620_InfallibleAbortFix(VRLErrorFix):
    """Fix E620: can't abort infallible function"""
    
    def __init__(self):
        super().__init__("E620", "can't abort infallible function - ! operator on function that never fails")
    
    def can_fix(self, code: str, errors: List[str]) -> bool:
        return any('E620' in str(e) or "can't abort infallible" in str(e) for e in errors)
    
    def apply_fix(self, code: str, errors: List[str]) -> Tuple[str, List[str]]:
        fixes = []
        
        # Functions that are infallible when given proper string inputs
        infallible_functions = {
            'contains', 'starts_with', 'ends_with', 
            'length', 'downcase', 'upcase', 'trim'
        }
        
        for error in errors:
            if "can't abort infallible" in str(error):
                # Extract function name from error
                for func in infallible_functions:
                    if f'{func}!' in str(error):
                        # Remove ! from this function
                        pattern = rf'\b{func}!\('
                        replacement = f'{func}('
                        if re.search(pattern, code):
                            code = re.sub(pattern, replacement, code)
                            fixes.append(f"Removed ! from infallible function {func}()")
                            break
        
        return code, fixes


class E651_UnnecessaryCoalescingFix(VRLErrorFix):
    """Fix E651: unnecessary error coalescing operation"""
    
    def __init__(self):
        super().__init__("E651", "unnecessary error coalescing - ?? operator after expression that can't fail")
    
    def can_fix(self, code: str, errors: List[str]) -> bool:
        return any('E651' in str(e) or 'unnecessary error coalescing' in str(e) for e in errors)
    
    def apply_fix(self, code: str, errors: List[str]) -> Tuple[str, List[str]]:
        fixes = []
        
        # Pattern 1: downcase(string!(...)) ?? fallback
        # This is the most common Claude Opus error
        pattern1 = r'(\w+\(string!\([^)]+\)\))\s*\?\?\s*[\w.]+'
        if re.search(pattern1, code):
            code = re.sub(pattern1, r'\1', code)
            fixes.append("Removed ?? from infallible nested function call")
            
        # Pattern 2: any_function!(something) ?? fallback  
        pattern2 = r'(\w+!\([^)]*\))\s*\?\?\s*[\w.]+'
        if re.search(pattern2, code):
            code = re.sub(pattern2, r'\1', code)
            fixes.append("Removed ?? from infallible function call")
        
        # Pattern 3: infallible_function(fallible_function!(...)) ?? fallback
        pattern3 = r'((?:downcase|upcase|length|trim|contains)\([^)]*string!\([^)]+\)[^)]*\))\s*\?\?\s*[\w.]+'
        if re.search(pattern3, code):
            code = re.sub(pattern3, r'\1', code)
            fixes.append("Removed ?? from nested infallible operation")
            
        # Pattern 4: anything ?? null (often unnecessary)
        pattern4 = r'(\w+!\([^)]*\))\s*\?\?\s*null'
        if re.search(pattern4, code):
            code = re.sub(pattern4, r'\1', code)
            fixes.append("Removed ?? null from infallible operation")
        
        return code, fixes


class E203_SyntaxErrorFix(VRLErrorFix):
    """Fix E203: syntax error - basic VRL syntax issues"""
    
    def __init__(self):
        super().__init__("E203", "syntax error - invalid VRL syntax")
    
    def can_fix(self, code: str, errors: List[str]) -> bool:
        return any('E203' in str(e) or 'syntax error' in str(e) for e in errors)
    
    def apply_fix(self, code: str, errors: List[str]) -> Tuple[str, List[str]]:
        fixes = []
        
        # Fix 1: Empty return statements (VRL is expression-based)
        if re.search(r'^\s*return\s*$', code, re.MULTILINE):
            code = re.sub(r'^\s*return\s*$', '', code, flags=re.MULTILINE)
            fixes.append("Removed empty return statements")
        
        # Fix 2: Variable array indexing (not allowed in VRL)
        # Pattern: array[variable] -> conditional access
        if 'expected one of: "integer literal"' in str(errors):
            pattern = r'(\w+)\[(\w+)\]'
            matches = re.findall(pattern, code)
            for array_name, index_var in matches:
                # Replace with conditional access
                replacement = f'''if {index_var} == 0 {{
    {array_name}[0]
}} else if {index_var} == 1 {{
    {array_name}[1]
}} else {{
    null
}}'''
                code = code.replace(f'{array_name}[{index_var}]', replacement)
                fixes.append(f"Fixed dynamic array access {array_name}[{index_var}]")
        
        return code, fixes


class VRLErrorFixFactory:
    """Factory for VRL error fixes organized by error code"""
    
    def __init__(self):
        self.fixes = {
            'E103': E103_UnhandledFallibleFix(),
            'E105': E105_UndefinedFunctionFix(), 
            'E110': E110_FalliblePredicateFix(),
            'E203': E203_SyntaxErrorFix(),
            'E620': E620_InfallibleAbortFix(),
            'E651': E651_UnnecessaryCoalescingFix(),
        }
        
    def get_applicable_fixes(self, code: str, errors: List[str]) -> List[VRLErrorFix]:
        """Get all fixes that can handle the given errors"""
        applicable = []
        
        for fix in self.fixes.values():
            if fix.can_fix(code, errors):
                applicable.append(fix)
                
        return applicable
    
    def apply_all_fixes(self, code: str, errors: List[str]) -> Tuple[str, List[str], Dict[str, Any]]:
        """Apply all applicable fixes to the code"""
        original_code = code
        all_fixes = []
        error_codes_fixed = []
        
        applicable_fixes = self.get_applicable_fixes(code, errors)
        
        logger.info(f"🔧 Found {len(applicable_fixes)} applicable fixes for error codes: {[f.error_code for f in applicable_fixes]}")
        
        for fix in applicable_fixes:
            try:
                code, fixes_applied = fix.apply_fix(code, errors)
                if fixes_applied:
                    all_fixes.extend(fixes_applied)
                    error_codes_fixed.append(fix.error_code)
                    logger.debug(f"  ✅ {fix.error_code}: {fix.description}")
                    for applied_fix in fixes_applied:
                        logger.debug(f"    - {applied_fix}")
            except Exception as e:
                logger.warning(f"⚠️ Failed to apply {fix.error_code} fix: {e}")
        
        was_fixed = code != original_code
        
        metadata = {
            'error_codes_fixed': error_codes_fixed,
            'total_fixes': len(all_fixes),
            'original_length': len(original_code),
            'fixed_length': len(code),
            'was_modified': was_fixed
        }
        
        if was_fixed:
            logger.success(f"🎯 Applied {len(all_fixes)} fixes for error codes: {error_codes_fixed}")
        
        return code, all_fixes, metadata


# Factory instance for easy import
vrl_error_fixer = VRLErrorFixFactory()


def fix_vrl_errors(code: str, errors: List[str]) -> Tuple[str, List[str], Dict[str, Any]]:
    """
    Main entry point for VRL error fixing
    
    Args:
        code: VRL code to fix
        errors: List of error messages from PyVRL or Vector
        
    Returns:
        Tuple of (fixed_code, list_of_applied_fixes, metadata)
    """
    return vrl_error_fixer.apply_all_fixes(code, errors)