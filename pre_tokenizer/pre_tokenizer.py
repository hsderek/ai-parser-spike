#!/usr/bin/env python3
"""
Pre-Tokenizer for Large Sample Data

Efficiently handles large log samples by:
1. Tokenizing and counting tokens before sending to LLM
2. Intelligent sampling to maximize diversity within token limits
3. Deduplication of similar patterns
4. Priority-based selection of representative samples
"""

import json
import hashlib
from typing import List, Dict, Any, Tuple
from collections import Counter
import random
import tiktoken
from loguru import logger

class PreTokenizer:
    """Intelligent pre-tokenizer for optimizing LLM input"""
    
    def __init__(self, model: str = "claude-3-opus-20240229", max_tokens: int = 150000):
        """
        Initialize pre-tokenizer with model-specific settings
        
        Args:
            model: LLM model name for token counting
            max_tokens: Maximum tokens to use (leaving room for prompts)
        """
        self.model = model
        self.max_tokens = max_tokens
        
        # Use cl100k_base encoding (good approximation for Claude/GPT-4)
        try:
            self.encoder = tiktoken.get_encoding("cl100k_base")
        except:
            # Fallback to GPT-2 encoding if cl100k not available
            self.encoder = tiktoken.get_encoding("gpt2")
            
        logger.info(f"Initialized PreTokenizer for {model} with {max_tokens:,} max tokens")
    
    def count_tokens(self, text: str) -> int:
        """Count tokens in text using appropriate tokenizer"""
        return len(self.encoder.encode(text))
    
    def hash_sample(self, sample: Dict[str, Any]) -> str:
        """Generate hash for sample to detect duplicates"""
        # Focus on message content for deduplication
        msg = sample.get('message', sample.get('msg', ''))
        # Normalize by removing timestamps and IPs for pattern matching
        normalized = msg
        # Remove common variable parts
        import re
        normalized = re.sub(r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}', 'IP', normalized)
        normalized = re.sub(r'\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}', 'TIMESTAMP', normalized)
        normalized = re.sub(r'\d+', 'NUM', normalized)
        
        return hashlib.md5(normalized.encode()).hexdigest()[:8]
    
    def extract_patterns(self, sample: Dict[str, Any]) -> List[str]:
        """Extract key patterns from a sample for diversity scoring"""
        patterns = []
        msg = sample.get('message', sample.get('msg', ''))
        
        # Extract common log patterns
        if '%ASA-' in msg:
            patterns.append('cisco-asa')
        if 'devname=' in msg:
            patterns.append('fortigate')
        if '%SEC-' in msg or '%LINK-' in msg:
            patterns.append('cisco-ios')
        if 'CEF:' in msg:
            patterns.append('cef')
        if 'action=' in msg and 'src=' in msg:
            patterns.append('firewall')
        if 'user=' in msg or 'username=' in msg:
            patterns.append('auth')
        if 'error' in msg.lower():
            patterns.append('error')
        if 'warning' in msg.lower() or 'warn' in msg.lower():
            patterns.append('warning')
            
        return patterns
    
    def optimize_samples(self, samples: List[Dict[str, Any]], 
                         target_tokens: int = None) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Optimize sample selection for maximum diversity within token budget
        
        Args:
            samples: List of all available samples
            target_tokens: Target token count (defaults to self.max_tokens)
            
        Returns:
            Tuple of (selected_samples, statistics)
        """
        if target_tokens is None:
            target_tokens = self.max_tokens
            
        logger.info(f"Optimizing {len(samples)} samples for {target_tokens:,} tokens")
        
        # Phase 1: Deduplication
        seen_hashes = set()
        unique_samples = []
        pattern_counter = Counter()
        
        for sample in samples:
            sample_hash = self.hash_sample(sample)
            if sample_hash not in seen_hashes:
                seen_hashes.add(sample_hash)
                unique_samples.append(sample)
                patterns = self.extract_patterns(sample)
                pattern_counter.update(patterns)
        
        logger.info(f"Reduced to {len(unique_samples)} unique samples from {len(samples)}")
        logger.info(f"Pattern distribution: {dict(pattern_counter.most_common(10))}")
        
        # Phase 2: Priority scoring
        scored_samples = []
        for sample in unique_samples:
            score = 0
            patterns = self.extract_patterns(sample)
            
            # Prioritize diverse patterns
            for pattern in patterns:
                # Inverse frequency scoring - rare patterns get higher scores
                pattern_frequency = pattern_counter[pattern]
                score += 100 / (pattern_frequency + 1)
            
            # Bonus for samples with multiple patterns
            score += len(patterns) * 10
            
            # Length penalty (prefer medium-length samples)
            msg_len = len(sample.get('message', sample.get('msg', '')))
            if 100 < msg_len < 500:
                score += 20
            elif msg_len > 1000:
                score -= 10
                
            scored_samples.append((score, sample))
        
        # Sort by score (highest first)
        scored_samples.sort(key=lambda x: x[0], reverse=True)
        
        # Phase 3: Token-aware selection
        selected_samples = []
        current_tokens = 0
        patterns_seen = set()
        
        # Always include top diverse samples
        for score, sample in scored_samples:
            sample_json = json.dumps(sample)
            sample_tokens = self.count_tokens(sample_json)
            
            if current_tokens + sample_tokens > target_tokens:
                break
                
            selected_samples.append(sample)
            current_tokens += sample_tokens
            patterns_seen.update(self.extract_patterns(sample))
            
            # Stop if we have good pattern coverage
            if len(patterns_seen) >= len(pattern_counter) * 0.8:
                # Fill remaining space with random samples
                remaining_tokens = target_tokens - current_tokens
                for score, sample in random.sample(scored_samples[len(selected_samples):], 
                                                  min(50, len(scored_samples) - len(selected_samples))):
                    sample_json = json.dumps(sample)
                    sample_tokens = self.count_tokens(sample_json)
                    if current_tokens + sample_tokens > target_tokens:
                        break
                    selected_samples.append(sample)
                    current_tokens += sample_tokens
                break
        
        # Generate statistics
        stats = {
            'original_count': len(samples),
            'unique_count': len(unique_samples),
            'selected_count': len(selected_samples),
            'total_tokens': current_tokens,
            'token_utilization': f"{(current_tokens / target_tokens) * 100:.1f}%",
            'patterns_covered': len(patterns_seen),
            'total_patterns': len(pattern_counter),
            'pattern_coverage': f"{(len(patterns_seen) / len(pattern_counter)) * 100:.1f}%" if pattern_counter else "0%",
            'top_patterns': dict(pattern_counter.most_common(5))
        }
        
        logger.success(f"Selected {len(selected_samples)} samples using {current_tokens:,} tokens")
        logger.info(f"Pattern coverage: {stats['pattern_coverage']}")
        
        return selected_samples, stats
    
    def prepare_for_llm(self, samples: List[Dict[str, Any]], 
                       include_stats: bool = True) -> Dict[str, Any]:
        """
        Prepare optimized samples for LLM consumption
        
        Args:
            samples: Raw samples to process
            include_stats: Whether to include optimization statistics
            
        Returns:
            Dictionary with optimized samples and metadata
        """
        optimized_samples, stats = self.optimize_samples(samples)
        
        result = {
            'samples': optimized_samples,
            'count': len(optimized_samples)
        }
        
        if include_stats:
            result['optimization_stats'] = stats
            
        return result


def test_pre_tokenizer():
    """Test the pre-tokenizer with sample data"""
    
    # Create test samples with various patterns
    test_samples = [
        {"message": "2024-01-01 10:00:00 %ASA-6-302016: Built outbound connection"},
        {"message": "2024-01-01 10:00:01 %ASA-6-302016: Built outbound connection"},  # Duplicate pattern
        {"message": "2024-01-01 10:00:02 devname=FG100 action=allow src=192.168.1.1"},
        {"message": "2024-01-01 10:00:03 ERROR: Database connection failed"},
        {"message": "2024-01-01 10:00:04 User admin logged in successfully"},
        {"message": "2024-01-01 10:00:05 WARNING: Disk usage at 85%"},
    ] * 100  # Multiply to create larger dataset
    
    tokenizer = PreTokenizer(max_tokens=5000)
    result = tokenizer.prepare_for_llm(test_samples)
    
    print(json.dumps(result['optimization_stats'], indent=2))
    print(f"Selected {result['count']} samples from {len(test_samples)} original")
    

if __name__ == "__main__":
    test_pre_tokenizer()