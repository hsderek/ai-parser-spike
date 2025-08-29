#!/usr/bin/env python3
"""
Stage 1 Simple Test - Focus on Reliability

Test stage 1 VRL generation with different log types using simple approach.
Fix and amend as we go to improve reliability.
"""

import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dfe_ai_parser_vrl.core.generator import DFEVRLGenerator


def test_log_type(log_file: str, device_type: str, sample_lines: int = 3):
    """Test stage 1 VRL generation for specific log type"""
    
    log_path = Path(log_file)
    if not log_path.exists():
        print(f"❌ {log_file} not found")
        return False
    
    print(f"\n🧪 Testing {device_type.upper()} logs: {log_path.name}")
    print("-" * 50)
    
    # Read sample data
    try:
        with open(log_path, 'r') as f:
            if log_path.suffix == '.ndjson':
                # NDJSON format
                sample_data = ''.join(f.readlines()[:sample_lines])
            else:
                # Raw log format  
                lines = f.readlines()[:sample_lines]
                import json
                sample_data = '\n'.join(json.dumps({"message": line.strip()}) for line in lines if line.strip())
        
        print(f"Sample data ({sample_lines} lines):")
        for i, line in enumerate(sample_data.strip().split('\n'), 1):
            content = json.loads(line) if line.startswith('{') else {"message": line}
            message = content.get('message', line)[:100] + ('...' if len(content.get('message', line)) > 100 else '')
            print(f"  {i}. {message}")
        print()
        
    except Exception as e:
        print(f"❌ Error reading {log_file}: {e}")
        return False
    
    # Test stage 1 VRL generation
    try:
        print("Generating stage 1 VRL...")
        generator = DFEVRLGenerator()
        
        # Use basic generator - no complex performance iteration
        vrl_code, metadata = generator.generate(
            sample_logs=sample_data,
            device_type=device_type,
            validate=True,
            fix_errors=True
        )
        
        print(f"Results:")
        print(f"  Validation passed: {metadata.get('validation_passed', False)}")
        print(f"  Iterations: {metadata.get('iterations', 0)}")
        print(f"  Errors fixed: {metadata.get('errors_fixed', 0)}")
        
        if metadata.get('validation_passed'):
            print(f"✅ {device_type.upper()} SUCCESS!")
            
            # Save working VRL
            output_file = f"output/stage1_{device_type}_working.vrl"
            with open(output_file, 'w') as f:
                f.write(vrl_code)
            
            print(f"💾 Saved to {output_file}")
            print(f"VRL length: {len(vrl_code)} chars")
            
            return True
        else:
            print(f"❌ {device_type.upper()} validation failed")
            return False
            
    except Exception as e:
        print(f"❌ {device_type.upper()} generation error: {e}")
        return False


def main():
    """Test stage 1 across different log types"""
    
    if not os.environ.get('ANTHROPIC_API_KEY'):
        print("❌ ANTHROPIC_API_KEY not set")
        return 1
    
    print("🎯 STAGE 1 RELIABILITY TESTING")
    print("Testing working VRL generation across different log types")
    print("Performance optimization DISABLED - focus on reliability")
    print()
    
    # Test different log types
    test_cases = [
        ("data/input/small/cisco-asa.ndjson", "cisco"),
        ("data/input/SSH.log", "ssh"), 
        ("data/input/Apache.log", "apache"),
        ("data/input/small/fortinet-fortigate.ndjson", "fortinet")
    ]
    
    results = []
    
    for log_file, device_type in test_cases:
        try:
            success = test_log_type(log_file, device_type, sample_lines=3)
            results.append((device_type, success))
        except KeyboardInterrupt:
            print("\n⚠️ Interrupted by user")
            break
        except Exception as e:
            print(f"❌ {device_type} test failed: {e}")
            results.append((device_type, False))
    
    # Summary
    print(f"\n{'='*60}")
    print("🏁 STAGE 1 RELIABILITY SUMMARY")
    print(f"{'='*60}")
    
    successes = [r for r in results if r[1]]
    failures = [r for r in results if not r[1]]
    
    print(f"✅ Successful: {len(successes)}/{len(results)}")
    for device_type, _ in successes:
        print(f"  ✅ {device_type}")
    
    if failures:
        print(f"❌ Failed: {len(failures)}/{len(results)}")
        for device_type, _ in failures:
            print(f"  ❌ {device_type}")
    
    success_rate = len(successes) / len(results) if results else 0
    
    if success_rate >= 0.75:
        print(f"\n🎉 STAGE 1 RELIABLE! {success_rate:.1%} success rate")
        print("Ready to re-enable performance optimization stage")
        return 0
    else:
        print(f"\n⚠️ STAGE 1 NEEDS IMPROVEMENT: {success_rate:.1%} success rate")
        print("Need to fix issues before enabling performance stage")
        return 1


if __name__ == "__main__":
    exit(main())