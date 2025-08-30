#!/usr/bin/env python3
"""
Generate and Save VRL with Enhanced Session System
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dfe_ai_parser_vrl.llm.session_manager import get_vrl_session


def main():
    print('🎯 Generating VRL with Enhanced Session System')
    print('Will save VRL for verification')
    print()

    # Create session with enhanced Derek's guide
    session = get_vrl_session(
        device_type='ssh',
        session_type='baseline_stage'
    )

    ssh_sample = '''Dec 10 06:55:46 LabSZ sshd[24200]: Invalid user test from 192.168.1.1'''

    print(f'Enhanced guide loaded: {len(session.dereks_guide)} chars')
    print('Sample:', ssh_sample)
    print()

    # Generate VRL
    vrl_code = session.generate_vrl(ssh_sample)

    print(f'Generated VRL: {len(vrl_code)} chars')
    print(f'Session cost: ${session.total_cost:.4f}')

    # Save the VRL for verification
    with open('output/enhanced_session_generated.vrl', 'w') as f:
        f.write(vrl_code)

    print('💾 VRL saved to: output/enhanced_session_generated.vrl')
    print()
    print('VRL Preview (first 20 lines):')
    lines = vrl_code.split('\n')
    for i, line in enumerate(lines[:20], 1):
        print(f'  {i:2}. {line}')

    if len(lines) > 20:
        print(f'     ... and {len(lines) - 20} more lines')
    
    return 0


if __name__ == "__main__":
    exit(main())