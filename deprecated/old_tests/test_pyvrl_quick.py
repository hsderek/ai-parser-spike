#!/usr/bin/env python3
"""Quick PyVRL test for generated code"""

import pyvrl
import json

# Load the generated VRL
with open('.tmp/anthropic_test.vrl') as f:
    vrl_code = f.read()

print("Testing VRL with PyVRL...")
print("-" * 40)

try:
    # Create transform
    transform = pyvrl.Transform(vrl_code)
    
    # Test with sample event
    test_event = {
        'message': '{"message":"<134>Aug 26 2023 10:22:33 ASA-FW-01 : %ASA-6-302015: Built outbound TCP connection 123456 for outside:192.168.1.100/44321 (192.168.1.100/44321) to dmz:10.0.0.50/443 (10.0.0.50/443)"}',
        'file': 'test.log',
        'host': 'test-host',
        'timestamp': '2023-01-01T00:00:00Z'
    }
    
    result = transform.remap(test_event)
    
    print("✅ PyVRL validation passed!")
    print("\nExtracted fields:")
    for key, value in result.items():
        if key not in test_event:
            print(f"  {key}: {value}")
    
except Exception as e:
    print(f"❌ PyVRL validation failed:")
    print(str(e)[:500])