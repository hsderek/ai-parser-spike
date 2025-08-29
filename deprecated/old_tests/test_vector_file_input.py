#!/usr/bin/env python3
"""
Test what Vector file source actually produces as input to VRL
"""

import subprocess
import yaml
import json
import os
from pathlib import Path

def test_vector_file_input():
    """Test Vector file source input format"""
    
    # Create test JSON data file
    test_file = '.tmp/vector_input_test.ndjson'
    Path('.tmp').mkdir(exist_ok=True)
    with open(test_file, 'w') as f:
        f.write('{"msg": "test log", "priority": 123}\n')
        f.write('{"msg": "another log", "hostname": "server1"}\n')
    
    # Vector config with minimal passthrough VRL  
    vrl_code = """
# Debug: Show what Vector file source produces
.debug_keys = keys(.)
.debug_message_field = .message
.debug_full_event, _ = to_string(.)
."""
    
    config = {
        'data_dir': '.tmp/vector_data',
        'sources': {
            'test_input': {
                'type': 'file',
                'include': [test_file],
                'read_from': 'beginning'
            }
        },
        'transforms': {
            'debug_transform': {
                'type': 'remap',
                'inputs': ['test_input'],
                'source': vrl_code
            }
        },
        'sinks': {
            'debug_output': {
                'type': 'console',
                'inputs': ['debug_transform'],
                'encoding': {'codec': 'json'}
            }
        }
    }
    
    config_file = '.tmp/vector_input_debug.yaml'
    with open(config_file, 'w') as f:
        yaml.dump(config, f, default_flow_style=False)
    
    print("🔍 TESTING VECTOR FILE INPUT FORMAT")
    print("="*50)
    
    try:
        env = os.environ.copy()
        env['VECTOR_DATA_DIR'] = '.tmp'
        
        print("Running Vector for 3 seconds to capture input format...")
        result = subprocess.run(
            ['vector', '--config', config_file],
            env=env,
            capture_output=True,
            text=True,
            timeout=3
        )
        
        print(f"\nVector output:")
        print(result.stdout)
        print(f"\nVector stderr:")
        print(result.stderr)
        
    except subprocess.TimeoutExpired as e:
        print(f"Vector timed out (expected)")
        print(f"STDOUT:\n{e.stdout}")
        print(f"STDERR:\n{e.stderr}")
    except Exception as e:
        print(f"Error: {e}")
    
    # Cleanup
    try:
        os.unlink(config_file)
        os.unlink(test_file)
    except:
        pass

if __name__ == "__main__":
    test_vector_file_input()