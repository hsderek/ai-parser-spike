import pytest
import os
from pathlib import Path


@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Set up test environment variables and paths."""
    os.environ["ANTHROPIC_API_KEY"] = "test-key-for-testing"
    os.environ["LOG_LEVEL"] = "DEBUG"
    os.environ["VECTOR_CONFIG_PATH"] = "./test_vector.toml"


@pytest.fixture
def sample_ndjson_data():
    """Sample NDJSON data for testing."""
    return [
        '{"timestamp": "2024-01-01T10:00:00Z", "level": "INFO", "message": "User login successful", "user_id": 123, "ip": "192.168.1.1"}',
        '{"timestamp": "2024-01-01T10:01:00Z", "level": "ERROR", "message": "Database connection failed", "user_id": 456, "ip": "10.0.0.1"}',
        '{"timestamp": "2024-01-01T10:02:00Z", "level": "WARN", "message": "High memory usage detected", "user_id": 123, "ip": "192.168.1.1"}'
    ]


@pytest.fixture
def temp_ndjson_file(tmp_path, sample_ndjson_data):
    """Create a temporary NDJSON file for testing."""
    test_file = tmp_path / "test_data.ndjson"
    test_file.write_text("\n".join(sample_ndjson_data))
    return test_file


@pytest.fixture
def sample_output_dir(tmp_path):
    """Create a temporary output directory for testing."""
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    return output_dir