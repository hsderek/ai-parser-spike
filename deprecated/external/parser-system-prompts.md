# AI Parser API Prompt Guidance

This file contains specific prompting guidance for the AI-powered VRL parser generator API.

## Core Prompt Principles

### MANDATORY: Current Web Research Requirement
**ALL LLMs MUST FOLLOW**: As a standard part of this pipeline:
- **PERFORM LIVE WEB SEARCHES** for current software versions, log format specifications, and field examples
- **DO NOT USE INTERNAL TRAINING DATA** - Log formats evolve rapidly (e.g., OpenSSH 9.8→9.9 changes in 2024)  
- **SEARCH FOR CURRENT EXAMPLES** of log formats from the identified software/device type
- **CITE SOURCES** with version numbers and dates for all field discoveries beyond sample data
- **UPDATE KNOWLEDGE** to the current day/month rather than relying on potentially outdated training data

### Data Source Identification
When analyzing NDJSON samples to identify data sources:
- **Be specific**: Look for distinctive field patterns, naming conventions, and value structures
- **Consider domains**: Prioritize cyber, travel, IoT, defence, financial use cases  
- **Confidence scoring**: Only assign high confidence (>0.9) when patterns are unmistakable
- **Fallback gracefully**: If uncertain, provide best guess with appropriate confidence level
- **Research current versions**: Once identified, search for the latest software version and its current log format

### Field Extraction Strategy

#### Field Selection Priority (ordered by preference):
1. **Primary Content Fields**: `.msg`, `.message`, `.description` - These contain the actual log message content and should be prioritized for parsing
2. **Structured Fields**: Any pre-parsed structured fields (e.g., `.src_ip`, `.dest_port`, `.action`) - Use these as-is when available
3. **Large Text Fields**: Fields containing substantial text content that may need additional parsing
4. **Last Resort Fields**: `.logoriginal`, `.logjson` - Only use if content isn't already parsed elsewhere in the record

#### Type Mapping Strategy - Meta Schema Approach:
The system uses `type_maps.csv` with a meta-schema approach that considers:
- **Data Type**: Not just basic types (string/int/float), but usage patterns and performance characteristics
- **Cardinality**: Expected uniqueness levels (low/medium/high cardinality) based on sample analysis
- **Search Patterns**: How the field will likely be queried in production (filters, searches, aggregations)
- **Performance**: Optimization for different use cases and query patterns

#### String Type Selection Logic:
For string-like fields, the LLM must intelligently choose between:
- `string` - General purpose string field for moderate cardinality data
- `string_fast` - Optimized for high-performance searches/filters (IP addresses, IDs)
- `string_low_cardinality` - For fields with limited unique values (status, severity levels)
- `text` - For large text content optimized for full-text search

#### Decision Criteria:
- **MANDATORY WEB RESEARCH**: Must perform live web searches for current software versions and log format specifications
- **NO TRAINING DATA RELIANCE**: Do not use internal model knowledge - log formats change rapidly (e.g., OpenSSH 9.8 changed "sshd" to "sshd-session" in July 2024)  
- **Current Version Requirements**: Must identify and search for the latest software versions and their specific log formats
- **Evidence-Based Field Discovery**: Only add fields beyond sample data if concrete log examples are found via current web research
- **Parser Validation Required**: Must validate the generated VRL parser against the web-sourced log examples used to justify additional fields
- **Version-Specific Documentation**: Reference which software version/date the log format examples are from
- **Use web knowledge** of device types and industry standards to inform type selection
- **Infer usage patterns** from field names, content patterns, and industry context  
- **Consider cardinality** based on sample data analysis and expected real-world usage
- **Optimize for common query patterns** (filters, searches, aggregations) based on cybersecurity context
- **Match industry/device specifications** found online for the identified data source

#### Type Selection Examples:
- IP addresses → `string_fast` (commonly filtered/searched, medium cardinality)
- Log severity levels → `string_low_cardinality` (limited values: info, warn, error, critical)  
- Log message content → `text` (large content requiring full-text search capabilities)
- Usernames → `string` (medium cardinality, moderate search frequency)
- Device hostnames → `string_fast` (commonly used in filters and dashboards)

### LLM Error Pattern Supervision & Prevention

#### CRITICAL: VRL Error Code Prevention System
**All LLMs must avoid these specific Vector error codes:**

**E103 - Unhandled Fallible Assignment**
```vrl
❌ WRONG: parts = split(msg, ":")  # Can fail if msg is null
✅ CORRECT: parts = split!(msg, ":")  # Infallible version
```

**E105 - Call to Undefined Function**  
```vrl
❌ WRONG: string_fast!(.field)  # This function doesn't exist
✅ CORRECT: string!(.field)     # Use actual VRL functions
```

