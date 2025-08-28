"""Tests for config loader"""

import pytest
from vrl_parser.config.loader import ConfigLoader


def test_config_loader():
    """Test config loading"""
    config = ConfigLoader.load()
    
    assert config is not None
    assert "defaults" in config
    assert "platforms" in config


def test_config_defaults():
    """Test config defaults"""
    config = ConfigLoader.load()
    
    defaults = config.get("defaults", {})
    assert defaults.get("platform") is not None
    assert defaults.get("capability") is not None


def test_smart_defaults():
    """Test smart defaults are applied"""
    config = ConfigLoader.load()
    
    # Should have paths configured
    assert "paths" in config
    assert "logging" in config