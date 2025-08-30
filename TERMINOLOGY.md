# DFE VRL Standard Terminology

## 🎯 **Two-Stage Architecture**

```
baseline_vrl → baseline_stage → candidate_baseline → performance_stage → optimized_vrl
```

## 📋 **Standard Terms**

### **VRL Types:**
- **`baseline_vrl`**: Input working VRL (if available) - the current solution that works
- **`candidate_baseline`**: Working VRL output from baseline_stage - proven functional
- **`optimized_vrl`**: Best performing VRL from performance_stage - VPI optimized

### **Stages:**
- **`baseline_stage`**: Establishes working VRL that passes validation
  - **Purpose**: Get functional VRL that extracts fields correctly
  - **Class**: `DFEVRLGenerator` 
  - **Input**: Log samples + optional baseline_vrl
  - **Output**: candidate_baseline (working VRL)
  - **Success**: validation_passed=True + Vector CLI processes events

- **`performance_stage`**: Optimizes candidate_baseline for maximum VPI performance  
  - **Purpose**: Generate VPI-optimized VRL variants
  - **Class**: `DFEVRLPerformanceOptimizer`
  - **Input**: candidate_baseline from baseline_stage
  - **Output**: optimized_vrl (best VPI performer)
  - **Success**: Higher VPI score than candidate_baseline

## 🔄 **Workflow:**

### **Baseline Stage Workflow:**
```
baseline_vrl (optional) → baseline_stage → candidate_baseline
```

1. **Input**: Log samples + optional baseline_vrl
2. **Process**: LLM generation + error learning + validation
3. **Output**: candidate_baseline (proven working VRL)

### **Performance Stage Workflow:**
```
candidate_baseline → performance_stage → optimized_vrl
```

1. **Input**: candidate_baseline from baseline_stage
2. **Process**: Multi-candidate generation + VPI measurement + optimization cycles  
3. **Output**: optimized_vrl (best performing variant)

## 🎯 **Usage Examples:**

### **Baseline Stage Only:**
```python
from dfe_ai_parser_vrl import DFEVRLGenerator

generator = DFEVRLGenerator()
candidate_baseline, metadata = generator.generate(
    sample_logs=ssh_logs,
    device_type='ssh',
    baseline_vrl=existing_working_vrl  # Optional incumbent
)
```

### **Complete Two-Stage Optimization:**
```python
from dfe_ai_parser_vrl import DFEVRLGenerator, DFEVRLPerformanceOptimizer

# Stage 1: Establish working baseline
generator = DFEVRLGenerator()
candidate_baseline, _ = generator.generate(sample_logs, device_type='ssh')

# Stage 2: Performance optimization  
optimizer = DFEVRLPerformanceOptimizer()
optimized_vrl, metrics = optimizer.run_performance_optimization(
    log_file=log_path,
    baseline_vrl=candidate_baseline
)
```

## 📚 **Benefits of Standardized Terminology:**

✅ **Clear Progression**: baseline_vrl → candidate_baseline → optimized_vrl  
✅ **Intuitive Names**: baseline (foundation), candidate (working), optimized (best)
✅ **Short & Memorable**: Easy to use in code and documentation
✅ **Consistent Purpose**: Each term reflects its role in the workflow
✅ **Scalable**: Can add more stages (e.g., production_vrl) following same pattern

This terminology structure supports **incumbent-based learning** where each stage builds on **proven working patterns** from the previous stage.