#!/usr/bin/env python3
"""
SSH VRL Test with Streaming Monitoring
Tests the new streaming monitoring system with SSH log parsing
"""

import asyncio
import sys
import time
import logging
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from vrl_testing_loop_clean import VRLTestingLoop
from streaming_integration import retrofit_vrl_session_streaming

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(name)s:%(funcName)s:%(lineno)d - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_ssh_with_streaming():
    """Test SSH VRL generation with streaming monitoring"""
    
    print("="*80)
    print("🚀 SSH VRL TEST WITH STREAMING MONITORING")  
    print("="*80)
    print(f"📁 Sample: samples/large/ssh-real.ndjson")
    print(f"🎯 Max Iterations: 10")
    print(f"⏱️ Streaming Timeout: 120s (hang detection: 30s)")
    print("="*80)
    
    try:
        # Initialize VRL testing loop
        logger.info("🔧 Initializing VRL testing loop...")
        loop = VRLTestingLoop('samples/large/ssh-real.ndjson')
        
        # Enable streaming monitoring
        logger.info("📡 Enabling streaming monitoring...")
        retrofit_vrl_session_streaming(loop)
        
        # Set streaming-friendly timeouts
        if hasattr(loop, 'llm_session') and hasattr(loop.llm_session, '_streaming_monitor'):
            loop.llm_session._streaming_monitor.streaming_monitor.timeout_seconds = 120
            loop.llm_session._streaming_monitor.streaming_monitor.hang_detection_seconds = 30
            logger.info("⏱️ Set streaming timeouts: 120s timeout, 30s hang detection")
        
        print("\n🎯 Starting VRL generation with real-time streaming monitoring...")
        print("   📊 You should see live progress updates during API calls")
        print("   🔄 No more waiting 10+ minutes without feedback!")
        print("   ⚡ Automatic hang detection and recovery")
        print()
        
        start_time = time.time()
        
        # Run automated LLM generation with streaming
        success = await loop.run_automated_llm_generation(
            provider='anthropic',
            max_iterations=10
        )
        
        elapsed_time = time.time() - start_time
        
        print("\n" + "="*80)
        if success:
            print("✅ SSH VRL GENERATION SUCCESSFUL!")
            print(f"⏱️ Total time: {elapsed_time:.1f} seconds")
            print(f"📂 Check samples-parsed/ for generated VRL")
        else:
            print("❌ SSH VRL GENERATION FAILED")
            print(f"⏱️ Total time: {elapsed_time:.1f} seconds")
            print("📋 Check logs for detailed error information")
        
        print("="*80)
        
        return success
        
    except Exception as e:
        logger.error(f"❌ SSH streaming test failed: {e}")
        print(f"\n❌ TEST FAILED: {e}")
        return False

async def main():
    """Main test runner"""
    print("🔬 Starting SSH VRL test with streaming monitoring...")
    
    try:
        success = await test_ssh_with_streaming()
        
        if success:
            print("\n🎉 SSH streaming test completed successfully!")
            sys.exit(0)
        else:
            print("\n💥 SSH streaming test failed!")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n⏹️ Test cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    # Run the async main function
    asyncio.run(main())