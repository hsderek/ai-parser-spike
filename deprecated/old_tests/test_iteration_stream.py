#!/usr/bin/env python3
"""
Streaming Iteration Test - Shows real-time progress
"""

import sys
import os
import time
from pathlib import Path
from datetime import datetime
from loguru import logger

# Add src to path
sys.path.append(str(Path(__file__).parent / 'src'))

def test_stream():
    """Stream the iteration improvements live"""
    
    # Check for API key
    if not os.environ.get('ANTHROPIC_API_KEY'):
        logger.error("Please set ANTHROPIC_API_KEY environment variable")
        return False
    
    logger.info("🎯 STREAMING ITERATION TEST")
    logger.info("SSH samples: 655,147 → optimized → VRL generation")
    logger.info("Expected: E103 → E620 → SUCCESS with local fixes")
    logger.info("="*60)
    
    try:
        from vrl_testing_loop_clean import VRLTestingLoop
        
        # Use SSH logs (good for testing E103 patterns)  
        test_file = "samples/large/ssh-real.ndjson"
        
        if not Path(test_file).exists():
            logger.error(f"File not found: {test_file}")
            return False
        
        logger.info(f"🔧 Initializing pipeline: {test_file}")
        loop = VRLTestingLoop(test_file)
        
        logger.info(f"🚀 Starting automated generation (max 5 iterations)")
        logger.info("Watch for:")
        logger.info("  - Pre-tokenizer: 655K → 3 samples")
        logger.info("  - Model-specific fixes triggering")
        logger.info("  - E103 → E620 → SUCCESS progression")
        
        # Run with timeout and live output
        success = loop.run_automated_llm_generation(
            provider='anthropic',
            max_iterations=5  # Focused test
        )
        
        if success:
            logger.success("🎉 SUCCESS! VRL generated and validated")
            logger.info("Check samples-parsed/ for results")
        else:
            logger.warning("⚠️ Still iterating - this shows the improvement process")
            
        return success
        
    except KeyboardInterrupt:
        logger.info("⏹️ Stopped by user")
        return False
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    logger.info("Starting in 3 seconds... (Ctrl+C to cancel)")
    time.sleep(3)
    test_stream()