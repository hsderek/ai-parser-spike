#!/bin/bash
# Load environment and run test with real API

# Load .env file
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Check if API key is set
if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "Error: ANTHROPIC_API_KEY not set"
    exit 1
fi

echo "API key loaded, running test..."
uv run python test_automated_llm_vrl.py