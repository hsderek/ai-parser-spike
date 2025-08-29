#!/usr/bin/env python3
"""
Test Iteration Efficiency with All Optimizations

Measures how many iterations are actually needed with:
- Pre-tokenizer
- Local syntax fixes  
- Batch error collection
- 10 iteration budget
"""

import sys
import os
import time
import json
from pathlib import Path
from datetime import datetime
from loguru import logger

# Add src to path
sys.path.append(str(Path(__file__).parent / 'src'))

from vrl_testing_loop_clean import VRLTestingLoop

class IterationTracker:
    """Track iteration metrics"""
    
    def __init__(self):
        self.iterations = []
        self.local_fixes = 0
        self.llm_calls = 0
        self.total_cost = 0.0
        self.start_time = None
        self.end_time = None
        
    def log_iteration(self, iteration_num: int, iteration_type: str, success: bool, cost: float = 0.0):
        """Log an iteration event"""
        self.iterations.append({
            'number': iteration_num,
            'type': iteration_type,  # 'initial', 'local_fix', 'llm_fix'
            'success': success,
            'cost': cost,
            'timestamp': datetime.now().isoformat()
        })
        
        if iteration_type == 'local_fix':
            self.local_fixes += 1
        elif iteration_type in ['initial', 'llm_fix']:
            self.llm_calls += 1
            self.total_cost += cost
    
    def get_summary(self):
        """Get iteration summary"""
        return {
            'total_iterations': len(self.iterations),
            'llm_calls': self.llm_calls,
            'local_fixes': self.local_fixes,
            'total_cost': self.total_cost,
            'average_cost_per_iteration': self.total_cost / len(self.iterations) if self.iterations else 0,
            'duration_seconds': (self.end_time - self.start_time).total_seconds() if self.end_time else 0,
            'successful': any(i['success'] for i in self.iterations),
            'success_at_iteration': next((i['number'] for i in self.iterations if i['success']), None),
            'free_iterations': self.local_fixes,
            'paid_iterations': self.llm_calls
        }

