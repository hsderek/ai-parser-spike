#!/usr/bin/env python3
"""
CLI wrapper for VRL generation
"""

import sys
import argparse
from pathlib import Path

# Add src directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dfe_ai_parser_vrl import DFEVRLGenerator
from loguru import logger


def main():
    parser = argparse.ArgumentParser(description="Generate VRL parser from log samples")
    parser.add_argument("log_file", help="Path to log file (e.g., data/input/SSH.log)")
    parser.add_argument("--device-type", help="Device type (e.g., ssh, apache, cisco)")
    parser.add_argument("--output", help="Output VRL file path")
    parser.add_argument("--no-validate", action="store_true", help="Skip validation")
    parser.add_argument("--no-fix", action="store_true", help="Don't attempt to fix errors")
    parser.add_argument("--config", help="Path to config file")
    parser.add_argument("--platform", help="LLM platform (anthropic, openai, google)")
    parser.add_argument("--capability", help="Model capability (reasoning, balanced, efficient)")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    
    args = parser.parse_args()
    
    # Configure logging
    if args.verbose:
        logger.remove()
        logger.add(sys.stderr, level="DEBUG")
    else:
        logger.remove()
        logger.add(sys.stderr, level="INFO")
    
    # Set environment overrides if provided
    if args.platform:
        import os
        os.environ["VRL_PLATFORM"] = args.platform
    if args.capability:
        import os
        os.environ["VRL_CAPABILITY"] = args.capability
    
    try:
        # Initialize generator
        generator = DFEVRLGenerator(config_path=args.config)
        
        # Generate VRL
        logger.info(f"Generating VRL for: {args.log_file}")
        vrl_code, metadata = generator.generate_from_file(
            args.log_file,
            device_type=args.device_type,
            validate=not args.no_validate,
            fix_errors=not args.no_fix
        )
        
        # Save output
        if args.output:
            output_path = Path(args.output)
            output_path.write_text(vrl_code)
            logger.success(f"VRL saved to: {output_path}")
        else:
            print("\n=== Generated VRL ===\n")
            print(vrl_code)
            print("\n=== Metadata ===")
            print(f"Model: {metadata['model_used']['model']}")
            print(f"Platform: {metadata['model_used']['platform']}")
            print(f"Capability: {metadata['model_used']['capability']}")
            print(f"Iterations: {metadata['iterations']}")
            print(f"Errors fixed: {metadata['errors_fixed']}")
            print(f"Validation: {'PASSED' if metadata['validation_passed'] else 'FAILED'}")
        
        return 0 if metadata['validation_passed'] else 1
        
    except Exception as e:
        logger.error(f"Generation failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())