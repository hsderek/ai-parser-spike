#!/usr/bin/env python3
"""
Manual Vector test to debug why performance measurement gets no output
"""

import subprocess
import yaml
import json
import os
import time
from pathlib import Path

def test_vector_processing():
    """Test Vector CLI processing manually"""
    
    # Create test data file (absolute path)
    test_file = os.path.abspath('.tmp/vector_manual_test.ndjson')
    Path('.tmp').mkdir(exist_ok=True)
    
    with open(test_file, 'w') as f:
        for i in range(5):
            f.write(json.dumps({"msg": f"test log {i}", "priority": 123 + i}) + '\n')
    
    print(f"Created test file: {test_file}")
    print(f"File exists: {os.path.exists(test_file)}")
    print(f"File size: {os.path.getsize(test_file)} bytes")
    
    # Simple VRL
    vrl_code = """
# Parse JSON from Vector file source input
. = parse_json!(string!(.message))
# Add debug field
.debug_processed = true
."""
    
    # Vector config
    output_file = os.path.abspath('.tmp/vector_manual_output.ndjson')
    config = {
        'data_dir': os.path.abspath('.tmp/vector_data'),
        'sources': {
            'manual_input': {
                'type': 'file',
                'include': [test_file],
                'read_from': 'beginning'
            }
        },
        'transforms': {
            'manual_transform': {
                'type': 'remap',
                'inputs': ['manual_input'],
                'source': vrl_code
            }
        },
        'sinks': {
            'manual_output': {
                'type': 'file',
                'inputs': ['manual_transform'],
                'path': output_file,
                'encoding': {'codec': 'json'}
            }
        }
    }
    
    config_file = os.path.abspath('.tmp/vector_manual_config.yaml')
    os.makedirs(os.path.dirname(config['data_dir']), exist_ok=True)
    
    with open(config_file, 'w') as f:
        yaml.dump(config, f, default_flow_style=False)
    
    print(f"\nVector config:")
    with open(config_file, 'r') as f:
        print(f.read())
    
    print(f"\nExpected output: {output_file}")
    
    try:
        # Run Vector for a short time
        print(f"\nRunning Vector for 3 seconds...")
        result = subprocess.run(
            ['vector', '--config', config_file],
            capture_output=True,
            text=True,
            timeout=3
        )
        
        print(f"Vector return code: {result.returncode}")
        print(f"Vector stdout:\n{result.stdout}")
        print(f"Vector stderr:\n{result.stderr}")
        
    except subprocess.TimeoutExpired as e:
        print(f"Vector timed out (expected)")
        print(f"STDOUT:\n{e.stdout}")
        print(f"STDERR:\n{e.stderr}")
    
    # Check output
    print(f"\nChecking output file: {output_file}")
    print(f"Output exists: {os.path.exists(output_file)}")
    
    if os.path.exists(output_file):
        with open(output_file, 'r') as f:
            content = f.read()
            print(f"Output content ({len(content)} chars):\n{content}")
            
        # Count lines
        with open(output_file, 'r') as f:
            lines = [line.strip() for line in f if line.strip()]
            print(f"Output lines: {len(lines)}")
    else:
        print("No output file created!")
        
        # Check if any files were created
        print(f"\nFiles in .tmp/:")
        for f in Path('.tmp').glob('*'):
            print(f"  {f} ({f.stat().st_size} bytes)")

if __name__ == "__main__":
    test_vector_processing()