import pytest
from src.vrl_generator import VRLGenerator
from src.config import Config
from src.models import ExtractedField, CPUCost


@pytest.fixture
def config():
    return Config(anthropic_api_key="test-key")


@pytest.fixture
def generator(config):
    return VRLGenerator(config)


@pytest.fixture
def sample_fields():
    return [
        ExtractedField(
            name="timestamp",
            type="datetime",
            description="Event timestamp",
            cpu_cost=CPUCost.MEDIUM,
            confidence=0.9,
            is_high_value=True
        ),
        ExtractedField(
            name="message",
            type="string",
            description="Log message",
            cpu_cost=CPUCost.LOW,
            confidence=0.95,
            is_high_value=True
        ),
        ExtractedField(
            name="user_id",
            type="int64",
            description="User identifier",
            cpu_cost=CPUCost.MEDIUM,
            confidence=0.8,
            is_high_value=True
        ),
        ExtractedField(
            name="ip_address",
            type="ipv4",
            description="Client IP address",
            cpu_cost=CPUCost.LOW,
            confidence=0.85,
            is_high_value=True
        )
    ]


class TestVRLGenerator:
    def test_generate_basic_vrl(self, generator, sample_fields):
        vrl_code = generator.generate(sample_fields, {})
        
        assert "# Filename: generated_parser.vrl" in vrl_code
        assert "HyperSec EULA © 2025" in vrl_code
        assert "timestamp" in vrl_code
        assert "message" in vrl_code
        assert "user_id" in vrl_code
        assert "ip_address" in vrl_code
    
    def test_generate_header(self, generator):
        header = generator._generate_header()
        
        assert "#---" in header
        assert "Filename: generated_parser.vrl" in header
        assert "HyperSec EULA © 2025" in header
        assert "Version: 1.0.0" in header
    
    def test_generate_string_extraction(self, generator):
        field = ExtractedField(
            name="message",
            type="string",
            description="Log message",
            cpu_cost=CPUCost.LOW,
            confidence=0.95,
            is_high_value=True
        )
        
        transform = generator._generate_field_transform(field)
        
        assert "string!" in transform
        assert ".message" in transform
        assert "if exists(" in transform
    
    def test_generate_int_extraction(self, generator):
        field = ExtractedField(
            name="user_id",
            type="int64",
            description="User ID",
            cpu_cost=CPUCost.MEDIUM,
            confidence=0.8,
            is_high_value=True
        )
        
        transform = generator._generate_field_transform(field)
        
        assert "to_int(" in transform
        assert "user_id_err" in transform
        assert "if .user_id_err != null" in transform
    
    def test_generate_datetime_extraction(self, generator):
        field = ExtractedField(
            name="timestamp",
            type="datetime",
            description="Event timestamp",
            cpu_cost=CPUCost.MEDIUM,
            confidence=0.9,
            is_high_value=True
        )
        
        transform = generator._generate_field_transform(field)
        
        assert "parse_timestamp(" in transform
        assert "format:" in transform
        assert "now()" in transform  # Fallback
    
    def test_generate_ip_extraction(self, generator):
        field = ExtractedField(
            name="client_ip",
            type="ipv4",
            description="Client IP",
            cpu_cost=CPUCost.LOW,
            confidence=0.85,
            is_high_value=True
        )
        
        transform = generator._generate_field_transform(field)
        
        assert 'contains(.client_ip_raw, ".")' in transform
        assert "length(.client_ip_raw)" in transform
        assert ">= 7" in transform and "<= 15" in transform
    
    def test_generate_boolean_extraction(self, generator):
        field = ExtractedField(
            name="is_active",
            type="boolean",
            description="Active status",
            cpu_cost=CPUCost.LOW,
            confidence=0.7,
            is_high_value=False
        )
        
        transform = generator._generate_field_transform(field)
        
        assert "is_boolean(" in transform
        assert "downcase(" in transform
        assert 'contains(.is_active_str, "true")' in transform
    
    def test_get_field_path(self, generator):
        assert generator._get_field_path("message") == ".message"
        assert generator._get_field_path(".message") == ".message"
        assert generator._get_field_path("nested.field") == ".nested.field"
    
    def test_safe_field_name(self, generator):
        assert generator._safe_field_name("field.name") == "field_name"
        assert generator._safe_field_name("field[0].name") == "field_0_name"
        assert generator._safe_field_name("field-name") == "field_name"
        assert generator._safe_field_name(".field") == "field"
    
    def test_generate_cleanup(self, generator, sample_fields):
        cleanup = generator._generate_cleanup(sample_fields)
        
        assert "del(..*_err)" in cleanup
        assert "Performance optimization" in cleanup
        assert f"fields processed = {len(sample_fields)}" in cleanup
    
    def test_vrl_code_structure(self, generator, sample_fields):
        vrl_code = generator.generate(sample_fields, {})
        lines = vrl_code.split('\n')
        
        # Check that it starts with header
        assert lines[0].startswith("#---")
        
        # Check that it contains transforms
        transform_lines = [line for line in lines if "if exists(" in line or "# Extract" in line]
        assert len(transform_lines) > 0
        
        # Check that it ends with cleanup
        assert "del(..*_err)" in vrl_code