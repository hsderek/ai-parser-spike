#!/usr/bin/env python3
"""
Quick Iteration Efficiency Test
Tests with smaller samples to measure iteration needs faster
"""

import sys
import os
import time
from pathlib import Path
from datetime import datetime
from loguru import logger

# Add src to path
sys.path.append(str(Path(__file__).parent / 'src'))

from vrl_testing_loop_clean import VRLTestingLoop

def quick_iteration_test():
    """Run quick test to measure iterations needed"""
    
    # Check for API key
    if not os.environ.get('ANTHROPIC_API_KEY'):
        logger.error("Please set ANTHROPIC_API_KEY environment variable")
        return False
    
    # Use SSH logs (smaller dataset for faster testing)
    test_file = "samples/large/ssh-real.ndjson"
    
    if not Path(test_file).exists():
        logger.error(f"File not found: {test_file}")
        return False
    
    # Count samples
    with open(test_file, 'r') as f:
        sample_count = sum(1 for _ in f)
    
    logger.info(f"\n{'='*80}")
    logger.info(f"🚀 QUICK ITERATION EFFICIENCY TEST")
    logger.info(f"File: {test_file}")
    logger.info(f"Samples: {sample_count:,}")
    logger.info(f"Max Iterations: 10")
    logger.info(f"{'='*80}\n")
    
    # Track iterations
    iteration_count = 0
    local_fixes = 0
    llm_calls = 0
    start_time = datetime.now()
    
    try:
        # Initialize testing loop
        loop = VRLTestingLoop(test_file)
        
        # Hook into the iteration process
        original_run = loop.run_with_llm_generated_vrl
        
        def tracked_run(vrl_code, iteration):
            nonlocal iteration_count, llm_calls
            iteration_count += 1
            llm_calls += 1
            logger.info(f"📍 Iteration {iteration_count} - LLM Call #{llm_calls}")
            return original_run(vrl_code, iteration)
        
        loop.run_with_llm_generated_vrl = tracked_run
        
        # Also track local fixes
        from vrl_syntax_fixer import apply_local_fixes
        original_apply = apply_local_fixes
        
        def tracked_local_fix(vrl_code, errors):
            nonlocal iteration_count, local_fixes
            fixed_code, was_fixed, metadata = original_apply(vrl_code, errors)
            if was_fixed:
                iteration_count += 1
                local_fixes += 1
                logger.info(f"📍 Iteration {iteration_count} - LOCAL FIX #{local_fixes} (FREE)")
            return fixed_code, was_fixed, metadata
        
        # Monkey patch for tracking
        import vrl_syntax_fixer
        vrl_syntax_fixer.apply_local_fixes = tracked_local_fix
        
        # Run with optimizations
        logger.info("🎯 Starting VRL generation with all optimizations...")
        success = loop.run_automated_llm_generation(
            provider='anthropic',
            max_iterations=10
        )
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        # Report results
        logger.info(f"\n{'='*80}")
        logger.info(f"📊 ITERATION EFFICIENCY RESULTS")
        logger.info(f"{'='*80}")
        
        logger.info(f"\n✅ Success: {'YES' if success else 'NO'}")
        logger.info(f"⏱️ Total Duration: {duration:.1f} seconds")
        
        logger.info(f"\n📈 Iteration Breakdown:")
        logger.info(f"  Total iterations: {iteration_count}")
        logger.info(f"  LLM calls (💰): {llm_calls} @ ~$0.50 each = ${llm_calls * 0.50:.2f}")
        logger.info(f"  Local fixes (🆓): {local_fixes} @ $0.00 each = $0.00")
        
        logger.info(f"\n💡 Efficiency Metrics:")
        if iteration_count > 0:
            free_ratio = (local_fixes / iteration_count) * 100
            logger.info(f"  Free iteration ratio: {free_ratio:.1f}%")
            logger.info(f"  Cost saved by local fixes: ${local_fixes * 0.50:.2f}")
            logger.info(f"  Average time per iteration: {duration / iteration_count:.1f} seconds")
        
        logger.info(f"\n🎯 Conclusion:")
        if iteration_count <= 3:
            logger.success("✨ Excellent! VRL generated within 3 iterations")
        elif iteration_count <= 5:
            logger.info("👍 Good! VRL generated within 5 iterations")
        else:
            logger.warning(f"🤔 Took {iteration_count} iterations - room for improvement")
        
        # Restore original functions
        loop.run_with_llm_generated_vrl = original_run
        vrl_syntax_fixer.apply_local_fixes = original_apply
        
        return success
        
    except KeyboardInterrupt:
        logger.warning("\n⚠️ Test interrupted by user")
        return False
    except Exception as e:
        logger.error(f"Error during testing: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    quick_iteration_test()