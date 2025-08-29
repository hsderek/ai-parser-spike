#!/usr/bin/env python3
"""
First Step VRL Iteration - Field Accountability

LLM declares exactly what fields it can extract from the provided sample data,
then we verify Vector CLI output contains those exact fields.
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
from dfe_ai_parser_vrl.core.validator import DFEVRLValidator
from dfe_ai_parser_vrl.core.error_fixer import DFEVRLErrorFixer


def test_first_step_iteration():
    """Test first step iteration with field accountability"""
    
    if not os.environ.get('ANTHROPIC_API_KEY'):
        print("❌ ANTHROPIC_API_KEY not set")
        return False
    
    # Test data - real SSH logs
    test_logs = """Dec 10 06:55:46 LabSZ sshd[24200]: Invalid user test from 192.168.1.1
Dec 10 06:55:47 LabSZ sshd[24201]: Failed password for admin from 192.168.1.2 port 22 ssh2
Dec 10 06:55:48 LabSZ sshd[24202]: Connection closed by 192.168.1.3 [preauth]
Dec 10 07:02:47 LabSZ sshd[24203]: authentication failure; logname= uid=0 euid=0 tty=ssh ruser= rhost=192.168.1.4"""
    
    print("🎯 FIRST STEP VRL ITERATION - Field Accountability")
    print("=" * 60)
    print(f"Sample data ({len(test_logs.split())} lines):")
    for i, line in enumerate(test_logs.split('\n'), 1):
        print(f"  {i}. {line}")
    print()
    
    # Initialize components
    client = DFELLMClient()
    validator = DFEVRLValidator()
    fixer = DFEVRLErrorFixer(client)
    
    # Step 1: LLM analyzes sample data and declares extractable fields
    print("Step 1: LLM analyzes sample data and declares extractable fields...")
    
    analysis_prompt = f"""Analyze this SSH log sample data and declare exactly what fields you can extract.

SAMPLE DATA:
{test_logs}

Look at each log line and identify:
1. What fields are actually present in this specific data
2. What values can be reliably extracted using VRL

Return JSON with:
{{
  "sample_analysis": "Brief analysis of what's in the data",
  "extractable_fields": {{
    "device_type": "Always 'ssh'",
    "event_type": "invalid_user, failed_password, connection_closed, auth_failure", 
    "source_ip": "IP addresses from each log line",
    "username": "Usernames where present"
  }},
  "field_sources": {{
    "source_ip": "from X.X.X.X patterns in logs",
    "username": "from 'Invalid user USERNAME' and 'for USERNAME' patterns"
  }}
}}

Be specific about what THIS sample data contains, not theoretical SSH fields."""
    
    try:
        response = client.completion([{"role": "user", "content": analysis_prompt}], max_tokens=1000, temperature=0.3)
        analysis_content = response.choices[0].message.content.strip()
        
        # Extract JSON
        if '```json' in analysis_content:
            start = analysis_content.find('```json') + 7
            end = analysis_content.find('```', start)
            analysis = json.loads(analysis_content[start:end])
        elif analysis_content.startswith('{'):
            analysis = json.loads(analysis_content)
        else:
            print("❌ LLM didn't return JSON analysis")
            return False
        
        extractable_fields = list(analysis.get('extractable_fields', {}).keys())
        field_sources = analysis.get('field_sources', {})
        
        print(f"✅ Sample analysis: {analysis.get('sample_analysis', 'No analysis')}")
        print(f"✅ Extractable fields: {extractable_fields}")
        print("✅ Field sources:")
        for field, source in field_sources.items():
            print(f"   {field}: {source}")
        print()
        
        # Step 2: LLM generates VRL to extract those specific fields
        print("Step 2: LLM generates VRL to extract declared fields...")
        
        vrl_prompt = f"""Generate VRL code to extract the fields you declared from this SSH data.

SAMPLE DATA:
{test_logs}

FIELDS YOU MUST EXTRACT:
{json.dumps(extractable_fields, indent=2)}

CRITICAL VRL SYNTAX (E630 Prevention):
- Handle fallible operations: message_str = to_string(.message) ?? ""
- Use safe string: contains(message_str, "pattern") 
- NO fallible functions in arguments: contains(to_string(.message), ...) is WRONG

VRL Requirements:
1. Extract ALL declared fields from the sample data
2. Use proper VRL syntax (no E630/E103/E110 errors)
3. Work with 101 transform (parse_json(.message) ?? already applied)

