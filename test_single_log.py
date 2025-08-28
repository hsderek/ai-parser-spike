#!/usr/bin/env python3
"""
Test VRL generation with a single log file
"""

import sys
import os
from pathlib import Path
from loguru import logger

# Add src to path
sys.path.append(str(Path(__file__).parent / 'src'))

from vrl_testing_loop_clean import VRLTestingLoop

def main():
    """Run VRL generation for Apache logs"""
    
    # Check for API key
    if not os.environ.get('ANTHROPIC_API_KEY'):
        logger.error("Please set ANTHROPIC_API_KEY environment variable")
        logger.error("Run: export ANTHROPIC_API_KEY='your-key-here'")
        return False
    
    # Use Apache logs
    file_path = "samples/large/apache-real.ndjson"
    
    if not Path(file_path).exists():
        logger.error(f"File not found: {file_path}")
        return False
    
    logger.info(f"{'='*80}")
    logger.info("Testing VRL Generation with Large Apache Logs")
    logger.info(f"File: {file_path}")
    
    # Count samples
    with open(file_path, 'r') as f:
        sample_count = sum(1 for _ in f)
    logger.info(f"Total samples in file: {sample_count:,}")
    logger.info(f"{'='*80}\n")
    
    try:
        # Initialize testing loop
        logger.info("Initializing VRL Testing Loop...")
        loop = VRLTestingLoop(file_path)
        
        # Run automated generation with optimizations
        logger.info("Starting automated VRL generation with optimizations...")
        logger.info("Provider: Anthropic")
        logger.info("Max iterations: 2")
        logger.info("")
        
        success = loop.run_automated_llm_generation(
            provider='anthropic',
            max_iterations=2
        )
        
        if success:
            logger.success("\n✅ Successfully generated valid VRL!")
            logger.info("Check samples-parsed/ for the generated VRL file")
        else:
            logger.warning("\n❌ Failed to generate valid VRL within 2 iterations")
            
    except Exception as e:
        logger.error(f"\nError during VRL generation: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)