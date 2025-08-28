"""Tests for model selector"""

import pytest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dfe_ai_parser_vrl.llm.model_selector import DFEModelSelector


def test_model_selector_init():
    """Test model selector initialization"""
    selector = DFEModelSelector()
    assert selector is not None
    assert selector.config is not None


def test_default_selection():
    """Test default model selection"""
    selector = DFEModelSelector()
    model, metadata = selector.select_model()
    
    # Should select something even with defaults
    assert metadata["platform"] is not None
    assert metadata["capability"] is not None


def test_capability_selection():
    """Test selecting by capability"""
    selector = DFEModelSelector()
    
    # Test each capability
    for capability in ["reasoning", "balanced", "efficient"]:
        model, metadata = selector.select_model(capability=capability)
        assert metadata["capability"] == capability


def test_platform_selection():
    """Test selecting by platform"""
    selector = DFEModelSelector()
    
    # Test known platforms
    for platform in ["anthropic", "openai", "google"]:
        model, metadata = selector.select_model(platform=platform)
        assert metadata["platform"] == platform