**E110 - Fallible Predicate**
```vrl
❌ WRONG: if contains(potentially_null_var, "pattern")
✅ CORRECT: if exists(.field) && contains(string!(.field), "pattern")
```

**E620 - Can't Abort Infallible Function**
```vrl
❌ WRONG: downcase!(string_value)  # downcase never fails
✅ CORRECT: downcase(string_value)  # No ! needed
```

**E651 - Unnecessary Error Coalescing**
```vrl
❌ WRONG: downcase(string!(.field)) ?? .field  # Left side can't fail
✅ CORRECT: downcase(string!(.field))          # Remove ??
```

#### Claude-Specific VRL Error Patterns (Applied when provider=anthropic)
When using Claude models, apply these specific error prevention patterns:

**CLAUDE CRITICAL ISSUE: Uses Imperative Loops (E205)**
```vrl
❌ NEVER DO THIS - VRL IS NOT IMPERATIVE:
for item in array {     # for/while loops DO NOT EXIST in VRL
  process(item)
}

✅ DO THIS INSTEAD - VRL IS FUNCTIONAL:
if contains(msg, "pattern") {
  parts = split!(msg, "delimiter")
  if length(parts) > 1 {
    .field = parts[1]
  }
}
```

**CLAUDE MISTAKE PATTERN 1: Fallible Predicate Errors (E110)**
```
# Claude's common mistake:
if contains(potentially_null_var, "pattern") {  # ERROR: E110
```
**Prevention Rule**: Always ensure variables are non-null before using in predicates:
```
# Correct pattern:
if exists(.field) && contains(string!(.field), "pattern") {
```

**CLAUDE MISTAKE PATTERN 2: Assuming Array Index Exists (E103)**
```
# Claude's common mistake:
parts = split(msg, ":")
field_value = parts[1]  # ERROR: parts[1] might not exist
```
**Prevention Rule**: Always check array length before access:
```
# Correct pattern:
parts = split(msg, ":")
if length(parts) > 1 {
  field_value = parts[1]  # Now safe
}
```

**CLAUDE MISTAKE PATTERN 3: Null Propagation in Nested Operations**
```
# Claude's common mistake:
parts = split(msg, "DELIMITER")
content = parts[1]  # Could be null
subparts = split(content, ":")  # ERROR: null argument
```
**Prevention Rule**: Use defensive nesting with length checks:
```
# Correct pattern:
parts = split(msg, "DELIMITER")
if length(parts) > 1 {
  content = parts[1]  # Guaranteed non-null
  subparts = split(content, ":")  # Now safe
}
```

#### IMPORTANT: Local Error Fixing System
**A sophisticated error-code-based fixing system will automatically fix common VRL syntax errors:**
- **E103**: Adds ! to fallible functions (split, parse_json, to_int, etc.)  
- **E105**: Maps invented functions to real VRL functions
- **E110**: Adds exists() checks and string coercion for null safety
- **E620**: Removes ! from infallible functions (contains, downcase, etc.)
- **E651**: Removes unnecessary ?? operators from expressions that can't fail
- **E203**: Fixes basic syntax issues like empty returns, dynamic array access

**Therefore, focus on generating semantically correct VRL rather than perfect syntax.** The local fixer will handle most syntax issues automatically.

#### Manual Error Recovery Instructions (When Local Fixer Insufficient)
When VRL validation still fails after local fixes, analyze the specific error and apply these recovery patterns:

**For E103 (unhandled fallible assignment):**
- Add length checks before array access
- Use `string!()` only when guaranteed non-null
- Wrap operations in existence checks

**For E110 (fallible predicate):**
- Ensure all predicate arguments are guaranteed non-null
- Use `exists()` checks before field access
- Apply `string!()` conversion within length-checked blocks

**For E651 (unnecessary error coalescing):**
- Remove `??` operators from infallible operations
- Use proper conditional logic instead of error coalescing

#### Provider-Specific Adaptations
```
# When provider == "anthropic" (Claude):
# - Apply extra defensive null checking
# - Use explicit length validation patterns  
# - Prioritize nested conditional structure over complex expressions

# When provider == "openai" (GPT):
# - Focus on clear function documentation
# - Emphasize return value handling
# - Use explicit error capture patterns

# When provider == "gemini":
# - Provide concrete examples
# - Use step-by-step logical flow
# - Emphasize type consistency
```

### VRL Code Generation Guidelines
**CRITICAL**: Always follow VECTOR-VRL.md guidelines for performance and syntax

