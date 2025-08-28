#!/usr/bin/env python3
"""
Enhanced Sample Optimizer with Smart Selection and Pattern Caching

Implements:
1. Smart sample selection (2-3 examples per pattern)
2. Pattern caching for successful VRL
3. Prompt compression strategies
4. Advanced deduplication
"""

import json
import os
import hashlib
import re
from typing import List, Dict, Any, Optional, Tuple
from collections import defaultdict, Counter
from datetime import datetime
from pathlib import Path
from loguru import logger

class EnhancedOptimizer:
    """Enhanced optimizer with caching and smart selection"""
    
    def __init__(self, cache_dir: str = ".vrl_cache"):
        """Initialize with cache directory"""
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.cache_file = self.cache_dir / "pattern_cache.json"
        self.prompt_cache_file = self.cache_dir / "prompt_cache.json"
        self.pattern_cache = self._load_cache()
        
        # Enhanced pattern detection
        self.pattern_detectors = {
            'cisco-asa': lambda m: '%ASA-' in m,
            'cisco-ios': lambda m: bool(re.search(r'%\w+-\d+-\w+:', m)),
            'fortigate': lambda m: 'devname=' in m and 'srcip=' in m,
            'palo-alto': lambda m: any(x in m for x in ['THREAT', 'TRAFFIC', 'SYSTEM']),
            'juniper': lambda m: any(x in m for x in ['RT_FLOW', 'PFE_FW', 'rpd[']),
            'meraki': lambda m: bool(re.search(r'\d+\.\d+ (MX|MS|MR)\d+', m)),
            'apache': lambda m: bool(re.search(r'\[(error|warn|notice|info|debug)\]', m.lower())),
            'ssh': lambda m: any(x in m.lower() for x in ['sshd[', 'accepted', 'failed password']),
            'openstack': lambda m: any(x in m for x in ['nova', 'neutron', 'glance', 'keystone', 'req-']),
            'windows-event': lambda m: 'EventID=' in m or 'Event ID' in m,
            'linux-audit': lambda m: 'type=AVC' in m or 'type=SYSCALL' in m,
            'cef': lambda m: 'CEF:' in m,
            'leef': lambda m: 'LEEF:' in m,
            'json': lambda m: m.strip().startswith('{') and m.strip().endswith('}'),
            'firewall-generic': lambda m: all(x in m for x in ['src=', 'dst=', 'port']),
            'auth': lambda m: any(x in m.lower() for x in ['login', 'auth', 'password', 'user']),
            'network': lambda m: any(x in m for x in ['MAC:', 'ARP:', 'DHCP']),
            'error': lambda m: 'error' in m.lower() or 'fail' in m.lower(),
            'warning': lambda m: 'warning' in m.lower() or 'warn' in m.lower(),
            'info': lambda m: 'info' in m.lower() or 'notice' in m.lower(),
        }
        
    def _load_cache(self) -> Dict[str, Any]:
        """Load pattern cache from disk"""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'r') as f:
                    return json.load(f)
            except:
                logger.warning("Failed to load cache, starting fresh")
        return {}
    
    def _save_cache(self):
        """Save pattern cache to disk"""
        with open(self.cache_file, 'w') as f:
            json.dump(self.pattern_cache, f, indent=2)
    
    def detect_log_pattern(self, sample: Dict[str, Any]) -> str:
        """Detect the primary log pattern type"""
        msg = sample.get('message', sample.get('msg', ''))
        
        # Check source type first if available
        source = sample.get('source_type', sample.get('source', ''))
        if source:
            return source
        
        # Use pattern detectors
        for pattern_name, detector in self.pattern_detectors.items():
            try:
                if detector(msg):
                    return pattern_name
            except:
                pass
        
        return 'unknown'
    
    def get_cached_vrl(self, log_pattern: str) -> Optional[str]:
        """Get cached VRL for a log pattern if exists"""
        if log_pattern in self.pattern_cache:
            cache_entry = self.pattern_cache[log_pattern]
            # Check if cache is recent (within 7 days)
            if 'timestamp' in cache_entry:
                cached_time = datetime.fromisoformat(cache_entry['timestamp'])
                if (datetime.now() - cached_time).days < 7:
                    logger.info(f"Using cached VRL for pattern: {log_pattern}")
                    return cache_entry.get('vrl_code')
        return None
    
    def cache_successful_vrl(self, log_pattern: str, vrl_code: str, samples: List[Dict]):
        """Cache successful VRL pattern"""
        self.pattern_cache[log_pattern] = {
            'vrl_code': vrl_code,
            'timestamp': datetime.now().isoformat(),
            'sample_count': len(samples),
            'sample_hash': hashlib.md5(json.dumps(samples[:3]).encode()).hexdigest()
        }
        self._save_cache()
        logger.success(f"Cached VRL for pattern: {log_pattern}")
    
    def smart_sample_selection(self, samples: List[Dict[str, Any]], 
                              max_per_pattern: int = 3,
                              max_total: int = 100) -> List[Dict[str, Any]]:
        """
        Smart selection of representative samples
        
        Args:
            samples: All available samples
            max_per_pattern: Maximum samples per detected pattern
            max_total: Maximum total samples to return
        """
        # Group samples by pattern
        pattern_groups = defaultdict(list)
        
        for sample in samples:
            pattern = self.detect_log_pattern(sample)
            pattern_groups[pattern].append(sample)
        
        logger.info(f"Found {len(pattern_groups)} distinct patterns in {len(samples)} samples")
        
        # Select representative samples
        selected = []
        patterns_included = set()
        
        # First pass: ensure each pattern is represented
        for pattern, pattern_samples in pattern_groups.items():
            # Skip if we have cached VRL for this pattern
            if self.get_cached_vrl(pattern):
                logger.info(f"Skipping pattern {pattern} - have cached VRL")
                continue
                
            # Take diverse samples from each pattern
            diverse_samples = self._select_diverse_from_group(pattern_samples, max_per_pattern)
            selected.extend(diverse_samples)
            patterns_included.add(pattern)
            
            if len(selected) >= max_total:
                break
        
        # Second pass: add more samples from complex patterns
        if len(selected) < max_total:
            # Prioritize patterns with more variety
            pattern_complexity = {
                pattern: self._calculate_pattern_complexity(samples)
                for pattern, samples in pattern_groups.items()
                if pattern not in patterns_included
            }
            
            for pattern in sorted(pattern_complexity, key=pattern_complexity.get, reverse=True):
                additional = self._select_diverse_from_group(
                    pattern_groups[pattern], 
                    min(2, max_total - len(selected))
                )
                selected.extend(additional)
                
                if len(selected) >= max_total:
                    break
        
        logger.success(f"Selected {len(selected)} samples covering {len(patterns_included)} patterns")
        return selected[:max_total]
    
    def _select_diverse_from_group(self, samples: List[Dict], max_count: int) -> List[Dict]:
        """Select diverse samples from a group"""
        if len(samples) <= max_count:
            return samples
        
        # Score samples by diversity
        scored = []
        for sample in samples:
            msg = sample.get('message', sample.get('msg', ''))
            score = 0
            
            # Length diversity
            msg_len = len(msg)
            if 100 < msg_len < 500:
                score += 10
            elif msg_len > 1000:
                score += 5
            else:
                score += 3
            
            # Content diversity (special characters, fields)
            score += len(re.findall(r'[=:,]', msg))
            score += len(re.findall(r'\b\w+=[^\s]+', msg)) * 2  # key=value pairs
            
            # Structural elements
            if '{' in msg and '}' in msg:
                score += 5  # JSON-like
            if re.search(r'<\d+>', msg):
                score += 3  # Syslog priority
                
            scored.append((score, sample))
        
        # Sort by score and select top diverse samples
        scored.sort(key=lambda x: x[0], reverse=True)
        
        # Take first, middle, and last to ensure variety
        result = []
        if len(scored) >= 3 and max_count >= 3:
            result.append(scored[0][1])  # Highest score
            result.append(scored[len(scored)//2][1])  # Middle
            result.append(scored[-1][1])  # Lowest score
            
            # Fill remaining slots with high-scoring samples
            for score, sample in scored[1:]:
                if sample not in result and len(result) < max_count:
                    result.append(sample)
        else:
            result = [s[1] for s in scored[:max_count]]
        
        return result
    
    def _calculate_pattern_complexity(self, samples: List[Dict]) -> float:
        """Calculate complexity score for a pattern group"""
        if not samples:
            return 0
        
        # Measure variety in message lengths
        lengths = [len(s.get('message', s.get('msg', ''))) for s in samples]
        length_variance = max(lengths) - min(lengths) if lengths else 0
        
        # Measure unique field combinations
        field_combos = set()
        for sample in samples[:10]:  # Sample first 10
            msg = sample.get('message', sample.get('msg', ''))
            fields = tuple(re.findall(r'\b(\w+)=', msg))
            field_combos.add(fields)
        
        complexity = length_variance / 100 + len(field_combos) * 10
        return complexity
    
    def compress_prompt(self, iteration: int, previous_prompt: str, errors: List[str]) -> str:
        """
        Compress prompt for subsequent iterations
        
        Args:
            iteration: Current iteration number
            previous_prompt: Previous full prompt
            errors: Current errors to fix
        """
        if iteration == 1:
            return previous_prompt  # Use full prompt on first iteration
        
        # For subsequent iterations, create focused prompt
        compressed = []
        
        # Add minimal context
        compressed.append("Continue refining the VRL parser. Focus on fixing these specific errors:")
        compressed.append("")
        
        # Add error-specific guidance
        error_guidance = self._get_error_specific_guidance(errors)
        compressed.extend(error_guidance)
        
        # Add samples only if errors suggest missing patterns
        if any('undefined' in e or 'missing' in e for e in errors):
            compressed.append("\n## Sample data structure reminder:")
            # Extract just first 2 samples from previous prompt
            sample_match = re.search(r'```json\n(\[[\s\S]*?\])\n```', previous_prompt)
            if sample_match:
                samples = json.loads(sample_match.group(1))
                compressed.append(f"```json\n{json.dumps(samples[:2], indent=2)}\n```")
        
        compressed_prompt = '\n'.join(compressed)
        
        # Log compression ratio
        original_len = len(previous_prompt)
        compressed_len = len(compressed_prompt)
        ratio = (1 - compressed_len/original_len) * 100
        logger.info(f"Compressed prompt by {ratio:.1f}% ({original_len} -> {compressed_len} chars)")
        
        return compressed_prompt
    
    def _get_error_specific_guidance(self, errors: List[str]) -> List[str]:
        """Get specific guidance for common VRL errors"""
        guidance = []
        
        error_patterns = {
            'E103': "MUST handle fallible operations with if-else or ?? operator",
            'E110': "Cannot use fallible function in boolean context without handling errors",
            'E651': "Remove unnecessary ?? on infallible operations",
            'undefined': "Check if field exists before accessing: if .field != null { }",
            'type': "Ensure type conversions: to_string(), to_int(), to_float()",
            'abort': "Cannot abort from infallible function - handle the error case",
        }
        
        for error in errors[:5]:  # Focus on top 5 errors
            for pattern, fix in error_patterns.items():
                if pattern in error:
                    guidance.append(f"- {fix}")
                    guidance.append(f"  Error: {error[:200]}")
                    break
        
        return guidance
    
    def get_optimization_stats(self, original: List[Dict], optimized: List[Dict]) -> Dict:
        """Generate detailed optimization statistics"""
        stats = {
            'timestamp': datetime.now().isoformat(),
            'original_count': len(original),
            'optimized_count': len(optimized),
            'reduction_ratio': f"{(1 - len(optimized)/len(original)) * 100:.1f}%",
            'patterns_detected': len(set(self.detect_log_pattern(s) for s in optimized)),
            'cached_patterns': len(self.pattern_cache),
            'cache_hits': sum(1 for s in original if self.get_cached_vrl(self.detect_log_pattern(s))),
        }
        
        # Pattern distribution
        pattern_dist = Counter(self.detect_log_pattern(s) for s in optimized)
        stats['pattern_distribution'] = dict(pattern_dist.most_common(10))
        
        return stats


# Integration helper for backward compatibility
def create_enhanced_optimizer():
    """Factory function to create enhanced optimizer"""
    return EnhancedOptimizer()