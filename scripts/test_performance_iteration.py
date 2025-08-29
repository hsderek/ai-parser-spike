#!/usr/bin/env python3
"""
VRL Performance Iteration Testing Script

Tests the new performance iteration capabilities of the dfe-ai-parser-vrl module.
Provides detailed metrics and cost analysis for VRL generation efficiency.
"""

import os
import sys
import json
from pathlib import Path
from loguru import logger

# Add src to path for module imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dfe_ai_parser_vrl.core.performance import DFEVRLIterativeSession


def test_performance_iteration():
    """Test VRL performance iteration with real data"""
    
    # Check for required environment
    if not os.environ.get('ANTHROPIC_API_KEY'):
        logger.error("Please set ANTHROPIC_API_KEY environment variable")
        return False
    
    # Test data files
    data_dir = Path("data/input")
    test_files = [
        ("SSH.tar.gz", "SSH Authentication Logs"),
        ("Apache.tar.gz", "Apache Web Server Logs"),
        ("OpenStack.tar.gz", "OpenStack Cloud Logs")
    ]
    
    # Extract test files if they exist as tar.gz
    available_files = []
    for filename, description in test_files:
        file_path = data_dir / filename
        if file_path.exists():
            # For tar.gz files, we'll need to extract or find extracted versions
            if filename.endswith('.tar.gz'):
                # Look for extracted version
                extracted_name = filename.replace('.tar.gz', '.log')
                extracted_path = data_dir / extracted_name
                if extracted_path.exists():
                    available_files.append((str(extracted_path), description))
                else:
                    logger.info(f"Extracting {filename}...")
                    # Extract the tar.gz file
                    import tarfile
                    with tarfile.open(file_path, 'r:gz') as tar:
                        tar.extractall(data_dir)
                    
                    # Find the extracted log file
                    for extracted_file in data_dir.iterdir():
                        if extracted_file.suffix == '.log' and extracted_name.replace('.log', '') in extracted_file.name:
                            available_files.append((str(extracted_file), description))
                            break
            else:
                available_files.append((str(file_path), description))
    
    if not available_files:
        logger.error("No test data files found. Please ensure data/input/ contains log files.")
        return False
    
    # Initialize performance session
    session = DFEVRLIterativeSession()
    
    results = []
    
    # Test each available file
    for log_file, description in available_files[:1]:  # Start with first file
        logger.info(f"\n{'='*80}")
        logger.info(f"🧪 TESTING VRL PERFORMANCE ITERATION")
        logger.info(f"Dataset: {description}")
        logger.info(f"File: {log_file}")
        logger.info(f"{'='*80}\n")
        
        try:
            # Run performance iteration
            vrl_code, metrics = session.run_performance_iteration(
                log_file=log_file,
                optimize_for="balanced"  # throughput, memory, or balanced
            )
            
            # Print detailed results
            session.print_session_summary(metrics)
            
            # Store result
            results.append({
                'dataset': description,
                'file': log_file,
                'success': metrics['successful'],
                'iterations_needed': metrics['success_at_iteration'] or metrics['total_iterations'],
                'total_cost': metrics['total_cost'],
                'free_iterations': metrics['local_fixes'],
                'efficiency_ratio': metrics['free_iteration_ratio'],
                'duration': metrics['duration_seconds']
            })
            
            # Save VRL output if successful
            if metrics['successful'] and vrl_code:
                output_dir = Path("output")
                output_dir.mkdir(exist_ok=True)
                
                # Save VRL code
                vrl_file = output_dir / f"{description.lower().replace(' ', '_')}_performance.vrl"
                with open(vrl_file, 'w') as f:
                    f.write(vrl_code)
                
                # Save metrics
                metrics_file = output_dir / f"{description.lower().replace(' ', '_')}_metrics.json"
                with open(metrics_file, 'w') as f:
                    json.dump(metrics, f, indent=2, default=str)
                
                logger.success(f"💾 Output saved to {output_dir}/")
            
        except Exception as e:
            logger.error(f"Error testing {description}: {e}")
            import traceback
            traceback.print_exc()
            continue
    
    # Overall summary
    if results:
        logger.info(f"\n{'='*80}")
        logger.info(f"🏆 OVERALL PERFORMANCE SUMMARY")
        logger.info(f"{'='*80}")
        
        total_tests = len(results)
        successful_tests = len([r for r in results if r['success']])
        
        logger.info(f"\n📊 Success Rate: {successful_tests}/{total_tests} ({successful_tests/total_tests*100:.1f}%)")
        
        if successful_tests > 0:
            successful_results = [r for r in results if r['success']]
            avg_iterations = sum(r['iterations_needed'] for r in successful_results) / len(successful_results)
            avg_cost = sum(r['total_cost'] for r in successful_results) / len(successful_results)
            avg_efficiency = sum(r['efficiency_ratio'] for r in successful_results) / len(successful_results)
            avg_duration = sum(r['duration'] for r in successful_results) / len(successful_results)
            
            logger.info(f"\n🎯 Average Performance (Successful Tests):")
            logger.info(f"  Iterations needed: {avg_iterations:.1f}")
            logger.info(f"  Cost per VRL: ${avg_cost:.2f}")
            logger.info(f"  Free iteration ratio: {avg_efficiency:.1f}%")
            logger.info(f"  Duration: {avg_duration:.1f} seconds")
            
            # Performance rating
            if avg_iterations <= 3 and avg_cost <= 1.0:
                logger.success("⭐ EXCELLENT: Fast convergence with low cost!")
            elif avg_iterations <= 5 and avg_cost <= 2.0:
                logger.info("👍 GOOD: Reasonable performance")
            elif avg_cost <= 3.0:
                logger.warning("🤔 ACCEPTABLE: Room for optimization")
            else:
                logger.error("❌ POOR: Performance optimization needed")
        
        # Detail each test
        for result in results:
            status_icon = "✅" if result['success'] else "❌"
            logger.info(f"\n{status_icon} {result['dataset']}:")
            logger.info(f"    Iterations: {result['iterations_needed']}")
            logger.info(f"    Cost: ${result['total_cost']:.2f}")
            logger.info(f"    Free iterations: {result['free_iterations']} ({result['efficiency_ratio']:.1f}%)")
            logger.info(f"    Duration: {result['duration']:.1f}s")
    
    return len(results) > 0 and any(r['success'] for r in results)


def main():
    """Main entry point"""
    logger.info("🎯 VRL Performance Iteration Testing")
    logger.info("Testing new performance iteration capabilities...")
    
    success = test_performance_iteration()
    
    if success:
        logger.success("✅ Performance iteration testing completed successfully!")
        return 0
    else:
        logger.error("❌ Performance iteration testing failed!")
        return 1


if __name__ == "__main__":
    exit(main())