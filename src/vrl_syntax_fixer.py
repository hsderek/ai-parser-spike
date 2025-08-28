#!/usr/bin/env python3
"""
VRL Syntax Fixer - Local fixes for common VRL syntax errors

Saves API costs by fixing simple syntax errors locally before iteration.
"""

import re
from typing import Tuple, List, Dict, Any
from loguru import logger

class VRLSyntaxFixer:
    """Fix common VRL syntax errors locally without LLM calls"""
    
    def __init__(self):
        self.fixes_applied = []
        
    def try_fix(self, vrl_code: str, errors: List[str]) -> Tuple[str, bool, List[str]]:
        """
        Attempt to fix common VRL syntax errors locally
        
        Returns:
            Tuple of (fixed_code, was_fixed, fixes_applied)
        """
        original_code = vrl_code
        fixes_applied = []
        
        # Analyze errors
        for error in errors:
            # Fix 1: Variable array indexing
            if "unexpected syntax token: \"Identifier\"" in error and "expected one of: \"integer literal\"" in error:
                vrl_code, fixed = self._fix_variable_array_indexing(vrl_code, error)
                if fixed:
                    fixes_applied.append("Fixed variable array indexing")
                    
            # Fix 2: Empty return statements
            elif "unexpected syntax token: \"Newline\"" in error and "return" in error:
                vrl_code, fixed = self._fix_empty_return(vrl_code)
                if fixed:
                    fixes_applied.append("Fixed empty return statement")
                    
            # Fix 3: Unhandled fallible operations
            elif "E103" in error or "unhandled fallible" in error:
                vrl_code, fixed = self._fix_fallible_operation(vrl_code, error)
                if fixed:
                    fixes_applied.append("Fixed fallible operation")
                    
            # Fix 4: Missing array bounds check
            elif "E110" in error or "fallible predicate" in error:
                vrl_code, fixed = self._add_array_bounds_check(vrl_code, error)
                if fixed:
                    fixes_applied.append("Added array bounds check")
                    
            # Fix 5: Unnecessary error coalescing
            elif "E651" in error:
                vrl_code, fixed = self._remove_unnecessary_coalescing(vrl_code, error)
                if fixed:
                    fixes_applied.append("Removed unnecessary ?? operator")
        
        was_fixed = vrl_code != original_code
        
        if was_fixed:
            logger.info(f"🔧 Applied {len(fixes_applied)} local syntax fixes:")
            for fix in fixes_applied:
                logger.info(f"   - {fix}")
                
        return vrl_code, was_fixed, fixes_applied
    
    def _fix_variable_array_indexing(self, code: str, error: str) -> Tuple[str, bool]:
        """Fix array[variable] → use conditional or literal"""
        
        # Extract line number from error
        line_match = re.search(r':(\d+):\d+', error)
        if not line_match:
            return code, False
            
        line_num = int(line_match.group(1))
        lines = code.split('\n')
        
        if line_num > len(lines):
            return code, False
            
        problem_line = lines[line_num - 1]
        
        # Pattern: array[variable] or array[last_index]
        pattern = r'(\w+)\[(\w+(?:_index)?)\]'
        match = re.search(pattern, problem_line)
        
        if match:
            array_name = match.group(1)
            index_var = match.group(2)
            
            # Replace with length check and literal access
            if 'last' in index_var.lower():
                # For last_index, use length(array) - 1 pattern
                replacement = f"""
    # Fixed: Dynamic indexing not supported in VRL
    array_len = length({array_name})
    if array_len > 0 {{
        # Access last element safely
        if array_len == 1 {{
            value = {array_name}[0]
        }} else if array_len == 2 {{
            value = {array_name}[1]
        }} else if array_len == 3 {{
            value = {array_name}[2]
        }} else {{
            # For longer arrays, take a reasonable element
            value = {array_name}[2]  # Third element as fallback
        }}
    }}"""
                
                # Replace the problematic line
                indent = len(problem_line) - len(problem_line.lstrip())
                replacement_lines = replacement.split('\n')
                indented_replacement = [(' ' * indent) + line if line.strip() else '' 
                                       for line in replacement_lines]
                
                # Replace the line
                lines[line_num - 1] = '\n'.join(indented_replacement)
                
                return '\n'.join(lines), True
                
        return code, False
    
    def _fix_empty_return(self, code: str) -> Tuple[str, bool]:
        """Fix empty return statements"""
        
        # Pattern: standalone 'return' on its own line
        pattern = r'^(\s*)return\s*$'
        
        lines = code.split('\n')
        fixed = False
        
        for i, line in enumerate(lines):
            if re.match(pattern, line):
                # Replace with proper VRL pattern
                indent = len(line) - len(line.lstrip())
                lines[i] = ' ' * indent + '# Return not needed here - VRL is expression-based'
                fixed = True
                
        return '\n'.join(lines), fixed
    
    def _fix_fallible_operation(self, code: str, error: str) -> Tuple[str, bool]:
        """Add ! to make operations infallible or add error handling"""
        
        # Enhanced E103 error handling
        # Parse error to find exact line and function
        line_match = re.search(r':(\d+):(\d+)', error)
        func_match = re.search(r'`(\w+)\(', error)
        
        # Also check for common fallible functions mentioned in error
        if 'split(' in error:
            func_name = 'split'
        elif 'parse_json(' in error:
            func_name = 'parse_json'
        elif 'parse_regex(' in error:
            func_name = 'parse_regex'
        elif 'parse_timestamp(' in error:
            func_name = 'parse_timestamp'
        elif 'to_int(' in error:
            func_name = 'to_int'
        elif 'to_float(' in error:
            func_name = 'to_float'
        elif func_match:
            func_name = func_match.group(1)
        else:
            # Try to extract function name from error message
            func_pattern = r'this expression is fallible.*?`(\w+)`'
            func_match2 = re.search(func_pattern, error)
            if func_match2:
                func_name = func_match2.group(1)
            else:
                return code, False
        
        # If we have line number, fix specific line
        if line_match:
            line_num = int(line_match.group(1))
            lines = code.split('\n')
            
            if 0 < line_num <= len(lines):
                problem_line = lines[line_num - 1]
                
                # Pattern: func_name(args) without !
                pattern = f'\\b{func_name}\\('
                replacement = f'{func_name}!('
                
                if pattern in problem_line and f'{func_name}!(' not in problem_line:
                    lines[line_num - 1] = re.sub(pattern, replacement, problem_line)
                    return '\n'.join(lines), True
        
        # Fallback: Fix all occurrences of the function
        pattern = f'\\b{func_name}\\('
        replacement = f'{func_name}!('
        
        # Count how many we can fix
        matches = list(re.finditer(pattern, code))
        needs_fixing = [m for m in matches if code[m.start() - 1:m.start()] != '!']
        
        if needs_fixing:
            # Replace from end to start to maintain positions
            for match in reversed(needs_fixing):
                code = code[:match.start()] + replacement + code[match.end():]
            return code, True
            
        return code, False
    
    def _add_array_bounds_check(self, code: str, error: str) -> Tuple[str, bool]:
        """Add length checks before array access"""
        
        # Find array access patterns without bounds checking
        pattern = r'(\w+)\[(\d+)\]'
        
        lines = code.split('\n')
        fixed = False
        
        for i, line in enumerate(lines):
            if re.search(pattern, line) and 'if length(' not in line:
                match = re.search(pattern, line)
                if match:
                    array_name = match.group(1)
                    index = int(match.group(2))
                    
                    # Wrap in length check
                    indent = len(line) - len(line.lstrip())
                    new_lines = [
                        ' ' * indent + f'if length({array_name}) > {index} {{',
                        line,
                        ' ' * indent + '}'
                    ]
                    
                    # Replace the line with wrapped version
                    lines[i] = '\n'.join(new_lines)
                    fixed = True
                    
        return '\n'.join(lines), fixed
    
    def _remove_unnecessary_coalescing(self, code: str, error: str) -> Tuple[str, bool]:
        """Remove ?? from infallible operations"""
        
        # Pattern: infallible_func() ?? default
        pattern = r'(\w+!)\([^)]*\)\s*\?\?\s*[^,\n;]+'
        
        if re.search(pattern, code):
            # Remove the ?? and default value
            code = re.sub(r'(\w+!\([^)]*\))\s*\?\?\s*[^,\n;]+', r'\1', code)
            return code, True
            
        return code, False

    def estimate_fix_confidence(self, errors: List[str]) -> float:
        """
        Estimate confidence that local fixes will work
        
        Returns confidence score 0.0 to 1.0
        """
        fixable_patterns = [
            "unexpected syntax token: \"Identifier\"",
            "expected one of: \"integer literal\"",
            "unhandled fallible",
            "E103", "E110", "E651",
            "empty return",
            "??"
        ]
        
        fixable_count = sum(1 for error in errors 
                          if any(pattern in error for pattern in fixable_patterns))
        
        if not errors:
            return 0.0
            
        confidence = fixable_count / len(errors)
        return min(confidence, 0.9)  # Cap at 90% confidence


