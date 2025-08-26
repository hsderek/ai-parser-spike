import pytest
from src.analyzer import DataAnalyzer
from src.config import Config
from src.models import SampleData


@pytest.fixture
def config():
    return Config(anthropic_api_key="test-key")


@pytest.fixture
def analyzer(config):
    return DataAnalyzer(config)


@pytest.fixture
def sample_logs():
    return [
        {"timestamp": "2024-01-01T10:00:00Z", "level": "INFO", "message": "User login successful", "user_id": 123, "ip": "192.168.1.1"},
        {"timestamp": "2024-01-01T10:01:00Z", "level": "ERROR", "message": "Database connection failed", "user_id": 456, "ip": "10.0.0.1"},
        {"timestamp": "2024-01-01T10:02:00Z", "level": "WARN", "message": "High memory usage detected", "user_id": 123, "ip": "192.168.1.1"}
    ]


class TestDataAnalyzer:
    def test_analyze_samples_basic(self, analyzer, sample_logs):
        result = analyzer.analyze_samples(sample_logs)
        
        assert isinstance(result, SampleData)
        assert "timestamp" in result.field_analysis
        assert "level" in result.field_analysis
        assert "message" in result.field_analysis
        assert result.field_analysis["timestamp"]["is_high_value"] is True
        assert result.field_analysis["message"]["is_high_value"] is True
    
    def test_flatten_dict(self, analyzer):
        nested_dict = {
            "outer": {
                "inner": "value",
                "nested": {"deep": "deep_value"}
            },
            "list": [{"item": "value1"}, {"item": "value2"}]
        }
        
        flattened = analyzer._flatten_dict(nested_dict)
        
        assert "outer.inner" in flattened
        assert "outer.nested.deep" in flattened
        assert "list[0].item" in flattened
        assert flattened["outer.inner"] == "value"
        assert flattened["outer.nested.deep"] == "deep_value"
    
    def test_map_python_to_abstract_type(self, analyzer):
        assert analyzer._map_python_to_abstract_type("int", []) == "int64"
        assert analyzer._map_python_to_abstract_type("float", []) == "float64"
        assert analyzer._map_python_to_abstract_type("bool", []) == "boolean"
    
    def test_infer_string_type_ip(self, analyzer):
        ip_samples = ["192.168.1.1", "10.0.0.1", "172.16.0.1"]
        result = analyzer._infer_string_type(ip_samples)
        assert result == "ipv4"
    
    def test_infer_string_type_uuid(self, analyzer):
        uuid_samples = ["550e8400-e29b-41d4-a716-446655440000"]
        result = analyzer._infer_string_type(uuid_samples)
        assert result == "uuid"
    
    def test_infer_string_type_text(self, analyzer):
        text_samples = ["This is a very long message that contains a lot of text and should be classified as text type rather than string"]
        result = analyzer._infer_string_type(text_samples)
        assert result == "text"
    
    def test_is_high_value_field(self, analyzer):
        assert analyzer._is_high_value_field("message") is True
        assert analyzer._is_high_value_field("timestamp") is True
        assert analyzer._is_high_value_field("user_id") is True
        assert analyzer._is_high_value_field("random_field") is False
    
    def test_extract_data_source_hints(self, analyzer, sample_logs):
        hints = analyzer._extract_data_source_hints(sample_logs)
        assert isinstance(hints, list)
    
    def test_extract_field_candidates_high_level(self, analyzer, sample_logs):
        sample_data = analyzer.analyze_samples(sample_logs)
        candidates = analyzer.extract_field_candidates(sample_data, "high")
        
        # High level should only include high-value fields
        high_value_count = sum(1 for c in candidates if c.is_high_value)
        assert high_value_count == len(candidates)
    
    def test_extract_field_candidates_medium_level(self, analyzer, sample_logs):
        sample_data = analyzer.analyze_samples(sample_logs)
        candidates = analyzer.extract_field_candidates(sample_data, "medium")
        
        # Medium level should include more fields than high
        assert len(candidates) >= 3
    
    def test_empty_samples_error(self, analyzer):
        with pytest.raises(ValueError, match="No samples provided"):
            analyzer.analyze_samples([])
    
    def test_calculate_confidence(self, analyzer):
        analysis_high_value = {"frequency": 0.8, "is_high_value": True}
        analysis_normal = {"frequency": 0.8, "is_high_value": False}
        
        high_conf = analyzer._calculate_confidence(analysis_high_value)
        normal_conf = analyzer._calculate_confidence(analysis_normal)
        
        assert high_conf > normal_conf
        assert high_conf <= 1.0