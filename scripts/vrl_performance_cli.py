#!/usr/bin/env python3
"""
VRL Performance Iteration CLI

Command-line interface for running VRL performance iteration tests
with detailed metrics and cost analysis.

Usage:
    python scripts/vrl_performance_cli.py data/input/SSH.tar.gz --device-type ssh --optimize-for throughput
    python scripts/vrl_performance_cli.py data/input/Apache.tar.gz --optimize-for memory --max-iterations 5
"""

import argparse
import os
import sys
from pathlib import Path
from loguru import logger

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dfe_ai_parser_vrl.core.performance import DFEVRLIterativeSession


def main():
    parser = argparse.ArgumentParser(
        description="VRL Performance Iteration Testing",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument('log_file', 
                       help='Path to log file for VRL generation')
    
    parser.add_argument('--device-type', '-d',
                       help='Device type hint (ssh, apache, cisco, etc.)')
    
    parser.add_argument('--optimize-for', 
                       choices=['throughput', 'cpu_efficiency', 'balanced'],
                       default='cpu_efficiency',
                       help='Performance optimization target: cpu_efficiency (events/CPU%) [default], throughput (events/sec), or balanced')
    
    parser.add_argument('--max-iterations', '-i',
                       type=int, default=10,
                       help='Maximum iteration attempts')
    
    parser.add_argument('--cost-threshold', '-c', 
                       type=float, default=5.0,
                       help='Maximum cost threshold in USD')
    
    parser.add_argument('--output-dir', '-o',
                       default='output',
                       help='Output directory for results')
    
    parser.add_argument('--config', 
                       help='Custom configuration file path')
    
    args = parser.parse_args()
    
    # Check environment
    if not os.environ.get('ANTHROPIC_API_KEY'):
        logger.error("❌ ANTHROPIC_API_KEY environment variable not set")
        logger.info("Please set your API key: export ANTHROPIC_API_KEY=your_key_here")
        return 1
    
    # Check log file
    log_path = Path(args.log_file)
    if not log_path.exists():
        logger.error(f"❌ Log file not found: {args.log_file}")
        return 1
    
    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(exist_ok=True)
    
    logger.info(f"🎯 VRL Performance Iteration CLI")
    logger.info(f"   Log file: {args.log_file}")
    logger.info(f"   Device type: {args.device_type or 'auto-detect'}")
    logger.info(f"   Optimize for: {args.optimize_for}")
    logger.info(f"   Max iterations: {args.max_iterations}")
    logger.info(f"   Cost threshold: ${args.cost_threshold}")
    logger.info(f"   Output dir: {args.output_dir}")
    
    try:
        # Initialize session with custom config if provided
        session = DFEVRLIterativeSession(args.config)
        
        # Update session settings from CLI args
        session.max_iterations = args.max_iterations
        session.cost_threshold = args.cost_threshold
        
        # Run performance iteration
        logger.info(f"\n🚀 Starting VRL performance iteration...")
        vrl_code, metrics = session.run_performance_iteration(
            log_file=str(log_path),
            device_type=args.device_type,
            optimize_for=args.optimize_for
        )
        
        # Print detailed summary
        session.print_session_summary(metrics)
        
        # Save outputs
        if metrics['successful'] and vrl_code:
            # Generate filename from log file
            base_name = log_path.stem.replace('.log', '').replace('.tar', '')
            
            # Save VRL code
            vrl_file = output_dir / f"{base_name}_performance.vrl"
            with open(vrl_file, 'w') as f:
                f.write(vrl_code)
            
            # Save metrics
            metrics_file = output_dir / f"{base_name}_metrics.json"
            with open(metrics_file, 'w') as f:
                import json
                json.dump(metrics, f, indent=2, default=str)
            
            logger.success(f"✅ Success! VRL saved to {vrl_file}")
            logger.info(f"📊 Metrics saved to {metrics_file}")
            
            # Performance recommendations
            if metrics['free_iteration_ratio'] > 70:
                logger.success("🎉 Excellent efficiency! Local fixes handled most iterations")
            elif metrics['free_iteration_ratio'] > 40:
                logger.info("👍 Good efficiency with local fixes")
            else:
                logger.warning("⚠️ Low local fix efficiency - consider enhancing error patterns")
            
            return 0
        else:
            logger.error("❌ VRL generation failed")
            logger.info("💡 Try:")
            logger.info("   - Increasing max iterations")
            logger.info("   - Checking log file format")
            logger.info("   - Verifying API key and connectivity")
            return 1
    
    except KeyboardInterrupt:
        logger.warning("⚠️ Interrupted by user")
        return 1
    except Exception as e:
        logger.error(f"❌ Error during VRL generation: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())