Return only clean VRL code that extracts the declared fields."""
        
        vrl_response = client.completion([{"role": "user", "content": vrl_prompt}], max_tokens=2000, temperature=0.1)
        vrl_code = vrl_response.choices[0].message.content.strip()
        
        # Clean up VRL code (remove markdown)
        if '```vrl' in vrl_code:
            start = vrl_code.find('```vrl') + 6
            end = vrl_code.find('```', start)
            vrl_code = vrl_code[start:end].strip()
        elif '```' in vrl_code:
            start = vrl_code.find('```') + 3
            end = vrl_code.find('```', start)
            vrl_code = vrl_code[start:end].strip()
        
        print(f"✅ Generated VRL ({len(vrl_code)} chars)")
        print()
        
        # Step 3: Iterative fixing until working
        print("Step 3: Iterative fixing until Vector CLI produces output...")
        
        for attempt in range(1, 4):  # Max 3 attempts
            print(f"   Attempt {attempt}: Testing VRL...")
            
            # Test with Vector CLI
            success, events_processed, output_fields, output_data = test_vrl_with_vector_cli(
                vrl_code, test_logs, f"attempt_{attempt}"
            )
            
            if success and events_processed > 0:
                print(f"   ✅ Success! {events_processed}/{len(test_logs.split())} events processed")
                
                # Step 4: Verify declared fields are present
                print()
                print("Step 4: Verifying field accountability...")
                
                missing_fields = set(extractable_fields) - set(output_fields)
                present_fields = set(extractable_fields) & set(output_fields)
                match_rate = len(present_fields) / len(extractable_fields)
                
                print(f"   Declared fields: {extractable_fields}")
                print(f"   Output fields: {output_fields}")
                print(f"   Field match rate: {match_rate:.1%}")
                
                if missing_fields:
                    print(f"   Missing declared fields: {list(missing_fields)}")
                
                if match_rate >= 0.8:  # 80% accountability required
                    print()
                    print("🎉 FIRST STEP SUCCESS!")
                    print(f"   ✅ Working VRL generated")
                    print(f"   ✅ {events_processed} events processed by Vector CLI")  
                    print(f"   ✅ {match_rate:.1%} field accountability achieved")
                    
                    # Save results
                    results = {
                        'vrl_code': vrl_code,
                        'declared_fields': extractable_fields,
                        'actual_fields': output_fields,
                        'events_processed': events_processed,
                        'field_match_rate': match_rate,
                        'sample_output': output_data[:2],  # First 2 events as examples
                        'analysis': analysis
                    }
                    
                    with open('output/first_step_success.json', 'w') as f:
                        json.dump(results, f, indent=2)
                    
                    with open('output/first_step_working.vrl', 'w') as f:
                        f.write(vrl_code)
                    
                    print("   💾 Results saved to output/first_step_success.json")
                    print("   💾 Working VRL saved to output/first_step_working.vrl")
                    print()
                    print("🚀 READY FOR PERFORMANCE ITERATION!")
                    
                    return True
                else:
                    print(f"   ❌ Poor field accountability: {match_rate:.1%}")
                    if attempt < 3:
                        print("   🔧 Will try to fix VRL...")
                        # Could add LLM-based fixing here
                    continue
            else:
                print(f"   ❌ Vector CLI failed: {events_processed} events processed")
                
                if attempt < 3:
                    # Try local fixes
                    print("   🔧 Attempting local fixes...")
                    
                    # Get validation error
                    syntax_valid, syntax_error = validator._validate_with_pyvrl(vrl_code) 
                    if not syntax_valid:
                        fixed_vrl = fixer.fix_locally(vrl_code, syntax_error)
                        if fixed_vrl and fixed_vrl != vrl_code:
                            vrl_code = fixed_vrl
                            print("   ✨ Applied local syntax fix")
                        else:
                            print("   ⚠️ No local fix available")
        
        print("❌ Failed to achieve working VRL after 3 attempts")
        return False
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_vrl_with_vector_cli(vrl_code: str, test_logs: str, test_name: str):
    """Test VRL with Vector CLI using single thread and return detailed results"""
    
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
            data_dir = temp_path / 'vector_data'
            data_dir.mkdir(exist_ok=True)
            
            # Vector config with 101 transform + VRL
            config = {
                'data_dir': str(data_dir),
                'sources': {
                    f'{test_name}_source': {
                        'type': 'file',
                        'include': [str(input_file)],
                        'read_from': 'beginning'
                    }
                },
                'transforms': {
                    # 101 transform
                    f'{test_name}_flatten': {
                        'type': 'remap',
                        'inputs': [f'{test_name}_source'],
                        'source': '. = parse_json(.message) ?? {}'
                    },
                    f'{test_name}_filter': {
                        'type': 'filter',
                        'inputs': [f'{test_name}_flatten'],
                        'condition': {
                            'type': 'vrl',
                            'source': '!is_empty(.)'
                        }
                    },
                    # VRL parser
                    f'{test_name}_vrl': {
                        'type': 'remap',
                        'inputs': [f'{test_name}_filter'],
                        'source': vrl_code
                    }
                },
                'sinks': {
                    f'{test_name}_output': {
                        'type': 'file',
                        'inputs': [f'{test_name}_vrl'],
                        'path': str(output_file),
                        'encoding': {'codec': 'json'}
                    }
                }
            }
            
            config_file = temp_path / 'vector.yaml'
            with open(config_file, 'w') as f:
                yaml.dump(config, f)
            
            # Run Vector CLI with single thread
            env = os.environ.copy()
            env['VECTOR_DATA_DIR'] = str(data_dir)
            
            result = subprocess.run(
                ['vector', '--config', str(config_file), '--threads', '1'],
                env=env,
                capture_output=True,
                text=True,
                timeout=25
            )
            
            if result.returncode != 0:
                print(f"      Vector CLI error: {result.stderr[:300]}")
                return False, 0, [], []
            
            # Analyze output
            events_processed = 0
            output_fields = set()
            output_data = []
            
            if output_file.exists():
                with open(output_file, 'r') as f:
                    for line in f:
                        if line.strip():
                            try:
                                event = json.loads(line)
                                events_processed += 1
                                output_fields.update(event.keys())
                                output_data.append(event)
                            except json.JSONDecodeError:
                                continue
            
            return True, events_processed, list(output_fields), output_data
            
    except subprocess.TimeoutExpired:
        print("      Vector CLI timed out")
        return False, 0, [], []
    except Exception as e:
        print(f"      Vector CLI test error: {e}")
        return False, 0, [], []


def main():
    """Main entry point"""
    print("🚀 First Step VRL Iteration Testing")
    print("Testing LLM field accountability with Vector CLI validation...")
    print()
    
    success = test_first_step_iteration()
    
    if success:
        print("🏆 FIRST STEP COMPLETE!")
        print("Ready to proceed to performance iteration with working VRL.")
        return 0
    else:
        print("❌ First step failed - need to improve VRL generation")
        return 1


if __name__ == "__main__":
    exit(main())