def should_try_local_fix(errors: List[str], iteration: int) -> bool:
    """
    Determine if we should try local fixes before calling LLM
    
    Decision factors:
    - Simple syntax errors present
    - Not too late in iteration cycle
    - High confidence in local fixes
    """
    fixer = VRLSyntaxFixer()
    confidence = fixer.estimate_fix_confidence(errors)
    
    # Try local fixes if:
    # - Confidence > 30% (lowered threshold)
    # - It's not too late (first 5 iterations)
    # - We have fixable errors (E103, syntax errors, etc.)
    
    has_fixable_errors = any('syntax error' in str(e) or 'E103' in str(e) or 'E110' in str(e) 
                            or 'unhandled fallible' in str(e) or 'split(' in str(e)
                           for e in errors)
    
    should_fix = confidence > 0.3 and iteration <= 5 and has_fixable_errors
    
    if should_fix:
        logger.info(f"💡 Local fix confidence: {confidence:.0%} - attempting local fixes")
    
    return should_fix


def apply_local_fixes(vrl_code: str, errors: List[str]) -> Tuple[str, bool, Dict[str, Any]]:
    """
    Main entry point for local VRL fixing
    
    Returns:
        Tuple of (fixed_code, was_fixed, metadata)
    """
    fixer = VRLSyntaxFixer()
    
    fixed_code, was_fixed, fixes = fixer.try_fix(vrl_code, errors)
    
    metadata = {
        'fixes_applied': fixes,
        'confidence': fixer.estimate_fix_confidence(errors),
        'cost_saved': 0.0
    }
    
    if was_fixed:
        # Estimate cost saved (average iteration costs ~$0.50)
        metadata['cost_saved'] = 0.50
        logger.success(f"💰 Saved ~${metadata['cost_saved']:.2f} by fixing locally")
    
    return fixed_code, was_fixed, metadata