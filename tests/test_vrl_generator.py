"""Tests for VRL generator"""

import pytest
from unittest.mock import Mock, patch
from vrl_parser.core.generator import VRLGenerator


def test_generator_init():
    """Test VRL generator initialization"""
    generator = VRLGenerator()
    assert generator is not None
    assert generator.config is not None
    assert generator.llm_client is not None


def test_device_type_detection():
    """Test auto-detection of device types"""
    generator = VRLGenerator()
    
    # Test various filename patterns
    assert generator._detect_device_type("ssh.log") == "ssh"
    assert generator._detect_device_type("apache_access.log") == "apache"
    assert generator._detect_device_type("cisco_asa.log") == "cisco"
    assert generator._detect_device_type("nginx_error.log") == "nginx"
    assert generator._detect_device_type("unknown.log") is None


@patch('vrl_parser.core.generator.VRLGenerator.generate')
def test_generate_from_file(mock_generate):
    """Test generating from file"""
    mock_generate.return_value = ("# VRL code", {"validation_passed": True})
    
    generator = VRLGenerator()
    
    # Mock file reading
    with patch('builtins.open', create=True) as mock_open:
        mock_open.return_value.__enter__.return_value.read.return_value = "log content"
        with patch('pathlib.Path.exists', return_value=True):
            vrl, metadata = generator.generate_from_file("test.log")
    
    assert vrl == "# VRL code"
    assert metadata["validation_passed"] is True