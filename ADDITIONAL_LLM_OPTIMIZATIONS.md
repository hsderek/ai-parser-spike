# Additional LLM Optimizations for VRL Generation

## Current Optimizations Already Implemented ✅

1. **Pre-tokenizer** - Reduces samples from 780K → ~50 representative samples
2. **Smart Sample Selection** - 3 examples per pattern max
3. **Pattern Caching** - Skip LLM for previously solved patterns  
4. **Prompt Compression** - Reduces prompts by 40-60% after iteration 1
5. **External Config Optimization** - Compresses vector-vrl and parser prompts

## Additional Optimizations to Implement 🚀

### 1. **Incremental Context Loading** (High Impact)
Instead of sending all context upfront, load incrementally:

```python
def incremental_context_strategy(iteration: int):
    if iteration == 1:
        # Minimal context - just samples and basic rules
        return ["samples", "basic_vrl_rules"]
    elif iteration == 2 and "array access" in errors:
        # Add specific array handling guidance
        return ["array_patterns", "fallible_examples"]
    elif iteration == 3 and "type" in errors:
        # Add type conversion guidance
        return ["type_conversion_rules"]
```

**Impact**: 30-40% reduction in initial token usage

### 2. **Error Pattern Learning** (Medium Impact)
Track common error patterns and preemptively add fixes:

```python
class ErrorPatternLearner:
    def __init__(self):
        self.error_patterns = {
            "E103": {
                "frequency": 0,
                "fix_template": "if length({var}) > {index} {{ {var}[{index}] }}",
                "prevention": "Always check array length before access"
            },
            "E110": {
                "frequency": 0,
                "fix_template": "{expr} ?? false",
                "prevention": "Fallible operations need error handling"
            }
        }
    
    def learn_from_error(self, error_code, context):
        self.error_patterns[error_code]["frequency"] += 1
        # After 3 occurrences, add prevention to initial prompt
        if self.error_patterns[error_code]["frequency"] >= 3:
            return self.error_patterns[error_code]["prevention"]
```

**Impact**: 20-30% reduction in iterations needed

### 3. **VRL Template Library** (High Impact)
Pre-built VRL snippets for common patterns:

```python
VRL_TEMPLATES = {
    "cisco_asa": """
# Cisco ASA base template
if starts_with(.message, "%ASA-") {
    parts = split(.message, " ")
    if length(parts) > 2 {
        .severity_code = replace(parts[0], r'%ASA-(\d)-.*', "$1") ?? "unknown"
        .event_id = replace(parts[0], r'%ASA-\d-(\d+):.*', "$1") ?? "unknown"
    }
}
""",
    "key_value": """
# Key-value extraction template
if contains(.message, "=") {
    pairs = split(.message, " ")
    for_each(pairs) -> |_index, pair| {
        if contains(pair, "=") {
            kv = split(pair, "=")
            if length(kv) == 2 {
                .extracted[kv[0]] = kv[1]
            }
        }
    }
}
"""
}

def inject_template(log_pattern: str) -> str:
    """Inject relevant template into prompt"""
    if log_pattern in VRL_TEMPLATES:
        return f"Start with this template:\n```vrl\n{VRL_TEMPLATES[log_pattern]}\n```"
    return ""
```

**Impact**: 40-50% faster convergence, 30% fewer errors

### 4. **Streaming Validation** (Medium Impact)
Validate VRL as it's generated:

```python
async def stream_validate(llm_stream):
    vrl_buffer = ""
    for chunk in llm_stream:
        vrl_buffer += chunk
        
        # Quick syntax check every 500 chars
        if len(vrl_buffer) % 500 == 0:
            syntax_valid = quick_syntax_check(vrl_buffer)
            if not syntax_valid:
                # Early termination if syntax broken
                return None, "Syntax error detected early"
    
    return vrl_buffer, "Complete"
```

**Impact**: 20% faster failure detection

### 5. **Parallel Pattern Processing** (High Impact)
Process multiple log patterns in parallel:

```python
async def parallel_vrl_generation(pattern_groups):
    tasks = []
    for pattern, samples in pattern_groups.items():
        # Check cache first
        if cached_vrl := get_cached(pattern):
            continue
            
        # Create parallel task
        task = asyncio.create_task(
            generate_vrl_for_pattern(pattern, samples[:3])
        )
        tasks.append((pattern, task))
    
    # Wait for all to complete
    results = await asyncio.gather(*[t[1] for t in tasks])
    
    # Combine VRL snippets
    combined_vrl = merge_vrl_snippets(results)
    return combined_vrl
```

**Impact**: 3-5x faster for multi-pattern logs

### 6. **Confidence-Based Early Stopping** (Low Impact)
Stop iteration if confidence is high:

```python
def calculate_confidence(vrl_code, test_results):
    confidence = 0.0
    
    # No errors = high confidence
    if not test_results.get('errors'):
        confidence += 0.5
    
    # Good performance = higher confidence
    if test_results.get('events_per_cpu_percent', 0) > 500:
        confidence += 0.3
    
    # Many fields extracted = higher confidence  
    if len(test_results.get('extracted_fields', [])) > 10:
        confidence += 0.2
        
    return confidence

# In iteration loop:
if calculate_confidence(vrl_code, test_results) > 0.8:
    logger.info("High confidence achieved, stopping iterations")
    break
```

**Impact**: 10-20% reduction in unnecessary iterations

