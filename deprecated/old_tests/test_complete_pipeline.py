#!/usr/bin/env python3
"""
Complete End-to-End VRL Testing Pipeline
Demonstrates the full automated workflow from sample logs to optimized VRL parsers
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

from src.vrl_testing_loop_clean import VRLTestingLoop
from loguru import logger


def main():
    """Run complete end-to-end VRL testing pipeline"""
    
    logger.info("🚀 STARTING COMPLETE END-TO-END VRL TESTING PIPELINE")
    logger.info("=" * 80)
    
    # Initialize the testing loop with sample data
    loop = VRLTestingLoop("samples/cisco-ios.ndjson")
    
    print(f"\n📋 PIPELINE CONFIGURATION:")
    print(f"  Sample file: {loop.sample_file}")
    print(f"  Sample count: {len(loop.samples)}")
    print(f"  Output directory: {loop.output_dir}")
    print(f"  Test events: {loop.test_events:,}")
    print(f"  CPU cores: {loop.cpu_info.get('cpu_count_logical', 1)}")
    print(f"  CPU model: {loop.cpu_info.get('model', 'Unknown')[:50]}")
    print(f"  CPU benchmark: {loop.cpu_benchmark_multiplier:.2f}x baseline")
    
    # Step 1: Generate initial VRL candidate
    print(f"\n📝 STEP 1: GENERATING INITIAL VRL CANDIDATE")
    print("-" * 50)
    initial_candidate = loop.generate_initial_vrl()
    loop._log_with_timestamp(f"Generated: {initial_candidate.name}")
    loop._log_with_timestamp(f"Strategy: {initial_candidate.strategy}")
    
    # Step 2: Test with PyVRL (fast validation)
    print(f"\n⚡ STEP 2: FAST VALIDATION WITH PyVRL")
    print("-" * 50)
    pyvrl_success = loop.test_with_pyvrl(initial_candidate)
    if pyvrl_success:
        loop._log_with_timestamp("✅ PyVRL validation PASSED")
        loop._log_with_timestamp(f"New fields: {', '.join(initial_candidate.extracted_fields)}")
    else:
        loop._log_with_timestamp("❌ PyVRL validation FAILED")
        return False
    
    # Step 3: Test with Vector CLI
    print(f"\n🔧 STEP 3: VALIDATION WITH VECTOR CLI")  
    print("-" * 50)
    vector_success = loop.test_with_vector(initial_candidate)
    if vector_success:
        loop._log_with_timestamp("✅ Vector CLI validation PASSED")
    else:
        loop._log_with_timestamp("⚠️  Vector CLI validation had issues (proceeding)")
    
    # Step 4: Performance measurement and baseline
    print(f"\n📊 STEP 4: PERFORMANCE MEASUREMENT & BASELINE")
    print("-" * 50) 
    baseline = loop.measure_performance(initial_candidate)
    loop._log_with_timestamp(f"Baseline established: {baseline}")
    
    # Step 5: Generate alternative candidates (simulated LLM iterations)
    print(f"\n🧠 STEP 5: GENERATING ALTERNATIVE VRL CANDIDATES")
    print("-" * 50)
    
    # Alternative 1: String operations focused
    string_ops_vrl = """
# Optimized String Operations VRL
# Parse JSON from raw input first
. = parse_json!(string!(.message))

# Extract and process fields
if exists(.msg) {
    msg = string!(.msg)
    if contains(msg, "%") {
        .has_cisco_pattern = true
        parts = split(msg, "%")
        if length(parts) > 1 {
            .cisco_section = string!(parts[1])
        }
    }
}
if exists(.hostname) {
    .hostname_normalized = downcase(string!(.hostname))
}
._parser_metadata = {"strategy": "string_ops_optimized", "tier": "tier_s"}
.
"""
    
    from src.vrl_testing_loop_clean import VRLCandidate
    
    string_candidate = VRLCandidate(
        name="string_ops_optimized",
        description="String operations optimized VRL parser",
        vrl_code=string_ops_vrl.strip(),
        strategy="string_optimization"
    )
    
    # Alternative 2: Minimal operations
    minimal_vrl = """
# Ultra-minimal VRL Parser
# Parse JSON from raw input first
. = parse_json!(string!(.message))

# Minimal processing
if exists(.hostname) {
    .hostname_clean = downcase(string!(.hostname))
}
._parser_metadata = {"strategy": "ultra_minimal", "tier": "tier_s_plus"}
.
"""
    
    minimal_candidate = VRLCandidate(
        name="ultra_minimal",
        description="Ultra-minimal VRL parser for maximum performance",
        vrl_code=minimal_vrl.strip(),
        strategy="minimal_optimization"
    )
    
    # Test alternative candidates
    alternatives = [string_candidate, minimal_candidate]
    
    for i, candidate in enumerate(alternatives, 2):
        loop._log_with_timestamp(f"\n🔄 Testing Alternative {i}: {candidate.name}")
        
        # Fast validation
        if loop.test_with_pyvrl(candidate):
            loop._log_with_timestamp(f"✅ {candidate.name} passed PyVRL validation")
            
            # Performance test
            loop.test_with_vector(candidate)
            performance = loop.measure_performance(candidate)
            loop._log_with_timestamp(f"📈 {candidate.name} performance: {performance}")
            
            loop.candidates.append(candidate)
        else:
            loop._log_with_timestamp(f"❌ {candidate.name} failed validation")
    
    # Step 6: A-B testing comparison
    print(f"\n🏁 STEP 6: A-B TESTING PERFORMANCE COMPARISON")
    print("-" * 50)
    best_candidate = loop.compare_candidates()
    
    # Step 7: Save results
    print(f"\n💾 STEP 7: SAVING OPTIMIZED RESULTS")
    print("-" * 50)
    loop.save_results()
    
    # Final summary
    print(f"\n🎯 PIPELINE COMPLETION SUMMARY")
    print("=" * 80)
    if best_candidate:
        vpi = loop._calculate_vrl_performance_index(
            best_candidate.performance_metrics['events_per_cpu_percent']
        )
        events_cpu = int(best_candidate.performance_metrics['events_per_cpu_percent'])
        tier = loop._classify_performance_tier(events_cpu)
        
        loop._log_with_timestamp(f"🏆 WINNING PARSER: {best_candidate.name}")
        loop._log_with_timestamp(f"🎯 VRL Performance Index: {vpi:,}")
        loop._log_with_timestamp(f"📊 Performance Tier: {tier}")
        loop._log_with_timestamp(f"⚡ Hardware Normalized Score: {vpi:,}")
        loop._log_with_timestamp(f"📁 VRL File: samples-parsed/{loop.sample_file.stem}.vrl")
        loop._log_with_timestamp(f"📄 Results File: samples-parsed/{loop.sample_file.stem}.json")
        
        print(f"\n✅ END-TO-END PIPELINE COMPLETED SUCCESSFULLY")
        return True
    else:
        loop._log_with_timestamp("❌ No valid candidates found")
        print(f"\n❌ PIPELINE FAILED")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)