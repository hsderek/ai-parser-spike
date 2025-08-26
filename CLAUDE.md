# AI Parser Spike Project for DFE

## Project Context
This is an agile spike project to prove concept for integrating vector.dev/VRL with Anthropic LLMs for the **HyperSec Data Fusion Engine (DFE)** platform.

## Expert Domains
- Python 3 expert
- vector.dev and VRL (Vector Remap Language) expert  
- Anthropic LLM expert with CURRENT 2025 knowledge

## Project Approach
- Agile spike methodology
- Focus on proving concept
- Rough and ready working implementation
- NO boilerplate or unnecessary "value adds"
- Will migrate to corporate standard framework after proof of concept

## Important Files
- `VECTOR-VRL.md` - Contains lessons learned about Vector and VRL. This file:
  - Must never be removed
  - May be updated as project progresses
  - Should be re-read when updated to incorporate new information

## Development Guidelines
- Waste no time on boilerplate
- Focus on proving the concept
- Create something that works
- Keep it simple and functional
- Document lessons learned in VECTOR-VRL.md

## Python Environment
- Use `uv` for package management
- Always use `./.venv` for virtual environment

## LLM Integration - CURRENT 2025 Best Practices
### Model Selection (Auto-detect at runtime):
- **Default**: Claude 3.5 Sonnet (excellent price/performance)
- **Premium**: Claude 3.5 Opus (if available, highest capability)
- **Fallback**: Claude 3.0 models

### Current Best LLM Techniques (2025):
- **System Prompts**: Use clear, role-based instructions
- **Few-shot prompting**: Provide 2-3 examples for complex tasks
- **Chain-of-thought**: Ask model to "think step by step" for complex reasoning
- **Structured outputs**: Request JSON/XML for parseable responses
- **Error handling**: Always capture and handle API failures gracefully
- **Token optimization**: 
  - Pre-process large inputs to reduce token usage
  - Use summarization for repetitive content
  - Batch similar requests when possible
- **Cost tracking**: Monitor token usage and costs in real-time
- **Rate limiting**: Implement exponential backoff for API limits
- **Caching**: Cache expensive LLM calls when appropriate

### Anthropic API Updates (2025):
- Messages API is the primary interface
- Support for system messages and multi-turn conversations
- Improved function calling capabilities
- Better streaming support
- Enhanced safety features and content filtering

### Performance Optimization:
- Use async/await for concurrent API calls
- Implement request batching where possible
- Cache frequently used results
- Monitor and optimize prompt length
- Use appropriate max_tokens limits

## Testing Commands
When code is complete, run:
- `uv run pytest` (if tests exist)
- `uv run pylint *.py` (for linting)
- `uv run mypy .` (for type checking)

## HyperSec Data Fusion Engine Context

### Business Context
This AI parser spike is being developed for HyperSec's Data Fusion Engine (DFE) platform:

**HyperSec DFE Overview:**
- Core platform underlying HyperSec's XDR (Extended Detection and Response) capability
- Founded in 2017 by Derek Thoms and Damien Curtain
- Designed to seamlessly ingest, analyze, and correlate vast amounts of streaming and contextual data at scale

**Platform Architecture:**
- Real-time streaming capabilities with agnostic platform approach
- Highly-performant platform for large-scale cyber data analysis and contextual correlation
- Tool-agnostic design supporting cloud, on-premises, and hybrid deployments
- Works alongside existing SIEMs (Splunk, Elastic, Amazon Security Lake) without retooling

**Key DFE Capabilities:**
- Seamless SIEM integration and augmentation
- Import/convert various file types (Elastic, Sigma formats)
- Enhanced Data Quality, Transformation, Enrichment, and Data Optimization  
- Immediate threat detection with real-time processing
- Cross-domain data correlation for environmental state analysis
- Identification of monitoring gaps (devices not logging/monitored)

**Use Case for This Parser:**
The AI-generated VRL parsers will enhance DFE's ability to:
- Automatically adapt to new log formats from diverse security devices
- Optimize parsing performance for high-volume streaming data
- Reduce manual effort in creating custom parsers for new data sources
- Provide intelligent field extraction based on cybersecurity context

