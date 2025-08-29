#!/usr/bin/env python3
"""
Direct test of local fixes to debug integration
"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent / 'src'))

from model_specific_vrl_fixer import get_model_specific_fixer

def test_direct_fixes():
    """Test the local fixes directly"""
    
    print("🧪 TESTING LOCAL FIXES DIRECTLY")
    print("="*50)
    
    # Test Claude Opus fixer
    fixer = get_model_specific_fixer({"provider": "anthropic", "model": "claude-opus-4-1"})
    print(f"✅ Got fixer: {fixer.model_name}")
    
    # Test E105 errors (undefined functions)
    print("\n🔧 Testing E105 fixes:")
    bad_vrl_e105 = """
    .field = string_fast!(value)
    .count = int32!(number)  
    .host = string_low_cardinality!(hostname)
    """
    
    errors_e105 = [
        'error[E105]: call to undefined function "string_fast"',
        'error[E105]: call to undefined function "int32"',
        'error[E105]: call to undefined function "string_low_cardinality"'
    ]
    
    fixed_vrl, was_fixed, metadata = fixer.fix(bad_vrl_e105, errors_e105)
    
    if was_fixed:
        print(f"✅ E105 fixes applied: {metadata['fixes_applied']}")
        print(f"Fixed code preview:\n{fixed_vrl[:200]}...")
    else:
        print("❌ E105 fixes not applied")
    
    # Test E651 errors (unnecessary ??)
    print("\n🔧 Testing E651 fixes:")
    bad_vrl_e651 = """
    .result = string!(value) ?? null
    .count = to_int!(number) ?? 0
    """
    
    errors_e651 = [
        'error[E651]: unnecessary error coalescing operation'
    ]
    
    fixed_vrl2, was_fixed2, metadata2 = fixer.fix(bad_vrl_e651, errors_e651)
    
    if was_fixed2:
        print(f"✅ E651 fixes applied: {metadata2['fixes_applied']}")
        print(f"Fixed code preview:\n{fixed_vrl2[:200]}...")
    else:
        print("❌ E651 fixes not applied")
    
    # Test E620 errors (can't abort infallible)
    print("\n🔧 Testing E620 fixes:")
    bad_vrl_e620 = """
    parts = split!(msg, "rhost=")
    result = contains!(text, "pattern")
    """
    
    errors_e620 = [
        'error[E620]: can\'t abort infallible function'
    ]
    
    fixed_vrl3, was_fixed3, metadata3 = fixer.fix(bad_vrl_e620, errors_e620)
    
    if was_fixed3:
        print(f"✅ E620 fixes applied: {metadata3['fixes_applied']}")
        print(f"Fixed code preview:\n{fixed_vrl3[:200]}...")
    else:
        print("❌ E620 fixes not applied")
    
    print(f"\n📊 Summary:")
    print(f"E105 fixes: {'✅' if was_fixed else '❌'}")
    print(f"E651 fixes: {'✅' if was_fixed2 else '❌'}")  
    print(f"E620 fixes: {'✅' if was_fixed3 else '❌'}")

if __name__ == "__main__":
    test_direct_fixes()