#### Performance Optimization Priority:
1. **String operations over regex**: Use `contains()`, `split()`, `upcase()` instead of `match()`
2. **Early exits**: Add conditional checks to skip unnecessary processing
3. **Error handling**: Always use fallible operations with proper error capture
4. **Memory cleanup**: Remove temporary fields and error variables immediately

#### Code Structure Standards:
```vrl
# Pattern: Check existence, extract with error handling, cleanup
if exists(.field) {
    .result, .error = to_type(.field)
    if .error != null {
        del(.error)
        .result = default_value
    }
}
```

### Response Format Requirements
Always return structured JSON responses:
- **status**: "success" | "error"  
- **message**: Brief description of operation result
- **data**: Complete result payload including VRL code, fields, metrics
- **llm_usage**: Token usage and cost tracking

## Domain-Specific Prompting

### Cyber Security Logs
Key indicators:
- Fields: `timestamp`, `level`, `source_ip`, `dest_ip`, `event_type`, `severity`
- Patterns: IP addresses, log levels, security events
- Standards: CEF, LEEF, Syslog RFC formats
- Focus on: Authentication events, network traffic, security alerts

### Travel/PNR Data  
Key indicators:
- Fields: `passenger_name`, `pnr_code`, `flight_number`, `departure_date`
- Patterns: IATA codes, date formats, booking references
- Standards: EDIFACT PNRGOV messages, GDS formats
- Focus on: Passenger details, itinerary data, booking status

### IoT Device Logs
Key indicators:
- Fields: `device_id`, `sensor_type`, `measurement`, `battery_level`
- Patterns: UUID device identifiers, numeric measurements, timestamps
- Standards: MQTT message formats, LoRaWAN payloads
- Focus on: Device telemetry, status updates, alerts

### Defence/Military
Key indicators:
- Fields: `unit_id`, `position`, `classification`, `operation_code`
- Patterns: Military time formats, coordinate systems, classification levels
- Standards: Link-16, VMF formats where applicable
- Focus on: Operational data, situational awareness, communications

### Financial Systems
Key indicators:
- Fields: `transaction_id`, `amount`, `currency`, `account_number`
- Patterns: ISO currency codes, decimal amounts, account formats
- Standards: ISO 20022, SWIFT message types
- Focus on: Transaction data, account activity, fraud indicators

## Prompt Engineering Techniques

### Chain of Thought for Complex Analysis
"Analyze this data step by step:
1. First, examine the field names and patterns
2. Look for domain-specific indicators  
3. Consider the data structure and formats
4. Make confidence assessment based on evidence
5. Provide final classification with reasoning"

### Few-Shot Examples
Include 2-3 examples of similar data source classifications:
```
Example 1: Apache access logs -> {"name": "Apache Access Logs", "confidence": 0.95, ...}
Example 2: Kubernetes logs -> {"name": "Kubernetes Container Logs", "confidence": 0.88, ...}
```

### Error Recovery Prompting
"If the data doesn't match known patterns:
1. Identify the closest similar data source type
2. Note what's different or unusual
3. Assign confidence ≤0.7 for uncertain classifications
4. Suggest generic parsing approaches"

## Quality Assurance

### Response Validation
Always validate LLM responses:
- JSON structure correctness
- Field type mappings exist in type_maps.csv
- VRL syntax follows VECTOR-VRL.md guidelines
- Performance estimates are realistic
- Cost tracking is accurate

### Fallback Strategies
- **Data source unknown**: Use generic "Structured Application Logs"
- **Field parsing fails**: Default to string type extraction  
- **VRL generation errors**: Provide basic field extraction patterns
- **API failures**: Return cached/default responses when possible

## Cost Optimization

### Token Usage Reduction
- **Pre-process samples**: Remove repetitive content
- **Summarize large payloads**: Focus on unique field patterns
- **Batch similar requests**: Combine related analysis tasks
- **Cache common patterns**: Store results for similar data sources

### Model Selection Strategy
- **Opus**: Complex analysis, unknown data sources, high accuracy requirements
- **Sonnet**: Standard log analysis, known patterns, production workloads
- **Auto**: Let system choose based on complexity and confidence thresholds

## Testing and Validation

### Required Test Cases
1. **Standard formats**: Apache, Nginx, Kubernetes, Syslog
2. **Malformed data**: Invalid JSON, missing fields, truncated logs
3. **Edge cases**: Empty files, single records, very large payloads
4. **Domain variations**: Each target domain with representative samples
5. **Performance limits**: High field counts, complex nested structures

### Success Criteria
- **Accuracy**: >90% correct field type inference
- **Performance**: Generated VRL processes >10k events/sec
- **Cost efficiency**: <$0.10 per 100 log samples analyzed
- **Error handling**: Graceful degradation for all edge cases