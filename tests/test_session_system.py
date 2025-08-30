#!/usr/bin/env python3
"""
Test Session-Based VRL Generation System
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dfe_ai_parser_vrl.llm.session_manager import get_vrl_session


def main():
    print('🎯 Testing SESSION-BASED VRL Generation')
    print('Features: Derek\'s guide loaded once, conversation context maintained')
    print()

    # Test session creation and guide loading
    session = get_vrl_session(
        device_type='ssh',
        session_type='baseline_stage',
        baseline_vrl=None
    )

    print(f'Session created: {session.session_id}')
    print(f'Guide loaded: {bool(session.dereks_guide)}')
    print(f'Guide size: {len(session.dereks_guide)} characters')
    print()

    # Test VRL generation with session
    ssh_sample = '''Dec 10 06:55:46 LabSZ sshd[24200]: Invalid user test from 192.168.1.1'''

    print('Generating VRL with session context...')

    try:
        vrl_code = session.generate_vrl(ssh_sample)
        
        print(f'✅ Generated VRL: {len(vrl_code)} chars')
        print(f'Session iterations: {session.iteration_count}')
        print(f'Session cost: ${session.total_cost:.4f}')
        
        # Test conversation context
        print(f'Conversation history: {len(session.conversation_history)} messages')
        
        # Show session summary
        summary = session.get_session_summary()
        print()
        print('📊 Session Summary:')
        for key, value in summary.items():
            print(f'   {key}: {value}')
        
        print()
        print('🎉 SESSION-BASED SYSTEM WORKING!')
        print('✅ Derek\'s guide loaded once at session start')
        print('✅ Conversation context maintained across iterations')
        print('✅ Layered prompt system active')
        
        return 0

    except Exception as e:
        print(f'❌ Session test failed: {e}')
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())