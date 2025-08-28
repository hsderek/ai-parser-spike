"""
VRL Parser - AI-powered Vector Remap Language generator
"""

__version__ = "0.1.0"
__author__ = "HyperSec DFE Team"

from .core.generator import VRLGenerator
from .llm.client import LLMClient
from .config.loader import ConfigLoader

__all__ = ["VRLGenerator", "LLMClient", "ConfigLoader"]