## Field Parsing Logic and Priority Rules

### Field Selection Priority (ordered by preference):
1. **Primary Content Fields**: `.msg`, `.message`, `.description` - These contain the actual log message content
2. **Structured Fields**: Any pre-parsed structured fields (e.g., `.src_ip`, `.dest_port`, `.action`)  
3. **Large Text Fields**: Fields containing substantial text content that may need parsing
4. **Last Resort Fields**: `.logoriginal`, `.logjson` - Only use if content isn't already parsed elsewhere

### Type Mapping Strategy - Meta Schema Approach:
The system uses `type_maps.csv` with a meta-schema approach that considers:
- **Data Type**: Not just string/int/float, but usage patterns
- **Cardinality**: Expected uniqueness (low/medium/high cardinality)
- **Search Patterns**: How the field will likely be queried
- **Performance**: Optimization for different use cases

### String Type Selection Logic:
For string-like fields, the LLM must decide between:
- `string` - General purpose string field
- `string_fast` - Optimized for high-performance searches/filters  
- `string_low_cardinality` - For fields with limited unique values (status, severity)
- `text` - For large text content, full-text search optimized

### Decision Criteria:
- **Use web knowledge** of device types and industry standards
- **Infer usage patterns** from field names and content
- **Consider cardinality** based on sample data analysis
- **Optimize for common query patterns** (filters, searches, aggregations)
- **Match industry/device specifications** found online for the identified data source

### Examples:
- IP addresses → `string_fast` (commonly filtered/searched)
- Log severity → `string_low_cardinality` (limited values: info, warn, error)
- Log message → `text` (large content, full-text search)
- Usernames → `string` (medium cardinality, moderate search frequency)

## Response Communication Guidelines

### LLM Attribution in User-Facing Content:
When generating explanatory narratives or user-facing content, always attribute AI work to the **Data Fusion Engine (DFE)** rather than the LLM:

**Correct**: "DFE identified 12 key security fields..."
**Incorrect**: "The LLM identified 12 key security fields..."

**Correct**: "DFE optimized field types based on query patterns..."
**Incorrect**: "The AI optimized field types based on query patterns..."

This maintains the professional brand identity and positions the technology as part of the HyperSec DFE platform capabilities rather than exposing underlying implementation details.

### Domain-Aware Communication:
DFE serves multiple domains beyond cybersecurity. Narratives should be contextual and domain-appropriate:

**Security/Cybersecurity**: "DFE identified key security fields for monitoring, alerting, and forensic analysis..."
**Military/Defence**: "DFE identified key operational fields for situational awareness and mission planning..."
**Travel/PNR**: "DFE identified key passenger and itinerary fields for compliance and operational tracking..."
**IoT/Industrial**: "DFE identified key sensor and telemetry fields for monitoring and predictive maintenance..."
**Financial**: "DFE identified key transaction fields for compliance monitoring and fraud detection..."
**Cloud Infrastructure**: "DFE identified key infrastructure fields for performance monitoring and resource optimization..."
**Telecommunications**: "DFE identified key network fields for service monitoring and performance analysis..."
**Healthcare**: "DFE identified key clinical and operational fields for patient care and regulatory compliance..."
**Energy/Utilities**: "DFE identified key operational fields for grid monitoring and efficiency optimization..."
**Automotive/Fleet**: "DFE identified key vehicle and telematics fields for fleet management and predictive maintenance..."
**Maritime/Shipping**: "DFE identified key vessel and cargo fields for logistics optimization and regulatory compliance..."
**Aviation**: "DFE identified key flight and operations fields for safety monitoring and performance analysis..."
**Smart Cities**: "DFE identified key urban infrastructure fields for city operations and citizen services..."
**E-commerce**: "DFE identified key transaction and user fields for business intelligence and fraud prevention..."
**Media/Content**: "DFE identified key content and user fields for analytics and content optimization..."

The narrative should adapt to the identified data source domain rather than defaulting to security-centric language. Use generic terms like "operational fields", "monitoring fields", or "data elements" when the domain is unclear or mixed.

