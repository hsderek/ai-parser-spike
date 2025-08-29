#!/usr/bin/env python3
"""
Focused Success Test - Get working VRL quickly

Uses lessons learned to get to success faster.
"""

import sys
import os
from pathlib import Path

sys.path.append(str(Path(__file__).parent / 'src'))

def test_focused():
    """Focus on getting working VRL"""
    
    if not os.environ.get('ANTHROPIC_API_KEY'):
        print("❌ Please set ANTHROPIC_API_KEY environment variable")
        return False
    
    print("🎯 FOCUSED SUCCESS TEST")
    print("Goal: Get working VRL in 3 iterations max")
    print("Strategy: Use all optimizations + shorter iteration cycles")
    print("="*60)
    
    try:
        from vrl_testing_loop_clean import VRLTestingLoop
        
        # Try Apache first (smaller than SSH)
        test_files = [
            ("samples/large/apache-real.ndjson", "Apache Web Server"),
            ("samples/large/ssh-real.ndjson", "SSH Authentication"),
        ]
        
        for test_file, description in test_files:
            if not Path(test_file).exists():
                print(f"⚠️ Skipping {test_file} (not found)")
                continue
                
            print(f"\n🔧 Testing: {description}")
            print(f"File: {test_file}")
            
            # Count samples
            with open(test_file, 'r') as f:
                sample_count = sum(1 for _ in f)
            print(f"Samples: {sample_count:,}")
            
            # Initialize with all optimizations
            loop = VRLTestingLoop(test_file)
            
            print(f"🚀 Running with 3-iteration limit...")
            start_time = time.time()
            
            # Run with tight iteration limit for faster results
            success = loop.run_automated_llm_generation(
                provider='anthropic',
                max_iterations=3  # Short cycle for faster results
            )
            
            end_time = time.time()
            duration = end_time - start_time
            
            print(f"⏱️ Duration: {duration:.1f} seconds")
            
            if success:
                print(f"🎉 SUCCESS! Generated working VRL for {description}")
                print(f"Check samples-parsed/ for results")
                
                # Show what we generated
                vrl_files = list(Path("samples-parsed").glob("*.vrl"))
                if vrl_files:
                    latest_vrl = max(vrl_files, key=lambda x: x.stat().st_mtime)
                    print(f"📄 Latest VRL: {latest_vrl}")
                    
                return True
            else:
                print(f"⚠️ Still working on {description} - trying next file")
                continue
        
        print("❌ No success in focused test - need more iteration improvements")
        return False
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    import time
    test_focused()