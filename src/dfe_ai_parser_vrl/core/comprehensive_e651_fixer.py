"""
Comprehensive E651 Error Fixer

Fixes ALL E651 "unnecessary error coalescing" patterns observed in testing.
Prevents cyclical failures by handling every known E651 case.
"""

import re
from typing import List, Tuple
from loguru import logger


class ComprehensiveE651Fixer:
    """Comprehensive E651 error pattern fixer"""
    
    def __init__(self):
        # All E651 patterns observed in testing
        self.e651_patterns = [
            # split() operations with unnecessary ?? []
            (r'split\([^)]+\)\s*\?\?\s*\[\]', self._remove_split_coalescing),
            
            # Array access with unnecessary ?? ""
            (r'(\w+)\[(\d+)\]\s*\?\?\s*""', r'\1[\2]'),
            (r'parts\[(\d+)\]\s*\?\?\s*""', r'parts[\1]'),
            
            # Field assignments with unnecessary ?? null
            (r'(\.[\w_]+)\s*=\s*([^?]+)\s*\?\?\s*null', r'\1 = \2'),
            
            # exists() operations with unnecessary ?? false/null
            (r'exists\([^)]+\)\s*\?\?\s*(false|null)', self._remove_exists_coalescing),
            
            # length() operations with unnecessary ?? number
            (r'length\([^)]+\)\s*\?\?\s*\d+', self._remove_length_coalescing),
            
            # Infallible string operations
            (r'(string!\([^)]+\))\s*\?\?\s*""', r'\1'),
            (r'(upcase\([^)]+\))\s*\?\?\s*""', r'\1'),
            (r'(downcase\([^)]+\))\s*\?\?\s*""', r'\1'),
            
            # Double coalescing patterns
            (r'\?\?\s*[^?\s]+\s*\?\?\s*', self._fix_double_coalescing),
            
            # Semicolon issues with coalescing
            (r'(\?\?\s*\[\])\s*;', r'\1'),
            (r'(\?\?\s*"")\s*;', r'\1'),
            (r'(\?\?\s*null)\s*;', r'\1'),
        ]
    
    def fix_all_e651_patterns(self, vrl_code: str) -> str:
        """Apply comprehensive E651 fixes to eliminate all unnecessary coalescing"""
        
        logger.info("🔧 Applying comprehensive E651 fixes...")
        
        lines = vrl_code.split('\n')
        fixed_lines = []
        fixes_applied = 0
        
        for line_num, line in enumerate(lines, 1):
            original_line = line
            
            # Skip comments and empty lines
            if line.strip().startswith('#') or not line.strip():
                fixed_lines.append(line)
                continue
            
            # Apply all E651 patterns
            for pattern, replacement in self.e651_patterns:
                if isinstance(replacement, str):
                    # Simple regex replacement
                    new_line = re.sub(pattern, replacement, line)
                else:
                    # Custom function replacement
                    new_line = replacement(line, pattern)
                
                if new_line != line:
                    logger.debug(f"Line {line_num}: E651 fix applied")
                    line = new_line
                    fixes_applied += 1
                    break  # One fix per line to avoid conflicts
            
            fixed_lines.append(line)
        
        result = '\n'.join(fixed_lines)
        
        if fixes_applied > 0:
            logger.info(f"✅ Applied {fixes_applied} comprehensive E651 fixes")
        
        return result
    
    def _remove_split_coalescing(self, line: str, pattern: str) -> str:
        """Remove ?? [] from split operations"""
        return re.sub(r'split\([^)]+\)\s*\?\?\s*\[\]', 
                     lambda m: m.group(0).replace(' ?? []', ''), line)
    
    def _remove_exists_coalescing(self, line: str, pattern: str) -> str:
        """Remove ?? false/null from exists() operations"""
        return re.sub(r'exists\([^)]+\)\s*\?\?\s*(false|null)', 
                     lambda m: m.group(0).split(' ??')[0], line)
    
    def _remove_length_coalescing(self, line: str, pattern: str) -> str:
        """Remove ?? number from length() operations"""
        return re.sub(r'length\([^)]+\)\s*\?\?\s*\d+', 
                     lambda m: m.group(0).split(' ??')[0], line)
    
    def _fix_double_coalescing(self, line: str, pattern: str) -> str:
        """Fix double coalescing patterns"""
        # Find ?? X ?? Y patterns and simplify to ?? Y
        return re.sub(r'\?\?\s*[^?\s]+\s*(\?\?\s*[^?\s]+)', r'\1', line)


# Global comprehensive fixer instance
_comprehensive_e651_fixer = ComprehensiveE651Fixer()

def apply_comprehensive_e651_fixes(vrl_code: str) -> str:
    """Apply all comprehensive E651 fixes"""
    return _comprehensive_e651_fixer.fix_all_e651_patterns(vrl_code)

def test_e651_patterns():
    """Test E651 pattern fixing"""
    
    test_cases = [
        'parts = split(message_str, " for ") ?? []',
        'user_part = parts[1] ?? ""',  
        'exists(.field) ?? false',
        'length(parts) ?? 0',
        'string!(field) ?? ""',
        'parts = split(text, " ") ?? []; # semicolon issue'
    ]
    
    print("Testing E651 comprehensive fixes:")
    for test_case in test_cases:
        fixed = apply_comprehensive_e651_fixes(test_case)
        if fixed != test_case:
            print(f"✅ Fixed: {test_case} → {fixed}")
        else:
            print(f"⚠️ No fix: {test_case}")


if __name__ == "__main__":
    test_e651_patterns()