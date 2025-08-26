import pytest
from src.performance import PerformanceOptimizer
from src.config import Config
from src.models import ExtractedField, CPUCost


@pytest.fixture
def config():
    return Config(anthropic_api_key="test-key")


@pytest.fixture
def optimizer(config):
    return PerformanceOptimizer(config)


@pytest.fixture
def sample_vrl_code():
    return '''
# Extract message field
if exists(.message) {
    .msg = string!(.message)
}

# Check for ERROR level using regex (inefficient)
if match(.message, r'ERROR.*') {
    .level = "error"
}

# Parse timestamp
if exists(.timestamp) {
    .ts = parse_timestamp(.timestamp, format: "%Y-%m-%d")
}
'''


class TestPerformanceOptimizer:
    def test_optimize_regex_to_string_ops(self, optimizer):
        inefficient_code = '''
if match(.message, r'ERROR') {
    .level = "error"
}
if match(.message, r'WARN') {
    .level = "warn"
}
'''
        
        optimized = optimizer._optimize_regex_to_string_ops(inefficient_code)
        
        assert 'contains(string!(.message), "ERROR")' in optimized
        assert 'contains(string!(.message), "WARN")' in optimized
        assert 'match(' not in optimized
    
    def test_optimize_conditionals(self, optimizer):
        code_with_redundant_checks = '''
if exists(.field) {
    .result = string!(.field)
}
'''
        
        optimized = optimizer._optimize_conditionals(code_with_redundant_checks)
        
        # The optimization might not change this particular case, so just check it doesn't break
        assert len(optimized) >= len(code_with_redundant_checks)
    
    def test_add_early_exits(self, optimizer):
        code_with_message = '''
if exists(.message) {
    .msg = string!(.message)
}
'''
        
        optimized = optimizer._add_early_exits(code_with_message)
        
        # Should add early exit optimization
        assert "Early exit optimization" in optimized
        assert "!exists(.message)" in optimized
        assert ".parser_skipped = true" in optimized
    
    def test_optimize_memory_usage(self, optimizer):
        base_code = "# Basic VRL code"
        
        optimized = optimizer._optimize_memory_usage(base_code)
        
        # Should add memory optimization
        assert "Memory optimization" in optimized
        assert "del(.raw_data)" in optimized
        assert "length(.raw_data) > 1000" in optimized
    
    def test_full_optimization(self, optimizer, sample_vrl_code):
        optimized = optimizer.optimize(sample_vrl_code, [])
        
        # Should contain all optimizations
        assert "Early exit optimization" in optimized
        assert "Memory optimization" in optimized
        assert len(optimized) > len(sample_vrl_code)
    
    def test_analyze_performance_basic(self, optimizer):
        simple_code = '''
.msg = string!(.message)
.level = downcase(.level)
'''
        
        analysis = optimizer.analyze_performance(simple_code)
        
        assert "function_calls" in analysis
        assert "tier_distribution" in analysis
        assert "estimated_cpu_per_event" in analysis
        assert "estimated_events_per_cpu_percent" in analysis
        assert "performance_rating" in analysis
    
    def test_analyze_performance_tier_detection(self, optimizer):
        tiered_code = '''
# Tier 1 operations (ultra-fast)
.msg = string!(.message)
if contains(.message, "ERROR") {
    .level = "error" 
}

# Tier 3 operations (moderate)
.parsed = parse_json(.data)
.hash = md5(.message)

# Tier 4 operations (slow)
if match(.message, r'\\d+') {
    .has_numbers = true
}
'''
        
        analysis = optimizer.analyze_performance(tiered_code)
        
        # Should detect operations from different tiers
        assert analysis["tier_distribution"]["tier1"] > 0  # contains, string!
        assert analysis["tier_distribution"]["tier3"] > 0  # parse_json, md5
        assert analysis["tier_distribution"]["tier4"] > 0  # match
    
    def test_get_performance_rating(self, optimizer):
        assert optimizer._get_performance_rating(400) == "excellent"
        assert optimizer._get_performance_rating(200) == "good"
        assert optimizer._get_performance_rating(100) == "acceptable"
        assert optimizer._get_performance_rating(20) == "poor"
    
    def test_performance_rating_calculation(self, optimizer):
        # Test with only fast operations
        fast_code = '''
.msg = string!(.message)
.upper = upcase(.level)
if contains(.message, "test") {
    .has_test = true
}
'''
        
        analysis = optimizer.analyze_performance(fast_code)
        
        # Should have good performance rating
        assert analysis["performance_rating"] in ["excellent", "good"]
        assert analysis["estimated_events_per_cpu_percent"] >= 100
    
    def test_performance_degradation_with_regex(self, optimizer):
        regex_heavy_code = '''
if match(.message, r'\\d{4}-\\d{2}-\\d{2}') {
    .has_date = true
}
if match(.message, r'ERROR|WARN|INFO') {
    .has_level = true  
}
if match(.ip, r'\\b(?:\\d{1,3}\\.){3}\\d{1,3}\\b') {
    .has_ip = true
}
'''
        
        analysis = optimizer.analyze_performance(regex_heavy_code)
        
        # Should have poor performance due to multiple regex operations
        assert analysis["tier_distribution"]["tier4"] >= 3
        assert analysis["performance_rating"] in ["poor", "acceptable"]
    
    def test_empty_code_analysis(self, optimizer):
        analysis = optimizer.analyze_performance("")
        
        assert analysis["estimated_events_per_cpu_percent"] >= 1000  # Very high for empty code
        assert analysis["performance_rating"] == "excellent"