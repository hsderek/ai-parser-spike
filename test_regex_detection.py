#!/usr/bin/env python3
"""Test regex detection logic"""

# Test VRL samples
test_cases = [
    ('# This uses regex for parsing', False, 'Comment with word regex'),
    ('msg = "looking for" something', False, 'String with "for"'),
    ('.field = parse_regex!(msg, r"\\d+")', True, 'parse_regex function'),
    ('.field = match(msg, r"pattern")', True, 'match function'),
    ('.field = split_regex!(msg, r",")', True, 'split_regex function'),
    ('if contains(msg, "for") {', False, 'String literal "for"'),
    ('.pattern = r"\\d{3}-\\d{4}"', True, 'Regex literal assignment'),
    ('# No regex, just string ops', False, 'Comment about no regex'),
]

def check_regex(vrl_code):
    """Check if VRL code contains regex functions"""
    # Remove comments
    code_lines = []
    for line in vrl_code.split('\n'):
        if '#' in line:
            code_part = line.split('#')[0]
        else:
            code_part = line
        code_lines.append(code_part)
    
    code_without_comments = '\n'.join(code_lines)
    
    # Look for actual VRL regex functions only
    regex_functions = [
        'parse_regex!',
        'parse_regex(',
        'match!',
        'match(',
        'capture_regex!',
        'capture_regex(',
        'replace_regex!',
        'replace_regex(',
        'split_regex!',
        'split_regex('
    ]
    
    found_patterns = [func for func in regex_functions if func in code_without_comments]
    
    # Check for regex literals
    import re
    if re.search(r'\br"[^"]*"', code_without_comments) or re.search(r"\br'[^']*'", code_without_comments):
        found_patterns.append('regex literal')
    
    return len(found_patterns) > 0

print("Testing regex detection logic:")
print("-" * 60)

for code, should_detect, description in test_cases:
    detected = check_regex(code)
    status = "✅" if detected == should_detect else "❌"
    print(f"{status} {description:30} | Detected: {detected}")
    if detected != should_detect:
        print(f"   Code: {code}")

print("-" * 60)
print("All tests passed!" if all(check_regex(c) == expected for c, expected, _ in test_cases) else "Some tests failed")