#!/usr/bin/env python3
"""
Test the 3-file output generation:
1. <basename>.vrl - The optimized VRL code
2. <basename>.json - Transformed sample data via Vector CLI 
3. <basename>-rest.json - REST API formatted results
"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent / "src"))

from vrl_testing_loop_clean import VRLTestingLoop


def main():
    print("=" * 80)
    print("TESTING 3-FILE OUTPUT GENERATION")
    print("=" * 80)
    
    # Initialize VRL testing loop with Cisco sample
    loop = VRLTestingLoop("samples/cisco-ios.ndjson")
    
    print("\n📋 Testing simple VRL with 3-file output...")
    
    # Test simple VRL that should work
    simple_vrl = """
# Simple VRL parser for Cisco IOS
. = parse_json!(string!(.message))

# Extract key syslog fields if they exist
if exists(.syslog) {
    .parsed_facility = string!(.syslog.facility) 
    .parsed_severity = string!(.syslog.severity)
    .parsed_mnemonic = string!(.syslog.mnemonic)
}

# Add parser metadata
._parser_metadata = {
    "parser_version": "1.0.0",
    "parser_type": "cisco_ios_simple", 
    "strategy": "json_parse_with_syslog_extraction",
    "timestamp": now()
}

# Return the event
.
"""
    
    # Run the VRL testing loop
    success = loop.run_with_llm_generated_vrl(simple_vrl, 1)
    
    if success:
        print("\n✅ VRL testing completed successfully!")
        
        # Check what files were generated
        base_name = "cisco-ios"
        output_dir = Path("samples-parsed")
        
        expected_files = [
            f"{base_name}.vrl",
            f"{base_name}.json", 
            f"{base_name}-rest.json"
        ]
        
        print(f"\n📁 Checking output files in {output_dir}:")
        for filename in expected_files:
            file_path = output_dir / filename
            if file_path.exists():
                file_size = file_path.stat().st_size
                print(f"   ✅ {filename} ({file_size} bytes)")
                
                # Show preview of each file
                with open(file_path, 'r') as f:
                    content = f.read()
                    preview = content[:200] + "..." if len(content) > 200 else content
                    print(f"      Preview: {preview}")
            else:
                print(f"   ❌ {filename} - NOT FOUND")
        
        # Show detailed results
        print(f"\n📊 VRL Testing Results:")
        if loop.best_candidate:
            print(f"   Name: {loop.best_candidate.name}")
            print(f"   Strategy: {loop.best_candidate.strategy}")
            print(f"   PyVRL Valid: {loop.best_candidate.validated_pyvrl}")
            print(f"   Vector Valid: {loop.best_candidate.validated_vector}")
            print(f"   Extracted Fields: {', '.join(loop.best_candidate.extracted_fields)}")
            print(f"   Performance: {loop.best_candidate.performance_metrics.get('events_per_cpu_percent', 0):.0f} events/CPU%")
        
    else:
        print("\n❌ VRL testing failed!")
        if loop.candidates:
            latest = loop.candidates[-1]
            print(f"   Errors: {', '.join(latest.errors)}")
    
    print("\n" + "=" * 80)
    print("3-FILE OUTPUT TEST COMPLETED")
    print("=" * 80)


if __name__ == "__main__":
    main()