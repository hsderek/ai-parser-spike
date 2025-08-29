#!/usr/bin/env python3
"""
Debug Vector CLI execution to understand why validation is failing
"""

import subprocess
import yaml
import json
import tempfile
import os
from pathlib import Path

def test_vector_validation():
    """Test Vector CLI validation with a simple config"""
    
    # Create minimal test data
    test_data = [
        {"message": "test log 1", "timestamp": "2023-01-01T00:00:00Z"},
        {"message": "test log 2", "timestamp": "2023-01-01T00:00:01Z"}
    ]
    
    # Write test data
    test_file = '.tmp/vector_debug_test.ndjson'
    Path('.tmp').mkdir(exist_ok=True)
    with open(test_file, 'w') as f:
        for item in test_data:
            f.write(json.dumps(item) + '\n')
    
    # Simple VRL code
    vrl_code = """
# Simple VRL test
if exists(.message) {
    .processed = true
}
._debug = "vector_cli_test"
.
"""
    
    # Create Vector config
    config = {
        'sources': {
            'test_input': {
                'type': 'file',
                'include': [test_file],
                'encoding': {'codec': 'json'},
                'start_at_beginning': True
            }
        },
        'transforms': {
            'test_transform': {
                'type': 'remap',
                'inputs': ['test_input'],
                'source': vrl_code
            }
        },
        'sinks': {
            'test_output': {
                'type': 'console',
                'inputs': ['test_transform'],
                'encoding': {'codec': 'json'}
            }
        }
    }
    
    config_file = '.tmp/vector_debug_config.yaml'
    with open(config_file, 'w') as f:
        yaml.dump(config, f, default_flow_style=False)
    
    print("🔧 TESTING VECTOR CLI VALIDATION")
    print("="*50)
    print(f"Config file: {config_file}")
    print(f"Data file: {test_file}")
    
    # Test Vector validate command
    try:
        env = os.environ.copy()
        env['VECTOR_DATA_DIR'] = '.tmp/vector_debug_data'
        
        print("\n📋 Vector config:")
        with open(config_file, 'r') as f:
            print(f.read())
            
        print("\n🔍 Running: vector validate")
        result = subprocess.run(
            ['vector', 'validate', config_file],
            env=env,
            capture_output=True,
            text=True,
            timeout=10
        )
        
        print(f"\n📊 VALIDATION RESULTS:")
        print(f"Return code: {result.returncode}")
        print(f"STDOUT:\n{result.stdout}")
        print(f"STDERR:\n{result.stderr}")
        
        if result.returncode == 0:
            print("✅ Vector validation PASSED")
            
            # Try running Vector briefly to see if it actually works
            print(f"\n🚀 Testing Vector execution (5 seconds)...")
            run_result = subprocess.run(
                ['vector', '--config', config_file],
                env=env,
                capture_output=True,
                text=True,
                timeout=5
            )
            
            print(f"\n📊 EXECUTION RESULTS:")
            print(f"Return code: {run_result.returncode}")
            print(f"STDOUT:\n{run_result.stdout}")
            print(f"STDERR:\n{run_result.stderr}")
            
        else:
            print("❌ Vector validation FAILED")
            
    except subprocess.TimeoutExpired as e:
        print(f"⏰ Vector execution timed out (expected): {e}")
        print("✅ This suggests Vector is working but running continuously")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # Cleanup
    try:
        os.unlink(config_file)
        os.unlink(test_file)
    except:
        pass

if __name__ == "__main__":
    test_vector_validation()