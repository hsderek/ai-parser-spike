"""
VRL error fixing using LLM and pattern-based fixes
"""

import re
from typing import Optional, Dict, Any
from loguru import logger


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
            "E110": {  # Fallible predicate
                "pattern": r"error\[E110\].*fallible.*predicate",
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
            }
        }
    
    def fix(self, vrl_code: str, error_message: str, sample_logs: str = None) -> Optional[str]:
        """
        Fix VRL error
        
        Args:
            vrl_code: VRL code with error
            error_message: Error message from validator
            sample_logs: Optional original logs
            
        Returns:
            Fixed VRL code or None if unable to fix
        """
        # Try pattern-based fixes first
        for error_code, pattern_info in self.error_patterns.items():
            if re.search(pattern_info["pattern"], error_message, re.IGNORECASE):
                logger.info(f"Applying {error_code} fix")
                fixed = pattern_info["fix"](vrl_code, error_message)
                if fixed:
                    return fixed
        
        # Fall back to LLM-based fix
        logger.info("Using LLM to fix error")
        return self.llm_client.fix_vrl_error(vrl_code, error_message, sample_logs)
    
    def _fix_unhandled_fallible(self, vrl_code: str, error_message: str) -> str:
        """Fix unhandled fallible assignment"""
        # Add error handling to fallible assignments
        lines = vrl_code.split('\n')
        fixed_lines = []
        
        for line in lines:
            # Look for assignments without error handling
            if '=' in line and not '??' in line and not line.strip().startswith('#'):
                # Check if this looks like a fallible operation
                if any(func in line for func in ['parse_timestamp', 'parse_json', 'parse_regex', 'split']):
                    # Add null coalescing
                    if not line.rstrip().endswith('?? null'):
                        line = line.rstrip() + ' ?? null'
            
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
        lines = vrl_code.split('\n')
        fixed_lines = []
        
        for line in lines:
            if 'if ' in line and any(func in line for func in ['parse_', 'split', 'contains']):
                # Wrap fallible operations in exists() or add ?? false
                if 'parse_' in line or 'split' in line:
                    if not '??' in line and not 'exists' in line:
                        # Add null coalescing for boolean context
                        line = re.sub(r'(parse_\w+\([^)]+\))', r'(\1 ?? false)', line)
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
        """Fix unnecessary error coalescing"""
        # Remove ?? operators on infallible operations
        infallible_patterns = [
            (r'(\.[\w]+)\s*\?\?\s*null', r'\1'),  # Field access doesn't need ??
            (r'(string!\([^)]+\))\s*\?\?\s*null', r'\1'),  # Infallible functions
            (r'(int!\([^)]+\))\s*\?\?\s*null', r'\1'),
            (r'(float!\([^)]+\))\s*\?\?\s*null', r'\1'),
            (r'(bool!\([^)]+\))\s*\?\?\s*null', r'\1'),
        ]
        
        fixed = vrl_code
        for pattern, replacement in infallible_patterns:
            fixed = re.sub(pattern, replacement, fixed)
        
        return fixed