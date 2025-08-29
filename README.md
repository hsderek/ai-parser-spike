# DFE AI Parser VRL

AI-powered Vector Remap Language (VRL) parser generator for HyperSec Data Fusion Engine.

## Overview

DFE AI Parser VRL leverages large language models to automatically generate VRL parsers for various log formats. It uses LiteLLM for unified LLM access and supports multiple AI providers including Anthropic, OpenAI, and Google.

## Features

- **AI-Powered Generation**: Automatically generates VRL parsers from log samples
- **Multi-Provider Support**: Works with Anthropic, OpenAI, Google, and more via LiteLLM
- **Smart Model Selection**: Config-driven selection with capability-based routing
- **Error Auto-Fix**: Automatically fixes VRL syntax errors through iterative refinement
- **Validation**: Built-in validation using PyVRL and Vector CLI
- **Device Detection**: Auto-detects log types (SSH, Apache, Cisco, etc.)

## Installation

### Prerequisites

- Python 3.11+
- Vector CLI (optional, for validation)
- API keys for your chosen LLM provider

### Install from Source

```bash
git clone https://github.com/hsderek/ai-parser-spike.git
cd ai-parser-spike
pip install -e .
```

### Dependencies

```bash
pip install litellm loguru pyyaml pyvrl python-dotenv
```

## Quick Start

### Basic Usage

```bash
# Generate VRL from log file
dfe-vrl-generate data/input/SSH.log --device-type ssh

# With specific provider and capability
dfe-vrl-generate logs.txt --platform openai --capability reasoning

# Save to file
dfe-vrl-generate logs.txt --output parser.vrl
```

### Python API

```python
from dfe_ai_parser_vrl import DFEVRLGenerator

# Initialize generator
generator = DFEVRLGenerator()

# Generate VRL from file
vrl_code, metadata = generator.generate_from_file(
    "data/input/ssh.log",
    device_type="ssh"
)

print(f"Model used: {metadata['model_used']}")
print(f"Validation: {metadata['validation_passed']}")
```

## Configuration

Configuration is managed through `config/config.yaml`:

```yaml
defaults:
  platform: anthropic      # or openai, google
  capability: reasoning     # or balanced, efficient
  
platforms:
  anthropic:
    capabilities:
      reasoning:
        families: [opus, sonnet]
      balanced:
        families: [sonnet, haiku]
      efficient:
        families: [haiku]
```

### Model Capabilities

- **REASONING**: Best quality, complex analysis (Opus, GPT-4, Gemini Pro)
- **BALANCED**: Good performance/cost ratio (Sonnet, GPT-4, Gemini Flash)
- **EFFICIENT**: Fast and economical (Haiku, GPT-3.5, Gemini Flash)

## Environment Variables

```bash
# Required: API Keys
export ANTHROPIC_API_KEY=sk-ant-...
export OPENAI_API_KEY=sk-...
export GOOGLE_API_KEY=...

# Optional: Override defaults
export VRL_PLATFORM=openai
export VRL_CAPABILITY=efficient
export VRL_MAX_ITERATIONS=5

# Threading Configuration
export DFE_MAX_THREADS=8  # Override CPU auto-detection
```

## Project Structure

```
.
├── src/
│   ├── dfe_ai_parser_vrl/     # Main VRL parser module
│   │   ├── core/               # Core generation logic
│   │   ├── llm/                # LiteLLM integration
│   │   └── config/             # Configuration management
│   └── dfe_ai_pre_tokenizer/  # Log pre-processing
├── config/                     # Configuration files
├── data/                       # Data directory
│   ├── input/                  # Sample log files
│   ├── output/                 # Generated parsers
│   └── examples/               # Example files
├── tests/                      # Unit tests
├── scripts/                    # CLI scripts
└── docs/                       # Documentation
```

## Development

### Running Tests

```bash
# Run all tests
pytest tests/

# Run specific test
pytest tests/test_model_selector.py -v
```

### Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests
5. Submit a pull request

## AWS Bedrock Support

For AWS Bedrock integration, see `aws/README_BEDROCK.md`.

## License

Proprietary - HyperSec DFE Team

## Contact

HyperSec DFE Team - dev@hypersec.com

## Acknowledgments

- Vector.dev for VRL
- LiteLLM for unified LLM access
- Anthropic, OpenAI, and Google for LLM APIs