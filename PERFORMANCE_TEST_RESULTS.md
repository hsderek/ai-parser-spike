# Performance Test Results - Large Apache Logs

## Test Date: August 28, 2025

### Dataset
- **File**: `samples/large/apache-real.ndjson`
- **Size**: 56,482 real Apache log entries from LogHub
- **Source**: Production Apache web server logs (not sanitized/anonymized)

## 🎯 Optimization Performance

### Sample Reduction
| Stage | Sample Count | Reduction |
|-------|-------------|-----------|
| Original | 56,482 | - |
| After Smart Selection | 3 | 99.995% |
| Patterns Detected | 1 (apache) | - |

### Token Optimization
| Metric | Value |
|--------|-------|
| Tokens Used | 1,778 |
| Max Budget | 30,000 |
| Utilization | 5.9% |
| Pattern Coverage | 100% |

### Prompt Compression
| Component | Original | Compressed | Reduction |
|-----------|----------|------------|-----------|
| vector_vrl_prompt | 19,919 chars | 18,026 chars | 9.5% |
| parser_prompts | 10,690 chars | 1,988 chars | 81.4% |
| type_maps | 2,877 chars | 2,749 chars | 4.4% |
| **Total** | 33,486 chars | 22,763 chars | **32.0%** |

## 💰 Cost Analysis

### Without Optimizations (Theoretical)
- Samples: 56,482
- Estimated tokens: ~14,120,500 (250 tokens/sample)
- Cost per iteration: $211.81 (@$15/1M input tokens)
- Total for 2 iterations: **$423.62**

### With Optimizations (Actual)
- Samples: 3
- Tokens: 1,778
- Cost per iteration: ~$0.03
- Total for 2 iterations: **~$0.06**

### **SAVINGS: 99.99% or $423.56 per run!**

## ⚡ Performance Metrics

### API Response Times
- Iteration 1: 40.6 seconds
- Iteration 2: 37.2 seconds
- Total API time: 77.8 seconds

### Processing Speed
- Sample optimization: <1 second
- Pre-tokenizer: <1 second
- Total overhead: ~2 seconds

## ❌ Current Issues

### VRL Syntax Errors
Both iterations failed with VRL syntax errors:
1. **Iteration 1**: Multiple syntax errors including:
   - Unexpected return statement
   - Variable `last_index` not defined properly
   - Missing array bounds checking

2. **Iteration 2**: Similar errors persisted:
   - Array indexing with variable still failing
   - Bracket mismatches

### Root Cause Analysis
The errors suggest Claude needs more specific guidance on:
1. VRL doesn't support dynamic array indexing with variables
2. Array access must use literal integers
3. Need to use conditional checks for array operations

## ✅ What Worked

1. **Pre-tokenizer**: Massive 99.995% sample reduction
2. **Pattern Detection**: Correctly identified Apache logs
3. **Token Budget**: Used only 5.9% of available tokens
4. **Prompt Compression**: 32% reduction in prompt size
5. **Cost Savings**: 99.99% reduction in API costs
6. **Auto Model Selection**: Successfully detected Claude Opus 4.1

## 🔧 Improvements Needed

1. **VRL Syntax Guidance**: Add more specific rules about:
   - No dynamic array indexing
   - Use `if length(array) > N` before `array[N]`
   - Avoid variable-based array access

2. **Template Enhancement**: The Apache template needs:
   - Better error handling patterns
   - Explicit array bounds checking
   - Simpler parsing logic

3. **Error Pattern Learning**: After seeing these errors, should add:
   - Specific prevention for `array[variable]` patterns
   - More defensive array handling examples

## 📊 Summary

The optimization system is working **exceptionally well** for:
- **Sample reduction**: 56K → 3 samples
- **Token savings**: 99.99% reduction
- **Cost savings**: $423+ saved per run

However, VRL generation still needs refinement for:
- Complex array operations
- Dynamic indexing patterns
- Apache-specific log parsing

The infrastructure is solid - just needs better VRL-specific guidance in the prompts.