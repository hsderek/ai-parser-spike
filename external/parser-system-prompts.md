# AI Parser API Prompt Guidance

This file contains specific prompting guidance for the AI-powered VRL parser generator API.

## Core Prompt Principles

### Data Source Identification
When analyzing NDJSON samples to identify data sources:
- **Be specific**: Look for distinctive field patterns, naming conventions, and value structures
- **Consider domains**: Prioritize cyber, travel, IoT, defence, financial use cases
- **Confidence scoring**: Only assign high confidence (>0.9) when patterns are unmistakable
- **Fallback gracefully**: If uncertain, provide best guess with appropriate confidence level

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