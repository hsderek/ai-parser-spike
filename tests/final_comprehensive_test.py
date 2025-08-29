#!/usr/bin/env python3
"""
Final Comprehensive SSH Test

All enhancements applied:
- 100 iterations max  
- $20 cost threshold
- Enhanced E651 local fixing
- Type safety standard
- Anti-cyclical detection
- Will ONLY report success if working VRL produced
"""

import sys
import time
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dfe_ai_parser_vrl.core.generator import DFEVRLGenerator


def main():
    print('🎯 FINAL COMPREHENSIVE SSH TEST')
    print('=' * 60)
    print('All enhancements applied - 100 iterations, $20 budget')
    print('SUCCESS = working VRL only. No exceptions.')
    print()
    
    generator = DFEVRLGenerator()
    ssh_sample = '''Dec 10 06:55:46 LabSZ sshd[24200]: Invalid user test from 192.168.1.1'''
    
    start_time = time.time()
    
    try:
        vrl_code, metadata = generator.generate(
            sample_logs=ssh_sample,
            device_type='ssh',
            validate=True,
            fix_errors=True
        )
        
        total_time = time.time() - start_time
        success = metadata.get('validation_passed', False)
        
        print()
        print('🏁 COMPREHENSIVE TEST RESULTS:')
        print('=' * 50)
        print(f'Time: {total_time:.1f}s')
        print(f'SUCCESS: {success}')  # This is the only metric that matters
        print(f'Iterations: {metadata.get("iterations", 0)}/100')
        
        if success:
            print()
            print('🎉🎉🎉 ACTUAL SUCCESS! 🎉🎉🎉')
            print('Working VRL produced!')
            
            with open('output/FINAL_SUCCESS.vrl', 'w') as f:
                f.write(vrl_code)
            
            with open('output/final_success.json', 'w') as f:
                json.dump({'success': True, 'iterations': metadata.get('iterations', 0)}, f)
            
            return 0
        else:
            print()
            print('❌ COMPREHENSIVE FAILURE')
            print('Enhanced system could not produce working VRL')
            
            with open('output/final_failure.json', 'w') as f:
                json.dump({'success': False, 'iterations': metadata.get('iterations', 0)}, f)
            
            return 1
    
    except Exception as e:
        print(f'❌ Exception: {e}')
        return 1


if __name__ == "__main__":
    exit(main())