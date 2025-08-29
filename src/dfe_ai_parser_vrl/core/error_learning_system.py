"""
Error Learning System

Learns from repeating errors that the LLM cannot fix and develops
local fixes to prevent cyclical failures. Automatically improves
error fixing capabilities based on observed patterns.
"""

import re
from typing import Dict, List, Set, Any, Optional
from collections import defaultdict, Counter
from loguru import logger


class ErrorLearningSystem:
    """Learns from repeating VRL errors and develops automatic fixes"""
    
    def __init__(self):
        # Track error patterns and frequencies
        self.error_frequency: Dict[str, int] = Counter()
        self.error_patterns: Dict[str, List[str]] = defaultdict(list)
        self.learned_fixes: Dict[str, Any] = {}
        
        # Initialize with known fixes
        self._init_known_fixes()
    
    def _init_known_fixes(self):
        """Initialize with patterns learned from testing"""
        
        # E203 fixes
        self.learned_fixes['E203_return_statement'] = {
            'pattern': r'^\s*return\s*$',
            'fix': lambda line: '# removed bare return statement',
            'description': 'Remove bare return statements'
        }
        
        self.learned_fixes['E203_function_in_array'] = {
            'pattern': r'parts\[length\(parts\)\s*-\s*1\]',
            'fix': lambda line: line.replace('parts[length(parts) - 1]', 'parts[to_int!(length(parts)) - 1]'),
            'description': 'Fix function calls in array indices'
        }
        
        # E651 fixes  
        self.learned_fixes['E651_split_coalescing'] = {
            'pattern': r'split\([^)]+\)\s*\?\?\s*\[\]',
            'fix': lambda line: re.sub(r'\s*\?\?\s*\[\]', '', line),
            'description': 'Remove unnecessary ?? [] from split operations'
        }
        
        self.learned_fixes['E651_array_coalescing'] = {
            'pattern': r'(\w+\[\d+\])\s*\?\?\s*""',
            'fix': lambda line: re.sub(r'(\w+\[\d+\])\s*\?\?\s*""', r'\1', line),
            'description': 'Remove unnecessary ?? "" from array access'
        }
        
        # E103 fixes
        self.learned_fixes['E103_fallible_split'] = {
            'pattern': r'(\w+)\s*=\s*split\(([^)]+)\)(?!\s*\?\?)',
            'fix': lambda line: re.sub(r'(\w+)\s*=\s*split\(([^)]+)\)(?!\s*\?\?)', r'\1 = split(\2) ?? []', line),
            'description': 'Add error handling to fallible split operations'
        }
        
        # E110 fixes  
        self.learned_fixes['E110_direct_field_contains'] = {
            'pattern': r'contains\(\.(\w+),',
            'fix': self._fix_direct_field_contains,
            'description': 'Convert direct field contains to type-safe version'
        }
    
    def learn_from_error(self, error_code: str, error_message: str, vrl_code: str) -> bool:
        """
        Learn from a repeating error and develop fixes
        
        Args:
            error_code: Error code (E203, E651, etc.)
            error_message: Full error message
            vrl_code: VRL code that caused the error
            
        Returns:
            True if new pattern learned
        """
        # Track frequency
        self.error_frequency[error_code] += 1
        
        # Extract specific error patterns
        if error_code == 'E203':
            return self._learn_e203_patterns(error_message, vrl_code)
        elif error_code == 'E651':
            return self._learn_e651_patterns(error_message, vrl_code) 
        elif error_code == 'E103':
            return self._learn_e103_patterns(error_message, vrl_code)
        elif error_code == 'E110':
            return self._learn_e110_patterns(error_message, vrl_code)
        
        return False
    
    def apply_learned_fixes(self, vrl_code: str) -> str:
        """Apply all learned fixes to VRL code"""
        
        fixed_code = vrl_code
        fixes_applied = []
        
        lines = fixed_code.split('\n')
        fixed_lines = []
        
        for line_num, line in enumerate(lines, 1):
            original_line = line
            
            # Apply all learned fixes
            for fix_name, fix_info in self.learned_fixes.items():
                pattern = fix_info['pattern']
                fix_func = fix_info['fix']
                
                if isinstance(pattern, str):
                    if re.search(pattern, line):
                        try:
                            if callable(fix_func):
                                line = fix_func(line)
                            else:
                                line = re.sub(pattern, fix_func, line)
                            
                            if line != original_line:
                                fixes_applied.append(f"Line {line_num}: {fix_name}")
                                break  # One fix per line
                                
                        except Exception as e:
                            logger.debug(f"Fix {fix_name} failed on line {line_num}: {e}")
            
            fixed_lines.append(line)
        
        result = '\n'.join(fixed_lines)
        
        if fixes_applied:
            logger.info(f"🎓 Applied {len(fixes_applied)} learned fixes")
            for fix in fixes_applied:
                logger.debug(f"   ✅ {fix}")
        
        return result
    
    def _learn_e203_patterns(self, error_message: str, vrl_code: str) -> bool:
        """Learn new E203 syntax error patterns"""
        
        # Extract line numbers from error
        line_matches = re.findall(r'(\d+)\s*│[^│]*│\s*(.+)', error_message)
        
        new_patterns = 0
        for line_num, line_content in line_matches:
            pattern_key = f"E203_line_{line_content.strip()[:30]}"
            
            if pattern_key not in self.learned_fixes:
                # Learn new E203 pattern
                if 'return' in line_content and 'unexpected' in error_message:
                    self.learned_fixes[pattern_key] = {
                        'pattern': line_content.strip(),
                        'fix': lambda l: '# ' + l.strip(),  # Comment out problematic line
                        'description': f'Comment out problematic line: {line_content.strip()[:50]}'
                    }
                    new_patterns += 1
                    logger.info(f"🎓 Learned new E203 pattern: {pattern_key}")
        
        return new_patterns > 0
    
    def _learn_e651_patterns(self, error_message: str, vrl_code: str) -> bool:
        """Learn new E651 coalescing patterns"""
        # E651 patterns are handled by comprehensive fixer
        return False
    
    def _learn_e103_patterns(self, error_message: str, vrl_code: str) -> bool:
        """Learn new E103 fallible operation patterns"""
        
        # Extract fallible operations from error message
        fallible_matches = re.findall(r'`([^`]+)`.*?expected.*?parameter.*?type.*?string', error_message)
        
        new_patterns = 0
        for match in fallible_matches:
            if 'split(' in match:
                pattern_key = f"E103_fallible_split_{hash(match) % 1000}"
                
                if pattern_key not in self.learned_fixes:
                    self.learned_fixes[pattern_key] = {
                        'pattern': re.escape(match),
                        'fix': lambda line, m=match: line.replace(m, f'({m} ?? "")'),
                        'description': f'Add type safety to fallible operation: {match[:50]}'
                    }
                    new_patterns += 1
                    logger.info(f"🎓 Learned new E103 pattern: {match[:50]}")
        
        return new_patterns > 0
    
    def _learn_e110_patterns(self, error_message: str, vrl_code: str) -> bool:
        """Learn new E110 type error patterns"""
        # E110 patterns are handled by type safety standard
        return False
    
    def _fix_direct_field_contains(self, line: str) -> str:
        """Fix direct field contains operations"""
        # Replace contains(.field, with contains(field_str,
        return re.sub(r'contains\(\.(\w+),', 
                     lambda m: f"contains({m.group(1)}_str,", line)
    
    def get_learning_summary(self) -> Dict[str, Any]:
        """Get summary of learned error patterns"""
        return {
            'total_learned_fixes': len(self.learned_fixes),
            'error_frequencies': dict(self.error_frequency),
            'most_common_errors': self.error_frequency.most_common(5),
            'learned_fix_types': list(self.learned_fixes.keys())
        }


# Global learning system
_error_learning = ErrorLearningSystem()

def learn_from_error(error_code: str, error_message: str, vrl_code: str) -> bool:
    """Learn from repeating error"""
    return _error_learning.learn_from_error(error_code, error_message, vrl_code)

def apply_all_learned_fixes(vrl_code: str) -> str:
    """Apply all learned error fixes"""
    return _error_learning.apply_learned_fixes(vrl_code)

def get_error_learning_summary() -> Dict[str, Any]:
    """Get learning system summary"""
    return _error_learning.get_learning_summary()