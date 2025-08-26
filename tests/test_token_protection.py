#!/usr/bin/env python3
"""
Test suite for LLM token protection and smart sampling
"""
import pytest
import json
from unittest.mock import patch, MagicMock

from src.llm_client import LLMClient
from src.config import Config
from src.models import SampleData


class TestTokenProtection:
    """Test LLM token protection and smart sampling features"""
    
    @pytest.fixture
    def config(self):
        """Create test configuration"""
        return Config(anthropic_api_key="test-key", llm_model_preference="sonnet")
    
    @pytest.fixture
    def llm_client(self, config):
        """Create LLM client for testing"""
        return LLMClient(config)
    
    def test_token_estimation(self, llm_client):
        """Test token count estimation"""
        short_text = "Hello world"
        long_text = "This is a much longer text that should result in more tokens being estimated"
        
        short_tokens = llm_client._estimate_token_count(short_text)
        long_tokens = llm_client._estimate_token_count(long_text)
        
        assert short_tokens < long_tokens
        assert short_tokens > 0
        assert long_tokens > 0
        
        # Rough check: should be approximately 1 token per 4 characters
        expected_short = max(1, len(short_text) // 4)
        expected_long = max(1, len(long_text) // 4)
        
        assert short_tokens == expected_short
        assert long_tokens == expected_long
    
    def test_model_limits_detection(self, llm_client):
        """Test that model limits are correctly set"""
        assert 'context_tokens' in llm_client.model_limits
        assert 'output_tokens' in llm_client.model_limits
        assert llm_client.model_limits['context_tokens'] > 0
        assert llm_client.model_limits['output_tokens'] > 0
        
        # Should be using Claude Opus 4 limits (200k context, 32k output)
        assert llm_client.model_limits['context_tokens'] == 200000
    
    def test_smart_sampling_no_sampling_needed(self, llm_client):
        """Test smart sampling when no sampling is needed"""
        small_sample = SampleData(
            original_sample='{"field1": "value1", "field2": "value2"}',
            field_analysis={},
            data_source_hints=[],
            common_patterns=[]
        )
        
        # Large target should not trigger sampling
        result = llm_client._smart_sample_data(small_sample, 10000)
        
        assert result.original_sample == small_sample.original_sample
    
    def test_smart_sampling_with_large_data(self, llm_client):
        """Test smart sampling with data that exceeds token limits"""
        # Create large sample data
        large_objects = []
        for i in range(100):
            obj = {
                "timestamp": f"2025-01-01T10:{i:02d}:00Z",
                "hostname": f"server-{i:02d}",
                "message": f"This is a long message with lots of details about event {i} " * 10,
                "level": "INFO",
                "process": f"app-{i % 5}",
                "extra_field_1": f"value_{i}_1",
                "extra_field_2": f"value_{i}_2",
                "extra_field_3": f"value_{i}_3"
            }
            large_objects.append(obj)
        
        large_sample_text = '\n'.join(json.dumps(obj) for obj in large_objects)
        sample_data = SampleData(
            original_sample=large_sample_text,
            field_analysis={},
            data_source_hints=[],
            common_patterns=[]
        )
        
        # Small target should trigger sampling
        result = llm_client._smart_sample_data(sample_data, 1000)  # Small target
        
        # Should be smaller than original
        assert len(result.original_sample) < len(sample_data.original_sample)
        
        # Should still be valid JSON lines
        result_lines = [line.strip() for line in result.original_sample.strip().split('\n')]
        for line in result_lines:
            if line:
                parsed_obj = json.loads(line)  # Should not raise exception
                assert isinstance(parsed_obj, dict)
                assert "timestamp" in parsed_obj  # Should preserve key fields
    
    def test_smart_sampling_preserves_diversity(self, llm_client):
        """Test that smart sampling preserves field diversity"""
        # Create samples with different field patterns
        diverse_objects = [
            {"type": "login", "user": "alice", "timestamp": "2025-01-01T10:00:00Z"},
            {"type": "logout", "user": "bob", "session_duration": 3600, "timestamp": "2025-01-01T10:01:00Z"},
            {"type": "error", "error_code": "E001", "message": "Database timeout", "timestamp": "2025-01-01T10:02:00Z"},
            {"type": "warning", "warning_code": "W123", "component": "auth", "timestamp": "2025-01-01T10:03:00Z"},
            {"type": "info", "module": "cache", "cache_hit_ratio": 0.95, "timestamp": "2025-01-01T10:04:00Z"},
        ]
        
        # Duplicate to create larger dataset
        large_objects = diverse_objects * 20  # 100 objects total
        
        large_sample_text = '\n'.join(json.dumps(obj) for obj in large_objects)
        sample_data = SampleData(
            original_sample=large_sample_text,
            field_analysis={},
            data_source_hints=[],
            common_patterns=[]
        )
        
        # Sample down significantly
        result = llm_client._smart_sample_data(sample_data, 500)
        
        # Parse sampled results
        result_lines = [line.strip() for line in result.original_sample.strip().split('\n')]
        sampled_objects = [json.loads(line) for line in result_lines if line]
        
        # Should have preserved some diversity in 'type' field
        sampled_types = set(obj.get('type') for obj in sampled_objects)
        original_types = set(obj.get('type') for obj in diverse_objects)
        
        # Should preserve most or all unique types despite sampling
        preserved_ratio = len(sampled_types) / len(original_types)
        assert preserved_ratio >= 0.6  # At least 60% of unique types preserved
    
    def test_aggressive_sampling_detection(self, llm_client):
        """Test detection of when aggressive sampling should be applied"""
        # Initially should not apply aggressive sampling
        assert not llm_client._should_apply_aggressive_sampling()
        
        # Simulate high token usage
        llm_client.usage.total_tokens = int(llm_client.model_limits['context_tokens'] * 0.8)
        
        # Should now trigger aggressive sampling
        assert llm_client._should_apply_aggressive_sampling()
    
    def test_token_limit_header_parsing(self, llm_client):
        """Test parsing of rate limit headers from API responses"""
        # Mock response headers
        test_headers = {
            'anthropic-ratelimit-tokens-limit': '200000',
            'anthropic-ratelimit-tokens-remaining': '150000'
        }
        
        # Mock usage object
        mock_usage = MagicMock()
        mock_usage.input_tokens = 1000
        mock_usage.output_tokens = 500
        
        initial_limit = llm_client.model_limits['context_tokens']
        
        # Track usage with headers
        llm_client._track_usage(mock_usage, test_headers)
        
        # Usage should be updated
        assert llm_client.usage.input_tokens == 1000
        assert llm_client.usage.output_tokens == 500
        assert llm_client.usage.total_tokens == 1500
        
        # Model limits should remain the same in this case (same as expected)
        assert llm_client.model_limits['context_tokens'] == initial_limit
    
    def test_token_limit_update_from_headers(self, llm_client):
        """Test updating model limits when API returns different limits"""
        # Mock response headers with different limit
        test_headers = {
            'anthropic-ratelimit-tokens-limit': '100000',  # Different from default 200k
            'anthropic-ratelimit-tokens-remaining': '75000'
        }
        
        # Mock usage object
        mock_usage = MagicMock()
        mock_usage.input_tokens = 500
        mock_usage.output_tokens = 250
        
        original_limit = llm_client.model_limits['context_tokens']
        
        with patch('builtins.print') as mock_print:
            llm_client._track_usage(mock_usage, test_headers)
        
        # Model limits should be updated
        assert llm_client.model_limits['context_tokens'] == 100000
        
        # Should have printed update message
        mock_print.assert_any_call(f"🔄 Updated model token limit: {original_limit:,} → 100,000")
    
    def test_smart_sampling_fallback_on_error(self, llm_client):
        """Test fallback to simple truncation when smart sampling fails"""
        # Create malformed sample data that will cause JSON parsing to fail
        malformed_sample = SampleData(
            original_sample="This is not JSON at all, just plain text that goes on and on " * 100,
            field_analysis={},
            data_source_hints=[],
            common_patterns=[]
        )
        
        # Should fallback to simple truncation
        result = llm_client._smart_sample_data(malformed_sample, 100)  # Very small target
        
        # Should be truncated but not empty
        assert len(result.original_sample) < len(malformed_sample.original_sample)
        assert len(result.original_sample) > 0
        
        # Should preserve other fields
        assert result.field_analysis == malformed_sample.field_analysis
        assert result.data_source_hints == malformed_sample.data_source_hints