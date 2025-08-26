import pytest
import os
from pathlib import Path
from src.config import Config


class TestConfig:
    def test_config_from_environment(self):
        # Test with environment variables
        os.environ["ANTHROPIC_API_KEY"] = "test-key"
        os.environ["LOG_LEVEL"] = "DEBUG"
        
        config = Config()
        
        assert config.anthropic_api_key == "test-key"
        assert config.log_level == "DEBUG"
        
        # Cleanup
        del os.environ["ANTHROPIC_API_KEY"]
        del os.environ["LOG_LEVEL"]
    
    def test_config_explicit_params(self):
        config = Config(
            anthropic_api_key="explicit-key",
            log_level="INFO",
            vector_config_path="./test.toml"
        )
        
        assert config.anthropic_api_key == "explicit-key"
        assert config.log_level == "INFO"
        assert config.vector_config_path == "./test.toml"
    
    def test_type_mappings_loaded(self):
        config = Config(anthropic_api_key="test-key")
        
        # Should load type mappings from CSV
        assert len(config.type_mappings) > 0
        assert "string" in config.available_types
        assert "int64" in config.available_types
        assert "datetime" in config.available_types
    
    def test_get_type_info(self):
        config = Config(anthropic_api_key="test-key")
        
        string_info = config.get_type_info("string")
        assert "type" in string_info
        assert string_info["type"] == "string"
        
        # Non-existent type
        unknown_info = config.get_type_info("unknown_type")
        assert unknown_info == {}
    
    def test_available_types(self):
        config = Config(anthropic_api_key="test-key")
        
        types = config.available_types
        assert isinstance(types, list)
        assert len(types) > 10  # Should have many types from CSV
        assert "string" in types
        assert "boolean" in types