#!/usr/bin/env python3
"""
Test Working VRL Generation - First Step

Focus on getting VRL that actually works and produces expected output.
LLM declares expected fields, then we test if Vector CLI output matches.
"""

import os
import sys
import json
import tempfile
import subprocess
import yaml
import time
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dfe_ai_parser_vrl.llm.client import DFELLMClient


def test_working_vrl_generation():
    """Test that LLM can generate VRL that actually works"""
    
    if not os.environ.get('ANTHROPIC_API_KEY'):
        print("❌ ANTHROPIC_API_KEY not set")
        return False
    
    # Test data
    test_logs = """Dec 10 06:55:46 LabSZ sshd[24200]: Invalid user test from 192.168.1.1
Dec 10 06:55:47 LabSZ sshd[24201]: Failed password for admin from 192.168.1.2 port 22 ssh2
Dec 10 06:55:48 LabSZ sshd[24202]: Connection closed by 192.168.1.3 [preauth]"""
    
    print("🎯 Testing Working VRL Generation")
    print("=" * 50)
    print(f"Test logs ({len(test_logs.split())} lines):")
    for i, line in enumerate(test_logs.split('\n'), 1):
        print(f"  {i}. {line}")
    print()
    
    # Step 1: Generate VRL with expected fields
    print("Step 1: LLM generates VRL + expected fields...")
    
    client = DFELLMClient()
    
    # Ask LLM to generate VRL AND declare expected fields
    prompt = f"""Generate VRL parser for SSH logs. Also provide the expected output fields.

CRITICAL VRL SYNTAX RULES:
- Use to_string(.message) ?? "" for type safety
- Use contains() for string matching (NOT includes)  
- Array access must be safe: if length(parts) > 2 then access parts[2]
- NO direct array indexing without bounds checking

SSH Log Data:
```
{test_logs}
```

Return JSON with:
{{"vrl_code": "VRL parser code here", "expected_fields": ["field1", "field2", "field3"]}}

Generate working VRL that extracts SSH events and security fields."""
    
    messages = [{"role": "user", "content": prompt}]
    
    try:
        response = client.completion(messages, max_tokens=2000, temperature=0.3)
        content = response.choices[0].message.content.strip()
        
        # Extract JSON from response
        if content.startswith('{'):
            result = json.loads(content)
        elif '```json' in content:
            start = content.find('```json') + 7
            end = content.find('```', start)
            result = json.loads(content[start:end])
        else:
            print("❌ LLM didn't return JSON format")
            return False
        
        vrl_code = result.get('vrl_code', '')
        expected_fields = result.get('expected_fields', [])
        
        if not vrl_code or not expected_fields:
            print("❌ LLM response missing VRL code or expected fields")
            return False
        
        print(f"✅ LLM generated VRL ({len(vrl_code)} chars)")
        print(f"✅ Expected fields: {expected_fields}")
        print()
        
        # Step 2: Test VRL with Vector CLI
        print("Step 2: Testing VRL with Vector CLI...")
        
        success, events_processed, output_fields = test_vrl_with_vector(
            vrl_code, test_logs, expected_fields
        )
        
        if success:
            print(f"✅ Vector CLI processed {events_processed} events")
            print(f"✅ Output fields: {output_fields}")
            
            # Step 3: Verify expected fields are present
            print()
            print("Step 3: Verifying expected vs actual fields...")
            
            missing_fields = set(expected_fields) - set(output_fields)
            extra_fields = set(output_fields) - set(expected_fields) - {'message'}  # Ignore original message
            
            field_match_rate = len(set(expected_fields) & set(output_fields)) / len(expected_fields)
            
            print(f"Field match rate: {field_match_rate:.1%}")
            if missing_fields:
                print("Missing fields:", list(missing_fields))
            if extra_fields:
                print("Extra fields:", list(extra_fields))
            
            if field_match_rate >= 0.8:  # 80% match required
                print("🎉 SUCCESS! Working VRL with expected field extraction!")
                
                # Save working VRL
                with open('output/first_working_vrl.vrl', 'w') as f:
                    f.write(vrl_code)
                
                with open('output/first_working_fields.json', 'w') as f:
                    json.dump({
                        'expected_fields': expected_fields,
                        'actual_fields': output_fields,
                        'field_match_rate': field_match_rate,
                        'events_processed': events_processed
                    }, f, indent=2)
                
                print("💾 Saved to output/first_working_vrl.vrl")
                return True
            else:
                print(f"❌ Poor field match rate: {field_match_rate:.1%}")
                return False
        else:
            print("❌ Vector CLI failed to process events")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_vrl_with_vector(vrl_code: str, test_logs: str, expected_fields: list):
    """Test VRL with Vector CLI and return results"""
    
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create input file
            input_file = temp_path / "input.json"
            with open(input_file, 'w') as f:
                for line in test_logs.strip().split('\n'):
                    if line.strip():
                        f.write(json.dumps({"message": line}) + '\n')
            
            output_file = temp_path / "output.json"
            
            # Create Vector config using the working pattern
            config = {
                'data_dir': str(temp_path / 'vector_data'),
                'sources': {
                    'test_logs': {
                        'type': 'file',
                        'include': [str(input_file)],
                        'read_from': 'beginning'
                    }
                },
                'transforms': {
                    # 101 transform
                    'flatten_parse': {
                        'type': 'remap',
                        'inputs': ['test_logs'],
                        'source': '. = parse_json(.message) ?? {}'
                    },
                    'flatten_filter': {
                        'type': 'filter',
                        'inputs': ['flatten_parse'],
                        'condition': {
                            'type': 'vrl',
                            'source': '!is_empty(.)'
                        }
                    },
                    # VRL parser
                    'vrl_parser': {
                        'type': 'remap',
                        'inputs': ['flatten_filter'], 
                        'source': vrl_code
                    }
                },
                'sinks': {
                    'output': {
                        'type': 'file',
                        'inputs': ['vrl_parser'],
                        'path': str(output_file),
                        'encoding': {'codec': 'json'}
                    }
                }
            }
            
            config_file = temp_path / 'vector.yaml'
            with open(config_file, 'w') as f:
                yaml.dump(config, f)
            
            # Create data directory
            (temp_path / 'vector_data').mkdir(exist_ok=True)
            
            # Run Vector
            print(f"   Running Vector CLI...")
            env = os.environ.copy()
            env['VECTOR_DATA_DIR'] = str(temp_path / 'vector_data')
            
            result = subprocess.run(
                ['vector', '--config', str(config_file), '--threads', '1'],
                env=env,
                capture_output=True,
                text=True,
                timeout=20
            )
            
            # Check results
            if result.returncode != 0:
                print(f"   Vector failed: {result.stderr[:200]}")
                return False, 0, []
            
            # Count events and extract fields
            events_processed = 0
            all_fields = set()
            
            if output_file.exists():
                with open(output_file, 'r') as f:
                    for line in f:
                        if line.strip():
                            try:
                                event = json.loads(line)
                                events_processed += 1
                                all_fields.update(event.keys())
                            except json.JSONDecodeError:
                                continue
            
            return True, events_processed, list(all_fields)
            
    except subprocess.TimeoutExpired:
        print("   Vector timed out")
        return False, 0, []
    except Exception as e:
        print(f"   Vector test error: {e}")
        return False, 0, []


if __name__ == "__main__":
    success = test_working_vrl_generation()
    if success:
        print("\n🏆 FIRST STEP COMPLETE: Working VRL with expected fields!")
        print("Ready for performance iteration testing.")
        exit(0)
    else:
        print("\n❌ Failed to generate working VRL")
        print("Need to improve VRL generation prompts.")
        exit(1)