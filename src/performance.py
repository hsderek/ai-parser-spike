import re
from typing import List, Dict, Tuple, Any
from .config import Config
from .models import ExtractedField


class PerformanceOptimizer:
    def __init__(self, config: Config):
        self.config = config
        
        self.performance_tiers = {
            "tier1_ultra_fast": ["contains", "split", "upcase", "downcase", "length", "slice"],
            "tier2_fast": ["to_string!", "to_int!", "to_float!", "to_bool!"],
            "tier3_moderate": ["parse_json", "md5", "sha2", "parse_timestamp"],
            "tier4_slow": ["match", "parse_regex", "capture"]
        }
    
    def optimize(self, vrl_code: str, fields: List[ExtractedField]) -> str:
        optimized_code = vrl_code
        
        optimized_code = self._optimize_regex_to_string_ops(optimized_code)
        optimized_code = self._optimize_conditionals(optimized_code)
        optimized_code = self._add_early_exits(optimized_code)
        optimized_code = self._optimize_memory_usage(optimized_code)
        
        return optimized_code
    
    def _optimize_regex_to_string_ops(self, vrl_code: str) -> str:
        optimizations = [
            (r'match\([^,]+,\s*r[\'"]ERROR[\'"].*?\)', 'contains(string!(.message), "ERROR")'),
            (r'match\([^,]+,\s*r[\'"]WARN[\'"].*?\)', 'contains(string!(.message), "WARN")'),
            (r'match\([^,]+,\s*r[\'"]INFO[\'"].*?\)', 'contains(string!(.message), "INFO")'),
            (r'match\([^,]+,\s*r[\'"]DEBUG[\'"].*?\)', 'contains(string!(.message), "DEBUG")'),
        ]
        
        optimized = vrl_code
        for pattern, replacement in optimizations:
            optimized = re.sub(pattern, replacement, optimized)
        
        return optimized
    
    def _optimize_conditionals(self, vrl_code: str) -> str:
        lines = vrl_code.split('\n')
        optimized_lines = []
        
        for line in lines:
            if 'if exists(' in line and 'string!' in line:
                field_match = re.search(r'exists\(([^)]+)\)', line)
                if field_match:
                    field_path = field_match.group(1)
                    if 'string!' in line and field_path in line:
                        line = line.replace(f'string!({field_path})', f'string({field_path})')
                        line = line.replace(f'if exists({field_path})', f'if {field_path} != null')
            
            optimized_lines.append(line)
        
        return '\n'.join(optimized_lines)
    
    def _add_early_exits(self, vrl_code: str) -> str:
        if 'message' in vrl_code.lower() or 'msg' in vrl_code.lower():
            early_exit = '''# Early exit optimization - skip processing if no message field
if !exists(.message) && !exists(.msg) && !exists(.log) {
    # Skip expensive processing for events without core message fields
    .parser_skipped = true
}
'''
            return early_exit + vrl_code
        
        return vrl_code
    
    def _optimize_memory_usage(self, vrl_code: str) -> str:
        memory_optimizations = '''
# Memory optimization - remove large temporary fields early
if exists(.raw_data) && length(.raw_data) > 1000 {
    del(.raw_data)
}
'''
        
        return vrl_code + memory_optimizations
    
    def analyze_performance(self, vrl_code: str) -> Dict[str, Any]:
        lines = vrl_code.split('\n')
        function_calls = []
        
        for line in lines:
            for tier, functions in self.performance_tiers.items():
                for func in functions:
                    if func in line and not line.strip().startswith('#'):
                        function_calls.append((func, tier))
        
        tier_counts = {"tier1": 0, "tier2": 0, "tier3": 0, "tier4": 0}
        for func, tier in function_calls:
            if "tier1" in tier:
                tier_counts["tier1"] += 1
            elif "tier2" in tier:
                tier_counts["tier2"] += 1
            elif "tier3" in tier:
                tier_counts["tier3"] += 1
            elif "tier4" in tier:
                tier_counts["tier4"] += 1
        
        estimated_cpu_per_event = (
            tier_counts["tier1"] * 0.003 +
            tier_counts["tier2"] * 0.006 +
            tier_counts["tier3"] * 0.015 +
            tier_counts["tier4"] * 0.100
        )
        
        events_per_cpu_percent = int(1 / max(estimated_cpu_per_event, 0.001))
        
        return {
            "function_calls": function_calls,
            "tier_distribution": tier_counts,
            "estimated_cpu_per_event": estimated_cpu_per_event,
            "estimated_events_per_cpu_percent": events_per_cpu_percent,
            "performance_rating": self._get_performance_rating(events_per_cpu_percent)
        }
    
    def _get_performance_rating(self, events_per_cpu_percent: int) -> str:
        if events_per_cpu_percent >= 300:
            return "excellent"
        elif events_per_cpu_percent >= 150:
            return "good"
        elif events_per_cpu_percent >= 50:
            return "acceptable"
        else:
            return "poor"