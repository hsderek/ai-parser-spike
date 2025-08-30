# 🚨 CRITICAL VRL DEVELOPMENT RESTRICTIONS 🚨

## ABSOLUTE RULES - NO EXCEPTIONS

### ❌ FORBIDDEN: Source-Specific Code in Python
**NEVER WRITE SOURCE-SPECIFIC PARSING LOGIC IN PYTHON CODE**

Examples of FORBIDDEN practices:
```python
# ❌ NEVER DO THIS
if 'cisco' in sample_file.name:
    # cisco-specific logic
if has_cisco_pattern:
    # cisco parsing
if contains(msg, '%LINEPROTO'):
    # hardcoded pattern matching
```

### ✅ REQUIRED: LLM-Only Specific Parsing
- **Python provides ONLY generic templates and testing infrastructure**
- **ALL specific field extraction comes from LLM analysis of VECTOR-VRL.md + AI-PARSER-PROMPTS.md**
- **LLM must follow both documents every time**

### ❌ FORBIDDEN: Regex in VRL Generation
- **EXPLICIT REJECTION**: Any VRL containing `parse_regex`, `match(`, or `regex` must be rejected
- **VECTOR-VRL.md is clear**: Regex is 50-100x slower than string operations
- **Use ONLY**: `contains()`, `split()`, `upcase()`, `downcase()`, `slice()`

### ✅ REQUIRED: Field Processing Order
**Per VECTOR-VRL.md: Field normalization AFTER extraction**
```vrl
# STEP 1: Extract fields first
if exists(.msg) {
    # extraction logic here
}

# STEP 2: Normalize AFTER extraction (at END)
if exists(.hostname) {
    .hostname_normalized = downcase(string!(.hostname))
}
```

### 🔧 Implementation Requirements
1. **Use `src/vrl_testing_loop_clean.py`** - contains NO source-specific code
2. **LLM API calls must reference both**:
   - VECTOR-VRL.md (performance + syntax)
   - AI-PARSER-PROMPTS.md (prompting strategies)
3. **Explicit regex rejection** in PyVRL validation step
4. **Generic templates only** in Python code

---

# VRL Parser Testing Loop Approach

## Overview
This document describes the comprehensive VRL parser testing and optimization loop implemented for automated parser generation and performance optimization.

## Testing Loop Flow

### 1. LLM VRL Generation (REQUIRED)
- **LLM analyzes JSON samples following VECTOR-VRL.md + AI-PARSER-PROMPTS.md**
- **NO source-specific logic in Python**
- **LLM generates VRL using ONLY string operations (NO REGEX)**
- **Field normalization placed AFTER extraction**

### 2. PyVRL Iteration/Debugging (Fast Validation)
- **EXPLICIT REGEX REJECTION**: Auto-fail any VRL with regex
- Use PyVRL Python bindings for rapid syntax validation
- Iterate up to 5 times with auto-fixes for common issues:
  - Remove unnecessary null coalescing after infallible operations
  - Fix parse_json with proper error handling
  - Replace % operator with mod() function
  - Convert type() calls to is_object()
- Validate field extraction with sample data
- Track new fields added by the parser

### 3. Vector CLI Validation
- Generate temporary YAML configuration
- Run actual Vector process with test data
- Validate that Vector accepts the VRL code
- Check for runtime errors or warnings

### 4. Performance Testing and Baseline Recording
- Create test dataset with 10,000 events
- Run Vector with optimal thread count (4 threads)
- Monitor performance metrics:
  - CPU utilization (via psutil)
  - Memory consumption
  - Events per second throughput
  - Events per CPU% (primary metric)
  - P99 latency estimation
- Record baseline for comparison

### 5. Alternative Implementation Generation (LLM)
- **LLM generates alternatives, not Python code**
- **String operations priority** (350-400 events/CPU%)
- **Hybrid approaches** (string checks before minimal processing)
- **NO REGEX alternatives** (forbidden per VECTOR-VRL.md)

### 6. A-B Performance Testing
- Run performance tests on all candidates
- Compare key metrics:
  - Events per CPU% (primary optimization target)
  - Absolute throughput (events/sec)
  - Memory usage
  - P99 latency
- Rank candidates by efficiency

### 7. Best Candidate Selection
- Select winner based on Events/CPU% metric
- Save optimized VRL to samples-parsed/
- Generate performance comparison report
- Document winning strategy

## Implementation Details

### Key Files
- `src/vrl_testing_loop_clean.py` - Clean testing infrastructure (NO source-specific code)
- `samples-parsed/*-optimized.vrl` - Best performing VRL parser
- `samples-parsed/*-performance.json` - Performance comparison data

### Performance Tiers (from VECTOR-VRL.md)
- **Tier 1** (300-400 events/CPU%): String operations - **USE THESE**
- **Tier 2** (150-250 events/CPU%): Type conversions
- **Tier 3** (50-100 events/CPU%): JSON/Crypto operations
- **Tier 4** (3-10 events/CPU%): Regex operations - **FORBIDDEN**

### VRL Optimization Patterns (LLM Must Follow)

#### Exit Fast
```vrl
if !exists(.msg) {
    .  # Return early if no message to parse
}
```

#### String Operations Over Regex (REQUIRED)
```vrl
# Tier 1 performance - contains() is 350-400 events/CPU%
if contains(msg, "%") && contains(msg, "-") {
    # Process only if pattern likely exists
    parts = split(msg, "%")  # split() is also Tier 1
}
```

#### Field Processing Order (REQUIRED)
```vrl
# STEP 1: Extract fields
if exists(.msg) {
    msg = string!(.msg)
    # extraction logic here
}

# STEP 2: Normalize AFTER extraction (at END)
if exists(.hostname) {
    .hostname_normalized = downcase(string!(.hostname))
}
```

#### Efficient Error Handling
```vrl
.parsed, .error = parse_json(string!(.message))
if .error == null {
    # Process parsed data
}
del(.error)  # Clean up immediately
```

## Usage

### Run with LLM-Generated VRL
```python
from src.vrl_testing_loop_clean import VRLTestingLoop

loop = VRLTestingLoop("samples/my-logs.ndjson")
llm_vrl = """
# LLM-generated VRL code here
# Must follow VECTOR-VRL.md + AI-PARSER-PROMPTS.md
"""
loop.run_with_llm_generated_vrl(llm_vrl)
```

### Dependencies
- PyVRL from PyPI: `pip install pyvrl`
- Other deps in `pyproject.toml`

## Results

### Performance Targets
- **Minimum**: 20K events/CPU% per transform
- **String ops**: 350-400 events/CPU% (Tier 1)
- **Regex forbidden**: 3-10 events/CPU% (Tier 4 - too slow)

### Lessons Learned
1. **Python code must be source-agnostic** - only generic templates
2. **LLM generates all specific parsing** following both guidance docs
3. **Regex is explicitly forbidden** - 50-100x slower than string ops
4. **Field normalization goes at END** after extraction
5. **PyVRL provides excellent validation** before Vector testing
6. **CPU efficiency (events/CPU%) is primary metric**

## References (LLM Must Use Both)
- [VECTOR-VRL.md](VECTOR-VRL.md) - **VRL performance constraints and syntax**
- [AI-PARSER-PROMPTS.md](AI-PARSER-PROMPTS.md) - **LLM prompting strategies**
- [Vector VRL Documentation](https://vector.dev/docs/reference/vrl/)
- [PyVRL PyPI](https://pypi.org/project/pyvrl/)