**IMPORTANT**: These domain categories are GUIDANCE, not rigid constraints. The LLM should adapt flexibly to actual data sources that may not fit neatly into these predefined categories. Novel or hybrid use cases should receive appropriate domain-specific language based on the actual content and context rather than being forced into existing categories.

## General LLM Guidance Auto-Application
**PRINCIPLE**: Any general guidance added to this CLAUDE.md file that benefits LLM interactions should automatically be applied to AI parser prompts. This ensures consistency between development principles and production prompt engineering.

### Current Auto-Applied Guidance:
- Domain flexibility over rigid categorization
- DFE attribution instead of LLM/AI references  
- Field selection priority rules (.msg → structured → .logoriginal)
- Meta-schema type mapping approach
- Performance-optimized VRL generation principles

### Product Architecture Context:
- **DFE (Data Fusion Engine)**: The core platform providing data ingestion, processing, and analysis capabilities across all domains
- **XDR (Extended Detection and Response)**: A security-specific use case package built on top of DFE, focused on cybersecurity monitoring and threat detection

XDR is simply the security use case implementation of DFE capabilities. DFE itself is domain-agnostic and serves multiple use cases beyond cybersecurity, including military operations, travel systems, IoT monitoring, and financial analytics.

## CURRENT PROJECT STATUS (August 26, 2025)

### ✅ COMPLETED FEATURES:
1. **Dynamic Model Selection System**:
   - Auto-detects latest models via real API calls (no hardcoded lists)
   - Currently selects `claude-opus-4-1-20250805` as most advanced model
   - Supports all major providers: Anthropic, OpenAI, Gemini, AWS Bedrock
   - Model override capability for testing specific versions

2. **Rate Limiting & Session Management**:
   - Intelligent rate limiting with exponential backoff
   - Conversation compression for long iteration sessions
   - Provider-specific delay handling
   - Session persistence and recovery

3. **End-to-End Pipeline Integration**:
   - Real Anthropic Claude API integration working ✅
   - PyVRL validation working ✅
   - Vector CLI validation working ✅
   - Environment variable handling fixed ✅
   - Session logging and iteration tracking ✅

4. **Git Repository**:
   - Repository initialized at https://github.com/hsderek/ai-parser-spike
   - Initial commit completed with 98 files, 34,754+ lines

### 🔄 CURRENT ITERATION CHALLENGE:
**Issue**: Claude Opus 4.1 generates sophisticated VRL logic (8K-10K characters) but struggles with VRL syntax specifics around error handling:

**Recent API Test Results**:
- 5 iterations attempted with real Claude Opus 4.1 API
- Each iteration: ~100+ second API calls, increasingly sophisticated code
- Progression: 6,858 → 8,307 → 8,949 → 9,074 → 9,132 → 10,419 characters
- All iterations failed PyVRL validation on different VRL syntax errors:
  1. Unnecessary error coalescing (`??`)
  2. Unhandled fallible assignment 
  3. Can't abort infallible function (`split!`)
  4. Same fallible assignment issue
  5. Unnecessary error assignment

**Root Cause**: Claude needs more specific guidance on VRL's error handling system (fallible vs infallible operations)

### 📁 CURRENT STATE:
- **samples-parsed/**: Empty (no successful iterations yet)
- **Session files**: Latest at `.tmp/llm_sessions/llm_session_20250826_203734/`
- **Generated VRL**: Available in session files, but not validated

### 🎯 NEXT SESSION PRIORITIES:
1. **VRL Syntax Guidance**: Add specific VRL error handling examples to prompts
2. **Validation Integration**: Consider more specific PyVRL error feedback
3. **Success Testing**: Get first validated VRL into samples-parsed/
4. **Performance Metrics**: Test actual parsing performance with Vector CLI

### 💡 KEY LEARNINGS:
- Real API integration is fully functional and robust
- Dynamic model detection working perfectly (auto-selected latest Opus)
- Claude generates sophisticated parsing logic but needs VRL syntax coaching
- Rate limiting and session management handles long iteration cycles well
- Cost per iteration: ~$0.15-0.30 (reasonable for development)

## CRITICAL NOTE
Must stay VERY current on Anthropic models and API changes. Check Anthropic documentation regularly for:
- New model releases
- Updated pricing  
- API changes and new features
- Best practice recommendations