def test_with_metrics():
    """Run VRL generation with detailed metrics"""
    
    # Check for API key
    if not os.environ.get('ANTHROPIC_API_KEY'):
        logger.error("Please set ANTHROPIC_API_KEY environment variable")
        return False
    
    tracker = IterationTracker()
    
    # Test files to try
    test_files = [
        ("samples/large/apache-real.ndjson", "Apache Web Server"),
        ("samples/large/ssh-real.ndjson", "SSH Authentication"),
        ("samples/large/openstack-normal-real.ndjson", "OpenStack"),
    ]
    
    results = []
    
    for file_path, description in test_files:
        if not Path(file_path).exists():
            logger.warning(f"File not found: {file_path}")
            continue
        
        logger.info(f"\n{'='*80}")
        logger.info(f"🧪 TESTING ITERATION EFFICIENCY")
        logger.info(f"Dataset: {description}")
        logger.info(f"File: {file_path}")
        
        # Count samples
        with open(file_path, 'r') as f:
            sample_count = sum(1 for _ in f)
        logger.info(f"Samples: {sample_count:,}")
        logger.info(f"Max Iterations: 10")
        logger.info(f"{'='*80}\n")
        
        # Reset tracker
        tracker = IterationTracker()
        tracker.start_time = datetime.now()
        
        try:
            # Initialize testing loop
            loop = VRLTestingLoop(file_path)
            
            # Hook into the iteration process to track metrics
            original_run = loop.run_with_llm_generated_vrl
            iteration_count = [0]
            
            def tracked_run(vrl_code, iteration):
                iteration_count[0] += 1
                logger.info(f"📍 Iteration {iteration_count[0]}")
                
                # Track as LLM iteration (costs money)
                if iteration == 1:
                    tracker.log_iteration(iteration_count[0], 'initial', False, 0.50)
                else:
                    tracker.log_iteration(iteration_count[0], 'llm_fix', False, 0.50)
                
                result = original_run(vrl_code, iteration)
                
                # Check if this succeeded
                if result:
                    # Update last iteration as successful
                    tracker.iterations[-1]['success'] = True
                    
                return result
            
            # Replace with tracked version
            loop.run_with_llm_generated_vrl = tracked_run
            
            # Also track local fixes
            from vrl_syntax_fixer import apply_local_fixes
            original_apply = apply_local_fixes
            
            def tracked_local_fix(vrl_code, errors):
                fixed_code, was_fixed, metadata = original_apply(vrl_code, errors)
                if was_fixed:
                    iteration_count[0] += 1
                    tracker.log_iteration(iteration_count[0], 'local_fix', False, 0.0)
                    logger.info(f"📍 Iteration {iteration_count[0]} (LOCAL FIX - FREE)")
                return fixed_code, was_fixed, metadata
            
            # Monkey patch for tracking
            import vrl_syntax_fixer
            vrl_syntax_fixer.apply_local_fixes = tracked_local_fix
            
            # Run with all optimizations
            logger.info("🚀 Starting VRL generation with full optimization suite...")
            success = loop.run_automated_llm_generation(
                provider='anthropic',
                max_iterations=10  # High budget
            )
            
            tracker.end_time = datetime.now()
            
            # Get summary
            summary = tracker.get_summary()
            
            # Log detailed results
            logger.info(f"\n{'='*80}")
            logger.info(f"📊 ITERATION METRICS for {description}")
            logger.info(f"{'='*80}")
            
            logger.info(f"\n📈 Iteration Breakdown:")
            logger.info(f"  Total iterations attempted: {summary['total_iterations']}")
            logger.info(f"  LLM calls (paid): {summary['llm_calls']} @ $0.50 each")
            logger.info(f"  Local fixes (free): {summary['local_fixes']} @ $0.00 each")
            logger.info(f"  Success: {'✅ YES' if summary['successful'] else '❌ NO'}")
            if summary['successful']:
                logger.success(f"  Success achieved at iteration: {summary['success_at_iteration']}")
            
            logger.info(f"\n💰 Cost Analysis:")
            logger.info(f"  Total cost: ${summary['total_cost']:.2f}")
            logger.info(f"  Average cost per iteration: ${summary['average_cost_per_iteration']:.2f}")
            logger.info(f"  Money saved by local fixes: ${summary['local_fixes'] * 0.50:.2f}")
            
            logger.info(f"\n⏱️ Performance:")
            logger.info(f"  Total duration: {summary['duration_seconds']:.1f} seconds")
            logger.info(f"  Average per iteration: {summary['duration_seconds'] / summary['total_iterations']:.1f} seconds")
            
            logger.info(f"\n🎯 Efficiency Score:")
            efficiency = (summary['local_fixes'] / summary['total_iterations']) * 100 if summary['total_iterations'] > 0 else 0
            logger.info(f"  Free iteration ratio: {efficiency:.1f}%")
            logger.info(f"  Cost reduction: {efficiency:.1f}% off baseline")
            
            # Show iteration timeline
            logger.info(f"\n📅 Iteration Timeline:")
            for i, iteration in enumerate(tracker.iterations, 1):
                icon = "💰" if iteration['type'] in ['initial', 'llm_fix'] else "🆓"
                status = "✅" if iteration['success'] else "❌"
                logger.info(f"  {i}. {icon} {iteration['type']:12} {status} (${iteration['cost']:.2f})")
            
            results.append({
                'file': description,
                'success': summary['successful'],
                'iterations_needed': summary['success_at_iteration'] or summary['total_iterations'],
                'cost': summary['total_cost'],
                'free_iterations': summary['local_fixes'],
                'efficiency': efficiency
            })
            
        except Exception as e:
            logger.error(f"Error during testing: {e}")
            import traceback
            traceback.print_exc()
            
        # Restore original functions
        loop.run_with_llm_generated_vrl = original_run
        vrl_syntax_fixer.apply_local_fixes = original_apply
        
        # Only test first file for now
        break
    
    # Overall summary
    if results:
        logger.info(f"\n{'='*80}")
        logger.info(f"🏆 OVERALL SUMMARY")
        logger.info(f"{'='*80}")
        
        for result in results:
            logger.info(f"\n{result['file']}:")
            logger.info(f"  Success: {'✅' if result['success'] else '❌'}")
            logger.info(f"  Iterations needed: {result['iterations_needed']}")
            logger.info(f"  Cost: ${result['cost']:.2f}")
            logger.info(f"  Free iterations: {result['free_iterations']} ({result['efficiency']:.1f}%)")
        
        avg_iterations = sum(r['iterations_needed'] for r in results) / len(results)
        avg_cost = sum(r['cost'] for r in results) / len(results)
        avg_efficiency = sum(r['efficiency'] for r in results) / len(results)
        
        logger.info(f"\n📊 Averages:")
        logger.info(f"  Iterations needed: {avg_iterations:.1f}")
        logger.info(f"  Cost per VRL: ${avg_cost:.2f}")
        logger.info(f"  Free iteration ratio: {avg_efficiency:.1f}%")
        
        logger.info(f"\n💡 Insights:")
        if avg_iterations <= 3:
            logger.success("✨ Excellent! Most VRLs succeed within 3 iterations")
        elif avg_iterations <= 5:
            logger.info("👍 Good! VRLs typically succeed within 5 iterations")
        else:
            logger.warning("🤔 Room for improvement - consider enhancing templates")
            
        if avg_efficiency > 50:
            logger.success(f"🎉 Local fixes handle {avg_efficiency:.0f}% of iterations!")
        
    return True

if __name__ == "__main__":
    test_with_metrics()