### 7. **Context Window Management** (High Impact)
Intelligently manage context window:

```python
class ContextManager:
    def __init__(self, max_tokens=100000):
        self.max_tokens = max_tokens
        self.used_tokens = 0
        self.context_priority = {
            'samples': 1,
            'errors': 2,
            'vrl_rules': 3,
            'type_maps': 4,
            'examples': 5
        }
    
    def fit_to_window(self, components):
        """Fit components into token window by priority"""
        sorted_components = sorted(
            components.items(), 
            key=lambda x: self.context_priority.get(x[0], 999)
        )
        
        final_context = {}
        for name, content in sorted_components:
            content_tokens = count_tokens(content)
            if self.used_tokens + content_tokens < self.max_tokens:
                final_context[name] = content
                self.used_tokens += content_tokens
            else:
                # Truncate or skip
                remaining = self.max_tokens - self.used_tokens
                if remaining > 1000:  # Worth truncating
                    final_context[name] = truncate_to_tokens(content, remaining)
                break
                
        return final_context
```

**Impact**: Prevents context overflow, maintains quality

### 8. **Differential Prompting** (Medium Impact)
Only send what changed:

```python
def differential_prompt(iteration, previous_prompt, errors):
    if iteration == 1:
        return previous_prompt
    
    # Only send new errors and specific fixes
    diff_prompt = []
    diff_prompt.append("Previous attempt had these NEW errors:")
    
    new_errors = [e for e in errors if e not in previous_errors]
    for error in new_errors[:5]:
        diff_prompt.append(f"- {error}")
    
    diff_prompt.append("\nFocus ONLY on fixing these new errors.")
    return '\n'.join(diff_prompt)
```

**Impact**: 50-70% reduction in iteration prompt size

### 9. **Model Routing** (Medium Impact)
Use different models for different complexity:

```python
def select_model_by_complexity(samples, pattern_count):
    # Simple single-pattern logs
    if pattern_count == 1 and len(samples) < 10:
        return "claude-3-haiku"  # Fast, cheap
    
    # Medium complexity
    elif pattern_count <= 3:
        return "claude-3-sonnet"  # Balanced
    
    # Complex multi-pattern
    else:
        return "claude-3-opus"  # Most capable
```

**Impact**: 40-60% cost reduction on simple logs

### 10. **Result Combination Strategy** (Low Impact)
Combine successful partial results:

```python
def combine_partial_successes(attempts):
    """Combine working parts from multiple attempts"""
    working_segments = []
    
    for attempt in attempts:
        # Test each segment independently
        segments = split_vrl_into_segments(attempt['vrl'])
        for segment in segments:
            if test_segment(segment):
                working_segments.append(segment)
    
    # Combine non-conflicting segments
    combined = merge_segments(working_segments)
    return combined
```

**Impact**: 15-25% improvement in final success rate

## Implementation Priority Matrix

| Optimization | Impact | Effort | Priority |
|-------------|--------|--------|----------|
| VRL Template Library | High | Low | **1** |
| Incremental Context | High | Medium | **2** |
| Parallel Patterns | High | High | **3** |
| Context Window Mgmt | High | Medium | **4** |
| Error Pattern Learning | Medium | Low | **5** |
| Model Routing | Medium | Low | **6** |
| Differential Prompting | Medium | Low | **7** |
| Streaming Validation | Medium | High | **8** |
| Confidence Stopping | Low | Low | **9** |
| Result Combination | Low | Medium | **10** |

## Quick Wins to Implement Now

### 1. Add VRL Templates (5 min implementation):
```python
# In llm_iterative_session.py
def get_vrl_template(pattern):
    templates = {
        'cisco-asa': '# Template for Cisco ASA\nif starts_with(.message, "%ASA-") {...}',
        'key-value': '# Template for key=value\nif contains(.message, "=") {...}'
    }
    return templates.get(pattern, "")

# In prompt building:
template = get_vrl_template(detected_pattern)
if template:
    prompt_parts.append(f"\nUse this template as a starting point:\n{template}")
```

### 2. Add Error Pattern Tracking (10 min):
```python
# Track in session
if not hasattr(self, 'error_frequency'):
    self.error_frequency = {}

for error in test_results['errors']:
    error_type = extract_error_code(error)
    self.error_frequency[error_type] = self.error_frequency.get(error_type, 0) + 1

# Add to prompt if frequent
frequent_errors = [e for e, count in self.error_frequency.items() if count >= 2]
if frequent_errors:
    prompt_parts.append(f"FREQUENT ERRORS TO AVOID: {frequent_errors}")
```

### 3. Add Simple Model Routing (5 min):
```python
# In run_automated_llm_generation
if len(set(o.detect_log_pattern(s) for s in self.samples)) == 1:
    # Single pattern - use cheaper model
    model_override = model_override or "claude-3-haiku-20240307"
    logger.info("Single pattern detected, using Haiku for speed")
```

## Expected Combined Impact

With all optimizations:
- **Token Usage**: 85-90% reduction
- **API Costs**: 70-85% reduction  
- **Processing Time**: 60-75% faster
- **Success Rate**: 30-40% improvement
- **Iterations Needed**: 40-50% reduction

The key is the synergy between optimizations:
- Pre-tokenizer reduces input size
- Templates provide good starting points
- Error learning prevents repeated mistakes
- Parallel processing handles complex logs efficiently
- Smart routing optimizes cost/performance