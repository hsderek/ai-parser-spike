"""
Sample Optimizer - Intelligent sample selection and diversity maximization
"""

import json
import random
from typing import List, Dict, Any, Set, Tuple
from collections import Counter
import hashlib
import re

class SampleOptimizer:
    """Advanced sample optimization for maximum pattern diversity"""
    
    def __init__(self):
        self.pattern_extractors = {
            'cisco-asa': lambda msg: '%ASA-' in msg,
            'fortigate': lambda msg: 'devname=' in msg and 'srcip=' in msg,
            'cisco-ios': lambda msg: '%SEC-' in msg or '%LINK-' in msg,
            'palo-alto': lambda msg: 'TRAFFIC' in msg or 'THREAT' in msg,
            'checkpoint': lambda msg: 'Check Point' in msg or 'fw1' in msg,
            'sophos': lambda msg: 'device="SFW"' in msg,
            'sonicwall': lambda msg: 'id=firewall' in msg,
            'cef': lambda msg: 'CEF:' in msg,
            'leef': lambda msg: 'LEEF:' in msg,
            'json': lambda msg: msg.strip().startswith('{') and msg.strip().endswith('}'),
            'syslog': lambda msg: re.match(r'<\d+>', msg) is not None,
            'windows-event': lambda msg: 'EventID=' in msg or 'Event ID:' in msg,
            'linux-audit': lambda msg: 'type=AVC' in msg or 'type=SYSCALL' in msg,
            'apache': lambda msg: '] [error]' in msg or '] [warn]' in msg,
            'nginx': lambda msg: 'nginx' in msg.lower(),
            'auth': lambda msg: any(x in msg.lower() for x in ['login', 'auth', 'user', 'password']),
            'network': lambda msg: any(x in msg for x in ['src=', 'dst=', 'sport=', 'dport=']),
            'error': lambda msg: 'error' in msg.lower() or 'fail' in msg.lower(),
            'warning': lambda msg: 'warning' in msg.lower() or 'warn' in msg.lower(),
            'info': lambda msg: 'info' in msg.lower() or 'notice' in msg.lower(),
        }
    
    def extract_patterns(self, sample: Dict[str, Any]) -> Set[str]:
        """Extract all matching patterns from a sample"""
        patterns = set()
        msg = sample.get('message', sample.get('msg', ''))
        
        for pattern_name, detector in self.pattern_extractors.items():
            try:
                if detector(msg):
                    patterns.add(pattern_name)
            except:
                pass
                
        return patterns
    
    def calculate_diversity_score(self, samples: List[Dict[str, Any]]) -> float:
        """Calculate diversity score for a set of samples"""
        all_patterns = Counter()
        for sample in samples:
            patterns = self.extract_patterns(sample)
            all_patterns.update(patterns)
        
        if not all_patterns:
            return 0.0
            
        # Shannon entropy for diversity
        total = sum(all_patterns.values())
        entropy = 0.0
        for count in all_patterns.values():
            if count > 0:
                p = count / total
                entropy -= p * (p if p > 0 else 0)
                
        # Normalize by number of unique patterns
        return entropy * len(all_patterns)
    
    def deduplicate_samples(self, samples: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove duplicate samples based on normalized content"""
        seen_hashes = set()
        unique_samples = []
        
        for sample in samples:
            sample_hash = self.normalize_and_hash(sample)
            if sample_hash not in seen_hashes:
                seen_hashes.add(sample_hash)
                unique_samples.append(sample)
                
        return unique_samples
    
    def normalize_and_hash(self, sample: Dict[str, Any]) -> str:
        """Normalize sample content and generate hash for deduplication"""
        msg = sample.get('message', sample.get('msg', ''))
        
        # Normalize variable parts
        normalized = msg
        # IPs
        normalized = re.sub(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b', 'IP', normalized)
        # Timestamps
        normalized = re.sub(r'\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?', 'TIMESTAMP', normalized)
        # Ports
        normalized = re.sub(r'\b\d{1,5}\b', 'PORT', normalized)
        # UUIDs
        normalized = re.sub(r'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}', 'UUID', normalized)
        # Hashes
        normalized = re.sub(r'\b[0-9a-fA-F]{32,64}\b', 'HASH', normalized)
        
        return hashlib.md5(normalized.encode()).hexdigest()[:16]
    
    def select_diverse_subset(self, samples: List[Dict[str, Any]], 
                             target_count: int) -> List[Dict[str, Any]]:
        """Select most diverse subset of samples"""
        if len(samples) <= target_count:
            return samples
            
        # Start with samples covering unique patterns
        pattern_samples = {}
        for sample in samples:
            patterns = self.extract_patterns(sample)
            for pattern in patterns:
                if pattern not in pattern_samples:
                    pattern_samples[pattern] = []
                pattern_samples[pattern].append(sample)
        
        selected = set()
        selected_list = []
        
        # First pass: ensure each pattern is represented
        for pattern, pattern_sample_list in pattern_samples.items():
            if len(selected_list) >= target_count:
                break
            sample = pattern_sample_list[0]
            sample_id = id(sample)
            if sample_id not in selected:
                selected.add(sample_id)
                selected_list.append(sample)
        
        # Second pass: add samples with multiple patterns
        multi_pattern_samples = [(len(self.extract_patterns(s)), s) for s in samples]
        multi_pattern_samples.sort(reverse=True)
        
        for pattern_count, sample in multi_pattern_samples:
            if len(selected_list) >= target_count:
                break
            sample_id = id(sample)
            if sample_id not in selected:
                selected.add(sample_id)
                selected_list.append(sample)
        
        # Third pass: random selection for remaining slots
        remaining = [s for s in samples if id(s) not in selected]
        random.shuffle(remaining)
        
        for sample in remaining:
            if len(selected_list) >= target_count:
                break
            selected_list.append(sample)
            
        return selected_list