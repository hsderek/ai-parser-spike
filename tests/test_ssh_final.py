#!/usr/bin/env python3
"""
Final SSH Test with Type Safety Standard
No timeout interference - let it run to completion
"""

import sys
import time
import json
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dfe_ai_parser_vrl.core.generator import DFEVRLGenerator


def main():
    """Final SSH test with type safety standard"""
    
    print('🎯 FINAL SSH TEST - MANDATORY TYPE SAFETY')
    print('=' * 60)
    print('Testing if type safety pattern results in working VRL')
    print('Target: validation_passed=True within 10 iterations')
    print()
    
    generator = DFEVRLGenerator()
    
    ssh_sample = '''Dec 10 06:55:46 LabSZ sshd[24200]: Invalid user test from 192.168.1.1'''
    
    print('SSH sample:', ssh_sample)
    print()
    print('Enhanced features active:')
    print('  ✅ Mandatory type safety pattern')
    print('  ✅ Anti-cyclical iteration history')
    print('  ✅ Pattern blacklisting')
    print('  ✅ Vector CLI integration')
    print()
    
    start_time = time.time()
    
    try:
        print('🚀 Starting SSH VRL generation...')
        
        vrl_code, metadata = generator.generate(
            sample_logs=ssh_sample,
            device_type='ssh',
            validate=True,
            fix_errors=True
        )
        
        total_time = time.time() - start_time
        success = metadata.get('validation_passed', False)
        iterations = metadata.get('iterations', 0)
        fixes = metadata.get('errors_fixed', 0)
        
        print()
        print('🏁 FINAL RESULTS:')
        print('=' * 40)
        print(f'⏱️  Time: {total_time:.1f} seconds')
        print(f'✅ Success: {success}')
        print(f'🔄 Iterations: {iterations}/10')
        print(f'🔧 Fixes: {fixes}')
        print(f'📝 VRL length: {len(vrl_code)} chars')
        
        if success:
            print()
            print('🎉 ACTUAL SUCCESS!')
            print('✅ Type safety standard worked!')
            print('✅ Working VRL achieved!')
            
            # Save success files
            with open('output/SSH_FINAL_SUCCESS.vrl', 'w') as f:
                f.write(vrl_code)
            
            with open('output/ssh_final_success.json', 'w') as f:
                json.dump({
                    'validation_passed': True,
                    'iterations_used': iterations,
                    'total_time': total_time,
                    'fixes_applied': fixes,
                    'vrl_length': len(vrl_code),
                    'type_safety_success': True
                }, f, indent=2)
            
            print('💾 Success files saved!')
            print()
            print('🚀 READY FOR MULTI-LOG TESTING!')
            
            return 0
            
        else:
            print()
            print('❌ FAILED')
            
            if iterations >= 10:
                print('❌ Hit 10 iteration limit')
                print('Type safety not sufficient for this complexity')
            else:
                print(f'❌ Stopped at iteration {iterations}')
                print('Encountered non-recoverable issue')
            
            # Save failure analysis
            with open('output/ssh_final_failure.json', 'w') as f:
                json.dump({
                    'validation_passed': False,
                    'iterations_used': iterations,
                    'total_time': total_time,
                    'iteration_history': metadata.get('iteration_history', []),
                    'error_progression': metadata.get('error_progression', []),
                    'type_safety_insufficient': True
                }, f, indent=2)
            
            return 1
    
    except Exception as e:
        elapsed = time.time() - start_time
        print(f'❌ ERROR after {elapsed:.1f}s: {e}')
        
        with open('output/ssh_final_error.json', 'w') as f:
            json.dump({
                'error': str(e),
                'elapsed_seconds': elapsed,
                'test_failed': True
            }, f, indent=2)
        
        return 1


if __name__ == "__main__":
    exit(main())