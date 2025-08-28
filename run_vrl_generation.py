#!/usr/bin/env python3
"""
Runner script for VRL generation with large log files
"""

import sys
import os
from pathlib import Path
from loguru import logger

# Add src to path
sys.path.append(str(Path(__file__).parent / 'src'))

from vrl_testing_loop_clean import VRLTestingLoop

def main():
    """Run VRL generation with optimizations"""
    
    # Check for API key
    if not os.environ.get('ANTHROPIC_API_KEY'):
        logger.error("Please set ANTHROPIC_API_KEY environment variable")
        return False
    
    # Test files
    test_files = [
        ("samples/large/apache-real.ndjson", "Apache Web Server Logs"),
        ("samples/large/ssh-real.ndjson", "SSH Authentication Logs"),
        ("samples/large/openstack-normal-real.ndjson", "OpenStack Normal Logs"),
    ]
    
    results = []
    
    for file_path, description in test_files:
        if not Path(file_path).exists():
            logger.warning(f"File not found: {file_path}")
            continue
            
        logger.info(f"\n{'='*80}")
        logger.info(f"Testing: {description}")
        logger.info(f"File: {file_path}")
        logger.info(f"{'='*80}")
        
        try:
            # Initialize testing loop
            loop = VRLTestingLoop(file_path)
            
            # Run automated generation with optimizations
            success = loop.run_automated_llm_generation(
                provider='anthropic',
                max_iterations=2
            )
            
            results.append({
                'file': file_path,
                'description': description,
                'success': success
            })
            
            if success:
                logger.success(f"✅ Successfully generated VRL for {description}")
            else:
                logger.warning(f"❌ Failed to generate valid VRL for {description}")
                
        except Exception as e:
            logger.error(f"Error processing {file_path}: {e}")
            results.append({
                'file': file_path,
                'description': description,
                'success': False,
                'error': str(e)
            })
    
    # Summary
    logger.info(f"\n{'='*80}")
    logger.info("SUMMARY")
    logger.info(f"{'='*80}")
    
    successful = sum(1 for r in results if r.get('success'))
    total = len(results)
    
    for result in results:
        status = "✅ SUCCESS" if result.get('success') else "❌ FAILED"
        logger.info(f"{status}: {result['description']}")
        if result.get('error'):
            logger.info(f"  Error: {result['error']}")
    
    logger.info(f"\nTotal: {successful}/{total} successful")
    
    return successful > 0

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)