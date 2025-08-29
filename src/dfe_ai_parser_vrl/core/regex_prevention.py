"""
Regex Prevention System for VRL Generation

Implements multiple strategies to prevent LLMs from generating regex-based VRL code,
which is 50-100x slower than string operations.
"""

import re
from typing import Tuple, List, Dict, Any
from loguru import logger


class RegexPreventionSystem:
    """Prevents and fixes regex usage in VRL generation"""
    
    def __init__(self):
        # Forbidden regex functions and patterns
        self.forbidden_regex_functions = [
            'parse_regex', 'parse_regex!', 'parse_regex_all',
            'match', 'match!', 'match_array', 
            'to_regex', 'replace_with_regex'
        ]
        
        # Regex pattern indicators  
        self.regex_indicators = [
            r'r"[^"]*\\[wdsWDS]',  # Raw strings with regex chars
            r"r'[^']*\\[wdsWDS]",  # Raw strings with regex chars
            r'\?P<\w+>',           # Named capture groups
            r'\\[wdsWDS]',         # Regex escape sequences
            r'\[\^',               # Character class negation
            r'\[a-zA-Z0-9',        # Character ranges
        ]
    
    def pre_generation_check(self, prompt: str) -> str:
        """Add anti-regex instructions to prompt before LLM generation"""
        
        anti_regex_header = """
🚨 CRITICAL: ABSOLUTELY NO REGEX FUNCTIONS 🚨

FORBIDDEN FUNCTIONS (Will cause immediate failure):
❌ parse_regex() ❌ parse_regex!() ❌ match() ❌ match_array() ❌ to_regex()

FORBIDDEN PATTERNS:
❌ r"\\w+" ❌ r"\\d+" ❌ r"\\S+" ❌ (?P<name>) ❌ [a-zA-Z0-9]

REQUIRED APPROACH - String Operations Only:
✅ contains(text, "pattern")     # Find text
✅ split(text, " ")             # Split by delimiter  
✅ starts_with(text, "prefix")  # Prefix check
✅ ends_with(text, "suffix")    # Suffix check
✅ slice(text, start, end)      # Extract substring

PERFORMANCE IMPACT:
• String operations: 400 events/CPU%  
• Regex operations: 8 events/CPU% (50x SLOWER!)

EXAMPLES OF CORRECT VRL:
"""

        string_examples = """
# ✅ CORRECT: Extract IP using string operations
if contains(message_str, " from ") {
    from_parts = split(message_str, " from ")
    if length(from_parts) >= 2 {
        ip_words = split(from_parts[1], " ")
        .source_ip = ip_words[0]  # First word after "from"
    }
}

# ✅ CORRECT: Extract username using string operations  
if contains(message_str, "Invalid user ") {
    user_parts = split(message_str, "Invalid user ")
    if length(user_parts) >= 2 {
        .username = split(user_parts[1], " ")[0]  # First word after "Invalid user"
    }
}

# ❌ WRONG: Using regex (FORBIDDEN)
# ip_match = parse_regex!(message_str, r"from (?P<ip>\\d+\\.\\d+\\.\\d+\\.\\d+)")
"""
        
        return anti_regex_header + string_examples + "\n" + prompt
    
    def post_generation_check(self, vrl_code: str) -> Tuple[bool, List[str]]:
        """Check generated VRL for regex usage"""
        
        violations = []
        
        # Check for forbidden functions
        for func in self.forbidden_regex_functions:
            if func in vrl_code:
                violations.append(f"FORBIDDEN_FUNCTION: {func}")
        
        # Check for regex patterns
        for pattern in self.regex_indicators:
            if re.search(pattern, vrl_code):
                violations.append(f"REGEX_PATTERN: {pattern}")
        
        # Check for escape sequences in raw strings
        raw_string_matches = re.findall(r'r["\'][^"\']*["\']', vrl_code)
        for match in raw_string_matches:
            if '\\' in match:
                violations.append(f"RAW_STRING_REGEX: {match}")
        
        has_regex = len(violations) > 0
        
        if has_regex:
            logger.warning(f"🚨 REGEX DETECTED in VRL: {len(violations)} violations")
            for violation in violations:
                logger.warning(f"   - {violation}")
        
        return has_regex, violations
    
    def fix_regex_in_vrl(self, vrl_code: str) -> str:
        """Automatically replace regex patterns with string operations"""
        
        fixed_code = vrl_code
        
        # Replace common regex patterns with string operations
        regex_replacements = [
            # Remove regex functions entirely
            (r'parse_regex!\([^)]+\)', '{}'),
            (r'parse_regex\([^)]+\)', '{}'),
            (r'match!\([^)]+\)', 'false'),
            (r'match\([^)]+\)', 'false'),
            
            # Replace regex-based field extraction examples
            (r'r"[^"]*\\w+[^"]*"', '"text"'),  # Replace \\w+ patterns
            (r'r"[^"]*\\d+[^"]*"', '"number"'),  # Replace \\d+ patterns
            (r'r"[^"]*\\S+[^"]*"', '"word"'),  # Replace \\S+ patterns
            (r'\?P<\w+>', ''),  # Remove named capture groups
        ]
        
        for pattern, replacement in regex_replacements:
            fixed_code = re.sub(pattern, replacement, fixed_code)
        
        # Remove lines that still contain regex indicators
        lines = fixed_code.split('\n')
        clean_lines = []
        
        for line in lines:
            # Skip lines with remaining regex patterns
            if any(indicator in line for indicator in ['\\w', '\\d', '\\S', '(?P<', 'parse_regex', 'match(']):
                logger.info(f"   Removing regex line: {line.strip()}")
                continue
            clean_lines.append(line)
        
        fixed_code = '\n'.join(clean_lines)
        
        return fixed_code
    
    def get_string_operation_alternative(self, regex_intent: str) -> str:
        """Suggest string operation alternatives to common regex patterns"""
        
        alternatives = {
            "extract_ip": """
# Extract IP using string operations
if contains(message_str, " from ") {
    from_parts = split(message_str, " from ")
    if length(from_parts) >= 2 {
        .source_ip = split(from_parts[1], " ")[0]
    }
}""",
            
            "extract_username": """
# Extract username using string operations
if contains(message_str, "Invalid user ") {
    user_parts = split(message_str, "Invalid user ")
    if length(user_parts) >= 2 {
        .username = split(user_parts[1], " ")[0]
    }
}""",
            
            "extract_port": """
# Extract port using string operations
if contains(message_str, " port ") {
    port_parts = split(message_str, " port ")
    if length(port_parts) >= 2 {
        .port = split(port_parts[1], " ")[0]
    }
}""",
            
            "extract_process_pid": """
# Extract process and PID using string operations
if contains(message_str, "[") && contains(message_str, "]") {
    bracket_parts = split(message_str, "[")
    if length(bracket_parts) >= 2 {
        pid_part = split(bracket_parts[1], "]")[0]
        .pid = pid_part
    }
}"""
        }
        
        return alternatives.get(regex_intent, "# Use contains() and split() operations")


# Global instance
_regex_prevention = RegexPreventionSystem()

def prevent_regex_in_prompt(prompt: str) -> str:
    """Add anti-regex instructions to prompt"""
    return _regex_prevention.pre_generation_check(prompt)

def check_vrl_for_regex(vrl_code: str) -> Tuple[bool, List[str]]:
    """Check if VRL contains regex patterns"""
    return _regex_prevention.post_generation_check(vrl_code)

def fix_regex_in_vrl(vrl_code: str) -> str:
    """Remove regex from VRL code"""
    return _regex_prevention.fix_regex_in_vrl(vrl_code)