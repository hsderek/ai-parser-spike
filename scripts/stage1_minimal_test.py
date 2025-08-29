#!/usr/bin/env python3
"""
Stage 1 Minimal Test - Ultra-Simple Approach

Focus on getting working VRL quickly with minimal complexity.
"""

import os
import sys
import json
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dfe_ai_parser_vrl.llm.client import DFELLMClient


def test_minimal_vrl_generation(log_sample: str, device_type: str):
    """Generate minimal working VRL using simple prompt"""
    
    client = DFELLMClient()
    
    # Ultra-simple prompt focused on reliability
    prompt = f"""Generate minimal working VRL for {device_type} logs that will definitely process events.

CRITICAL RULES:
- Use ONLY: contains(), to_string(), simple field assignments
- NO split() operations, NO array access, NO complex parsing
- Extract 2-3 basic fields maximum
- Use safe field names with {device_type}_ prefix

Sample: {log_sample}

Return JSON: {{"vrl_code": "minimal VRL", "fields": ["field1", "field2"]}}"""

    print(f"🎯 Generating minimal {device_type.upper()} VRL...")
    
    try:
        response = client.completion([{"role": "user", "content": prompt}], max_tokens=800, temperature=0.1)
        content = response.choices[0].message.content.strip()
        
        # Extract JSON
        if '{' in content:
            start = content.find('{')
            end = content.rfind('}') + 1
            result = json.loads(content[start:end])
            
            vrl_code = result.get('vrl_code', '')
            expected_fields = result.get('fields', [])
            
            print(f"✅ Generated VRL ({len(vrl_code)} chars)")
            print(f"✅ Expected fields: {expected_fields}")
            
            return vrl_code, expected_fields
            
    except Exception as e:
        print(f"❌ Generation failed: {e}")
        return None, []


def test_with_vector_minimal(vrl_code: str, log_sample: str, device_type: str):
    """Test minimal VRL with Vector CLI"""
    
    import tempfile
    import subprocess
    import yaml
    
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create simple input  
            input_file = temp_path / "input.json"
            with open(input_file, 'w') as f:
                f.write(json.dumps({"message": log_sample}) + '\n')
            
            output_file = temp_path / "output.json"
            data_dir = temp_path / 'data'
            data_dir.mkdir()
            
            # Minimal Vector config
            config = {
                'data_dir': str(data_dir),
                'sources': {
                    'test': {
                        'type': 'file',
                        'include': [str(input_file)],
                        'read_from': 'beginning'
                    }
                },
                'transforms': {
                    # 101 transform
                    'parse': {
                        'type': 'remap',
                        'inputs': ['test'],
                        'source': '. = parse_json(.message) ?? {}'
                    },
                    'filter': {
                        'type': 'filter', 
                        'inputs': ['parse'],
                        'condition': {'type': 'vrl', 'source': '!is_empty(.)'}
                    },
                    # Minimal VRL
                    'minimal_vrl': {
                        'type': 'remap',
                        'inputs': ['filter'],
                        'source': vrl_code
                    }
                },
                'sinks': {
                    'output': {
                        'type': 'file',
                        'inputs': ['minimal_vrl'],
                        'path': str(output_file),
                        'encoding': {'codec': 'json'}
                    }
                }
            }
            
            config_file = temp_path / 'vector.yaml'
            with open(config_file, 'w') as f:
                yaml.dump(config, f)
            
            # Run Vector
            env = os.environ.copy()
            env['VECTOR_DATA_DIR'] = str(data_dir)
            
            result = subprocess.run(
                ['vector', '--config', str(config_file), '--threads', '1'],
                env=env,
                capture_output=True,
                text=True,
                timeout=15
            )
            
            # Check results
            if result.returncode == 0 and output_file.exists():
                with open(output_file, 'r') as f:
                    output = f.read().strip()
                
                if output:
                    output_event = json.loads(output)
                    output_fields = list(output_event.keys())
                    
                    print(f"✅ Vector CLI success!")
                    print(f"   Input: 1 event → Output: 1 event")
                    print(f"   Fields: {output_fields}")
                    
                    return True, output_event
            
            print("❌ Vector CLI failed or no output")
            return False, {}
            
    except Exception as e:
        print(f"❌ Vector test error: {e}")
        return False, {}


def main():
    """Test minimal stage 1 approach"""
    
    if not os.environ.get('ANTHROPIC_API_KEY'):
        print("❌ ANTHROPIC_API_KEY not set")
        return 1
    
    print("🎯 STAGE 1 MINIMAL RELIABILITY TEST")
    print("Goal: Get working VRL quickly with minimal complexity")
    print()
    
    # Simple test cases
    test_cases = [
        ("Dec 10 06:55:46 LabSZ sshd[24200]: Invalid user test from 192.168.1.1", "ssh"),
        ("192.168.1.1 - - [10/Dec/2023:06:55:46 +0000] \"GET / HTTP/1.1\" 200 1234", "apache")
    ]
    
    results = []
    
    for log_sample, device_type in test_cases:
        print(f"\n📋 Testing {device_type.upper()}")
        print(f"Sample: {log_sample}")
        print()
        
        # Generate minimal VRL
        vrl_code, expected_fields = test_minimal_vrl_generation(log_sample, device_type)
        
        if vrl_code:
            # Test with Vector CLI
            success, output_event = test_with_vector_minimal(vrl_code, log_sample, device_type)
            
            if success:
                print(f"🎉 {device_type.upper()} SUCCESS!")
                
                # Save working result
                with open(f'output/stage1_{device_type}_minimal.vrl', 'w') as f:
                    f.write(vrl_code)
                
                with open(f'output/stage1_{device_type}_result.json', 'w') as f:
                    json.dump({
                        'device_type': device_type,
                        'vrl_code': vrl_code,
                        'expected_fields': expected_fields,
                        'output_event': output_event,
                        'success': True
                    }, f, indent=2)
                
                results.append(True)
            else:
                results.append(False)
        else:
            results.append(False)
    
    # Summary
    success_count = sum(results)
    total_count = len(results)
    
    print(f"\n🏁 STAGE 1 MINIMAL RESULTS")
    print(f"Success: {success_count}/{total_count}")
    
    if success_count == total_count:
        print("🎉 ALL LOG TYPES WORKING!")
        print("Stage 1 minimal approach successful")
        return 0
    else:
        print("⚠️ Some log types failed - need fixes")
        return 1


if __name__ == "__main__":
    exit(main())