"""
VRL error fixing using LLM and pattern-based fixes
"""

import re
from typing import Optional, Dict, Any
from loguru import logger
from .comprehensive_e651_fixer import apply_comprehensive_e651_fixes
from .error_learning_system import learn_from_error, apply_all_learned_fixes


class DFEVRLErrorFixer:
    """Fixes VRL syntax errors"""
    
    def __init__(self, llm_client):
        self.llm_client = llm_client
        self.error_patterns = self._init_error_patterns()
    
    def _init_error_patterns(self) -> Dict[str, Any]:
        """Initialize error patterns and fixes"""
        return {
            "E103": {  # Unhandled fallible
                "pattern": r"error\[E103\].*unhandled fallible",
                "fix": self._fix_unhandled_fallible
            },
            "E105": {  # Undefined function
                "pattern": r"error\[E105\].*undefined",
                "fix": self._fix_undefined_function
            },
            "E110": {  # Invalid argument type / Fallible predicate
                "pattern": r"error\[E110\].*(invalid argument type|fallible.*predicate)",
                "fix": self._fix_fallible_predicate
            },
            "E203": {  # Syntax error
                "pattern": r"error\[E203\].*syntax",
                "fix": self._fix_syntax_error
            },
            "E620": {  # Infallible abort
                "pattern": r"error\[E620\].*can't abort.*infallible",
                "fix": self._fix_infallible_abort
            },
            "E651": {  # Unnecessary coalescing
                "pattern": r"error\[E651\].*unnecessary.*coalescing",
                "fix": self._fix_unnecessary_coalescing
            },
            "E610": {  # Function compilation error
                "pattern": r"error\[E610\].*function compilation error.*del\(",
                "fix": self._fix_del_variable_error
            }
        }
    
    def fix(self, vrl_code: str, error_message: str, sample_logs: str = None) -> Optional[str]:
        """
        Fix VRL error using LLM
        
        Args:
            vrl_code: VRL code with error
            error_message: Error message from validator
            sample_logs: Optional original logs
            
        Returns:
            Fixed VRL code or None if unable to fix
        """
        logger.info("Using LLM to fix error")
        return self.llm_client.fix_vrl_error(vrl_code, error_message, sample_logs)
    
    def fix_locally(self, vrl_code: str, error_message: str) -> Optional[str]:
        """
        Attempt local pattern-based fixes with error learning (free)
        
        Args:
            vrl_code: VRL code with error
            error_message: Error message from validator
            
        Returns:
            Fixed VRL code or None if unable to fix locally
        """
        # Extract error code for learning
        error_code = self._extract_error_code(error_message)
        
        # Learn from this error (builds fix database)
        learned_new_pattern = learn_from_error(error_code, error_message, vrl_code)
        if learned_new_pattern:
            logger.info(f"🎓 Learned new {error_code} pattern")
        
        # Apply all learned fixes first (comprehensive)
        enhanced_fixed = apply_all_learned_fixes(vrl_code)
        if enhanced_fixed != vrl_code:
            logger.info(f"🎓 Applied learned fixes for {error_code}")
            return enhanced_fixed
        
        # Try traditional pattern-based fixes
        for err_code, pattern_info in self.error_patterns.items():
            if re.search(pattern_info["pattern"], error_message, re.IGNORECASE):
                logger.info(f"Applying local {err_code} fix")
                fixed = pattern_info["fix"](vrl_code, error_message)
                if fixed and fixed != vrl_code:
                    return fixed
        
        return None
    
    def _extract_error_code(self, error_message: str) -> str:
        """Extract error code from error message"""
        if not error_message:
            return "UNKNOWN"
        
        import re
        match = re.search(r'error\[E(\d+)\]', error_message)
        if match:
            return f"E{match.group(1)}"
        
        if "syntax error" in error_message.lower():
            return "E203"
        elif "coalescing" in error_message.lower():
            return "E651"
        elif "fallible" in error_message.lower():
            return "E103"
        elif "predicate" in error_message.lower():
            return "E110"
        
        return "UNKNOWN"
    
    def fix_with_history(self, vrl_code: str, error_message: str, sample_logs: str, iteration_context: str) -> str:
        """
        Fix VRL error with iteration history context to prevent cycles
        
        Args:
            vrl_code: VRL code with error
            error_message: Error message from validator
            sample_logs: Original log samples
            iteration_context: Context of previous attempts
            
        Returns:
            Fixed VRL code with anti-cyclical approach
        """
        logger.info("🔄 Using LLM error fix with iteration history context")
        
        # Enhanced fix prompt with iteration history
        enhanced_prompt = f"""You are a VRL expert fixing errors with ITERATION HISTORY to prevent repetition.

🚨🚨🚨 ABSOLUTELY NO REGEX - WILL CAUSE IMMEDIATE FAILURE 🚨🚨🚨

ITERATION HISTORY CONTEXT:
{iteration_context}

🚨 CRITICAL: DO NOT REPEAT PREVIOUS MISTAKES
- If patterns failed before, try completely different approach
- If same error keeps appearing, simplify the logic drastically
- Avoid complex array operations that caused previous failures

CURRENT ERROR TO FIX:
{error_message}

CURRENT VRL CODE:
```vrl
{vrl_code}
```

ANTI-CYCLICAL REQUIREMENTS:
1. Generate DIFFERENT solution than previous attempts
2. If previous attempts failed with complex patterns, use SIMPLER patterns
3. Avoid any patterns mentioned in the failed patterns list
4. Focus on MINIMAL working code, not comprehensive parsing

Return only the fixed VRL code that breaks the error cycle."""

        # Use standard LLM completion
        messages = [
            {"role": "user", "content": enhanced_prompt}
        ]
        
        response = self.llm_client.completion(messages, max_tokens=6000, temperature=0.2)
        
        if hasattr(response, 'choices') and response.choices:
            fixed_code = response.choices[0].message.content
            return self.llm_client._extract_vrl_code(fixed_code)
        
        return vrl_code  # Return original if no fix available
    
    def _fix_unhandled_fallible(self, vrl_code: str, error_message: str) -> str:
        """Fix unhandled fallible assignment - comprehensive approach"""
        import re
        
        lines = vrl_code.split('\n')
        fixed_lines = []
        
        for line in lines:
            # Skip comments and empty lines
            if line.strip().startswith('#') or not line.strip():
                fixed_lines.append(line)
                continue
            
            # Fix all array access patterns - this is the main E103 cause
            # Pattern: variable = split(something, delimiter)[index]
            line = re.sub(r'(\w+)\s*=\s*split\(([^)]+)\)\s*\[\s*(\d+)\s*\]', 
                         r'\1 = (split(\2) ?? [])[\3] ?? ""', line)
            
            # Pattern: .field = split(something, delimiter)[index] 
            line = re.sub(r'(\.[\w_]+)\s*=\s*split\(([^)]+)\)\s*\[\s*(\d+)\s*\]',
                         r'\1 = (split(\2) ?? [])[\3] ?? ""', line)
            
            # Fix nested split operations: split(split(x)[0])[1]
            line = re.sub(r'split\(split\(([^)]+)\)\s*\[\s*(\d+)\s*\]\s*\)\s*\[\s*(\d+)\s*\]',
                         r'(split((split(\1) ?? [])[\2] ?? "") ?? [])[\3] ?? ""', line)
            
            # Fix direct array access without null coalescing
            if re.search(r'(\w+)\s*=\s*(\w+)\[\s*\d+\s*\]', line) and '??' not in line:
                # variable = array[index] -> variable = array[index] ?? ""
                line = re.sub(r'(\w+)\s*=\s*(\w+)\[(\d+)\]', r'\1 = \2[\3] ?? ""', line)
                
            if re.search(r'(\.[\w_]+)\s*=\s*(\w+)\[\s*\d+\s*\]', line) and '??' not in line:
                # .field = array[index] -> .field = array[index] ?? ""  
                line = re.sub(r'(\.[\w_]+)\s*=\s*(\w+)\[(\d+)\]', r'\1 = \2[\3] ?? ""', line)
            
            # Fix any remaining split operations that need null coalescing
            if 'split(' in line and '??' not in line and '=' in line:
                # Add null coalescing to all split operations in assignments
                line = re.sub(r'=\s*split\(([^)]+)\)', r'= split(\1) ?? []', line)
            
            # Fix fallible function calls in assignments
            fallible_functions = ['parse_timestamp', 'parse_json', 'to_int', 'to_float', 'strip_whitespace']
            for func in fallible_functions:
                if func in line and '=' in line and '??' not in line:
                    line = re.sub(f'{func}\\(([^)]+)\\)', f'{func}(\\1) ?? null', line)
            
            fixed_lines.append(line)
        
        return '\n'.join(fixed_lines)
    
    def _fix_undefined_function(self, vrl_code: str, error_message: str) -> str:
        """Fix undefined function errors"""
        replacements = {
            'parse_timestamp!': 'parse_timestamp',
            'parse_json!': 'parse_json',
            'split!': 'split',
            'parse_regex!': 'parse_regex',
            'to_timestamp!': 'to_timestamp',
            'encode_json!': 'encode_json'
        }
        
        fixed = vrl_code
        for old, new in replacements.items():
            fixed = fixed.replace(old, new)
        
        return fixed
    
    def _fix_fallible_predicate(self, vrl_code: str, error_message: str) -> str:
        """Fix fallible expressions in predicates"""
        import re
        
        lines = vrl_code.split('\n')
        fixed_lines = []
        
        for line in lines:
            # Fix includes() -> contains() (common E110 error)
            line = line.replace('includes(', 'contains(')
            
            # Fix array type issues in contains()
            if 'contains(' in line and 'string!' in line:
                # Fix contains(string!(...), "text") which expects array
                line = re.sub(r'contains\(string!\(([^)]+)\),', r'contains(\1,', line)
            
            # Fix fallible operations in if conditions
            if 'if ' in line and any(func in line for func in ['parse_', 'split']):
                # Wrap fallible operations for boolean context
                if 'parse_' in line:
                    line = re.sub(r'(parse_\w+\([^)]+\))', r'(\1 ?? false)', line)
                if 'split(' in line and not '??' in line:
                    line = re.sub(r'(split\([^)]+\))', r'(\1 ?? [])', line)
            
            fixed_lines.append(line)
        
        return '\n'.join(fixed_lines)
    
    def _fix_syntax_error(self, vrl_code: str, error_message: str) -> str:
        """Fix general syntax errors"""
        # Common syntax fixes
        fixed = vrl_code
        
        # Fix missing semicolons
        lines = fixed.split('\n')
        fixed_lines = []
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped and not stripped.endswith((';', '{', '}', '//')) and not stripped.startswith('#'):
                # Check if this looks like a statement that needs a semicolon
                if '=' in stripped or stripped.startswith(('.', 'del(', 'abort')):
                    line = line.rstrip() + ';'
            
            fixed_lines.append(line)
        
        return '\n'.join(fixed_lines)
    
    def _fix_infallible_abort(self, vrl_code: str, error_message: str) -> str:
        """Fix abort in infallible context"""
        # Remove abort statements or replace with error handling
        lines = vrl_code.split('\n')
        fixed_lines = []
        
        for line in lines:
            if 'abort' in line.lower():
                # Comment out or remove abort statements
                continue  # Skip abort lines
            
            fixed_lines.append(line)
        
        return '\n'.join(fixed_lines)
    
    def _fix_unnecessary_coalescing(self, vrl_code: str, error_message: str) -> str:
        """Fix unnecessary error coalescing - use comprehensive E651 fixer"""
        return apply_comprehensive_e651_fixes(vrl_code)
    
    def _fix_del_variable_error(self, vrl_code: str, error_message: str) -> str:
        """Fix del() variable error - remove or convert to field deletion"""
        lines = vrl_code.split('\n')
        fixed_lines = []
        
        for line in lines:
            stripped = line.strip()
            # Remove del(variable) calls that don't work in VRL
            if stripped.startswith('del(') and not stripped.startswith('del(.'):
                # Remove the line entirely or comment it out
                continue
            fixed_lines.append(line)
            
        return '\n'.join(fixed_lines)