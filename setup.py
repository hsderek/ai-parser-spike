#!/usr/bin/env python
"""
Setup script for DFE AI Parser VRL
For compatibility with older pip versions
"""

from setuptools import setup, find_packages
from pathlib import Path

# Read the README
this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text()

setup(
    name="dfe-ai-parser-vrl",
    version="0.1.0",
    author="HyperSec DFE Team",
    author_email="dev@hypersec.com",
    description="AI-powered Vector Remap Language (VRL) parser generator for HyperSec Data Fusion Engine",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/hsderek/ai-parser-spike",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    package_data={
        "dfe_ai_parser_vrl": ["config/*.yaml"],
        "dfe_ai_pre_tokenizer": ["*.yaml", "*.json"],
    },
    install_requires=[
        "litellm>=1.40.0",
        "loguru>=0.7.0",
        "pyyaml>=6.0",
        "pyvrl>=0.0.2",
        "python-dotenv>=1.0.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
            "pytest-asyncio>=0.21.0",
            "black>=23.0.0",
            "ruff>=0.1.0",
            "mypy>=1.0.0",
        ],
        "test": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
            "pytest-asyncio>=0.21.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "dfe-vrl-generate=scripts.generate_vrl:main",
        ],
    },
    python_requires=">=3.11",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Operating System :: OS Independent",
    ],
    keywords="vrl vector log-parsing ai llm hypersec dfe",
    project_urls={
        "Bug Reports": "https://github.com/hsderek/ai-parser-spike/issues",
        "Source": "https://github.com/hsderek/ai-parser-spike",
    },
)