"""Tests for config loader"""

import pytest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dfe_ai_parser_vrl.config.loader import DFEConfigLoader


def test_config_loader():
    """Test config loading"""
    config = DFEConfigLoader.load()
    
    assert config is not None
    assert "defaults" in config
    assert "platforms" in config


def test_config_defaults():
    """Test config defaults"""
    config = DFEConfigLoader.load()
    
    defaults = config.get("defaults", {})
    assert defaults.get("platform") is not None
    assert defaults.get("capability") is not None


def test_smart_defaults():
    """Test smart defaults are applied"""
    config = DFEConfigLoader.load()
    
    # Should have paths configured
    assert "paths" in config
    assert "logging" in config