#!/usr/bin/env python3
"""
Test Pre-Tokenizer with Large Sample Data
"""

import json
import sys
sys.path.append('.')
from pre_tokenizer import PreTokenizer, SampleOptimizer

def test_large_samples():
    """Test pre-tokenizer with large diverse sample set"""
    
    print("=" * 80)
    print("TESTING PRE-TOKENIZER WITH LARGE SAMPLE DATA")
    print("=" * 80)
    
    # Load large sample file
    sample_file = "samples/large/diverse-logs-large.ndjson"
    samples = []
    
    print(f"\n1. Loading samples from {sample_file}...")
    with open(sample_file, 'r') as f:
        for line in f:
            samples.append(json.loads(line.strip()))
    
    print(f"   Loaded {len(samples)} samples")
    
    # Initialize pre-tokenizer with reasonable limit
    print("\n2. Initializing pre-tokenizer...")
    tokenizer = PreTokenizer(
        model="claude-3-opus-20240229",
        max_tokens=50000  # Smaller limit for testing
    )
    
    # Optimize samples
    print("\n3. Optimizing samples for LLM...")
    result = tokenizer.prepare_for_llm(samples)
    
    # Display results
    print("\n4. Optimization Results:")
    print("-" * 40)
    
    stats = result['optimization_stats']
    for key, value in stats.items():
        print(f"   {key}: {value}")
    
    print("\n5. Sample Diversity Check:")
    print("-" * 40)
    
    # Check source distribution in selected samples
    selected_sources = {}
    for sample in result['samples']:
        source = sample.get('source', 'unknown')
        selected_sources[source] = selected_sources.get(source, 0) + 1
    
    print("   Sources in selected samples:")
    for source, count in sorted(selected_sources.items(), key=lambda x: x[1], reverse=True):
        print(f"     {source}: {count}")
    
    # Test the sample optimizer directly
    print("\n6. Testing Sample Optimizer...")
    print("-" * 40)
    
    optimizer = SampleOptimizer()
    
    # Test pattern extraction
    test_sample = samples[0]
    patterns = optimizer.extract_patterns(test_sample)
    print(f"   Patterns in first sample: {patterns}")
    
    # Test deduplication
    deduplicated = optimizer.deduplicate_samples(samples)
    print(f"   Deduplication: {len(samples)} → {len(deduplicated)} samples")
    
    # Test diversity scoring
    diversity = optimizer.calculate_diversity_score(result['samples'])
    print(f"   Diversity score of selected samples: {diversity:.2f}")
    
    print("\n" + "=" * 80)
    print("✅ Pre-tokenizer test complete!")
    print(f"   Ready for LLM processing with {result['count']} optimized samples")
    print(f"   Using {stats['total_tokens']} tokens ({stats['token_utilization']})")
    print("=" * 80)

if __name__ == "__main__":
    test_large_samples()