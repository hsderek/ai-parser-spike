# Pre-Tokenizer Module

A standalone, portable module for optimizing large sample data before LLM processing.

## Features

- **Token Counting**: Accurate token counting for various LLM models
- **Sample Deduplication**: Intelligent deduplication based on normalized patterns
- **Diversity Optimization**: Maximizes pattern diversity within token budget
- **Pattern Recognition**: Built-in recognition for 20+ log format patterns
- **Self-Contained**: Copy entire directory to use in other projects

## Installation

Simply copy the entire `pre_tokenizer` directory to your project:

```bash
cp -r pre_tokenizer /path/to/your/project/
```

## Usage

```python
from pre_tokenizer import PreTokenizer, SampleOptimizer

# Initialize tokenizer with model and token limit
tokenizer = PreTokenizer(
    model="claude-3-opus-20240229",
    max_tokens=150000  # Leave room for prompts
)

# Load your samples
samples = [
    {"message": "log line 1..."},
    {"message": "log line 2..."},
    # ... many more samples
]

# Optimize samples for LLM
result = tokenizer.prepare_for_llm(samples)

print(f"Selected {result['count']} samples from {len(samples)}")
print(f"Token usage: {result['optimization_stats']['total_tokens']}")
print(f"Pattern coverage: {result['optimization_stats']['pattern_coverage']}")

# Use optimized samples with your LLM
optimized_samples = result['samples']
```

## Advanced Optimization

```python
from pre_tokenizer import SampleOptimizer

optimizer = SampleOptimizer()

# Deduplicate samples
unique_samples = optimizer.deduplicate_samples(samples)

# Select diverse subset
diverse_samples = optimizer.select_diverse_subset(samples, target_count=100)

# Calculate diversity score
diversity = optimizer.calculate_diversity_score(samples)
```

## Supported Patterns

The module recognizes patterns for:

- **Firewall Formats**: Cisco ASA, FortiGate, Palo Alto, Check Point, SonicWall, Sophos
- **Log Standards**: CEF, LEEF, Syslog, JSON
- **System Logs**: Windows Events, Linux Audit, Apache, Nginx
- **Event Types**: Auth, Network, Error, Warning, Info

## Configuration

### Token Limits by Model

```python
# Recommended max_tokens settings (leaving room for prompts)
MODELS = {
    'claude-3-opus': 150000,     # 200k context window
    'claude-3-sonnet': 150000,   # 200k context window
    'gpt-4-turbo': 100000,       # 128k context window
    'gpt-4': 6000,               # 8k context window
    'gpt-3.5-turbo': 14000,      # 16k context window
}
```

## Requirements

- Python 3.7+
- tiktoken
- loguru (optional, for logging)

```bash
pip install tiktoken loguru
```

## License

This module is part of the AI Parser Spike project.
© 2025 HyperSec Pty Ltd