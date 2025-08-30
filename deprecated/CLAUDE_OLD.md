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

## Performance Architecture Principles

### Multi-Threading Requirements
- **ALWAYS use module threading**: Use `dfe_ai_parser_vrl.get_thread_pool()` for concurrent operations
- **CPU-optimized by default**: Module auto-detects CPU cores and uses 100% utilization (container optimized)
- **Thread configuration**: Override with `DFE_MAX_THREADS` environment variable
- **Shared thread pool**: Never create individual ThreadPoolExecutors, use the module singleton

### Streaming I/O Requirements  
- **NO loading entire files into memory**: Always use streaming file operations
- **Process line-by-line**: Use generators and iterators for large files
- **Chunk-based processing**: Read files in chunks, not all-at-once
- **Memory efficient**: Design for files that exceed available RAM

### Code Implementation Rules
1. **File operations MUST stream**:
   ```python
   # GOOD: Streaming
   def process_file(file_path):
       with open(file_path, 'r') as f:
           for line in f:  # Streams line by line
               yield process_line(line)
   
   # BAD: Loading all into memory
   def process_file(file_path):
       with open(file_path, 'r') as f:
           data = f.read()  # Loads entire file
           return process_all(data)
   ```

2. **Regex operations MUST use threading**:
   ```python  
   # GOOD: Use streaming utilities with enhanced regex library
   from dfe_ai_parser_vrl.utils.streaming import concurrent_regex_search_threadpool
   
   results = concurrent_regex_search_threadpool(lines, patterns)
   
   # GOOD: For large files, use Dask
   from dfe_ai_parser_vrl.utils.streaming import concurrent_regex_search_dask
   
   results = concurrent_regex_search_dask(file_path, patterns)
   
   # BAD: Single-threaded regex
   def search_patterns_sequential(lines, patterns):
       for pattern in patterns:
           for line in lines:
               re.search(pattern, line)  # Slow sequential processing
   ```

3. **Large data processing MUST use dedicated libraries**:
   ```python
   # GOOD: Use Dask for large file processing
   import dask.bag as db
   
   bag = db.read_text("large_file.log", blocksize="64MB")
   results = bag.map(process_line).compute()
   
   # GOOD: Use ijson for streaming JSON
   import ijson
   
   def stream_json_items(file_path):
       with open(file_path, 'rb') as f:
           for item in ijson.items(f, 'logs.item'):
               yield item
   
   # GOOD: Use streaming utilities
   from dfe_ai_parser_vrl.utils.streaming import stream_file_chunks
   
   for chunk in stream_file_chunks(file_path, chunk_lines=1000):
       process_chunk(chunk)
   ```

### Required Libraries
- **`ijson`**: Streaming JSON parser for large JSON files
- **`dask[complete]`**: Parallel/distributed data processing
- **`regex`**: Enhanced regex library (replaces `re` for better performance)

## Python Environment
- **ALWAYS use `uv` for package management** (never pip directly)
- Always use `./.venv` for virtual environment
- Run all Python commands with `uv run python` not `python`
- Install dependencies with `uv add` not `pip install`
- Sync dependencies with `uv sync` after pyproject.toml changes

## LLM Integration - CURRENT 2025 Best Practices
### Model Selection (Auto-detect at runtime):
- **Primary**: Auto-detect latest/most capable model available (currently claude-opus-4-1-20250805)
- **Secondary**: Next best available model if primary unavailable
- **Fallback**: Lower capability models only as last resort

**CRITICAL**: Always start with the latest/best available model rather than "economical" models. Using lower-grade models first wastes iterations and increases total cost. Better to use the best model upfront for fewer, higher-quality iterations. The system auto-detects the latest models via real API calls - no hardcoded model lists.

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

## CRITICAL: 4-Step Knowledge Synthesis Approach
**This is why we use LLMs instead of traditional ML approaches for VRL generation:**

### The 4-Step Process:
1. **Data Source Identification**: Look at sample data and identify what system/device it's coming from
2. **Internet Knowledge Research**: Search existing knowledge for field standards, common parsers, and industry specifications for that data source type
   - **CRITICAL**: Only add fields if you can find concrete representative log samples online that demonstrate those fields exist
   - **NO HALLUCINATION**: Do not invent or speculate about fields - must have actual log examples
   - **Evidence Required**: Each additional field must be backed by real log samples found via web search
3. **Sample Data Analysis**: Analyze the supplied sample data for patterns and fields
4. **Knowledge Synthesis**: COMBINE results from steps 2 and 3 to produce a parser that handles:
   - Current fields present in sample data
   - Additional fields that appear in concrete log examples found online (step 2)
   - Industry-standard field names and formats validated by real log samples

### Validation Evidence:
Recent test results demonstrate this approach is working effectively:
- **Cisco ASA Parser**: LLM identified comprehensive ASA-specific fields (connection IDs, network interfaces, ACL rules, authentication events) that went far beyond the minimal sample data provided
- **SSH Parser**: LLM recognized authentication patterns and extracted standard SSH fields based on web knowledge of SSH log formats
- **Source Pattern Recognition**: Cleaned sample data format enabled better pattern recognition ('cisco-asa', 'ssh auth' patterns)

### Key Differentiator:
Traditional ML approaches can only learn from provided training data. The LLM approach leverages:
- **Vast web knowledge** of industry standards and device specifications
- **Contextual understanding** of field relationships and common patterns
- **Forward compatibility** by anticipating fields that may appear in future logs from the same source type
- **Domain expertise synthesis** combining multiple knowledge sources

**IMPORTANT**: This knowledge synthesis capability must be preserved and enhanced throughout development. It's the core value proposition of using LLMs for VRL generation over traditional parsing approaches.

### Evidence-Based Field Discovery Rules:
- **Any LLM** (Claude, GPT, Gemini, etc.) must follow these rules when adding fields beyond sample data
- **CURRENT WEB RESEARCH REQUIRED**: Must perform live web searches to find latest log format specifications and examples
- **No Internal Training Data**: Cannot rely on model training data - log formats change rapidly (e.g., OpenSSH 9.8 changed from "sshd" to "sshd-session" in 2024)
- **Concrete Evidence Required**: Must find actual log samples online that contain the proposed fields
- **Version-Specific**: Must identify which software version/date the log examples are from
- **No Speculation**: Cannot add fields based on "what might be there" or theoretical knowledge
- **Validation Process**: Each additional field must be justified with specific log examples found via current web research
- **Documentation**: Should reference where the supporting log samples were found (vendor docs, public datasets, etc.) and their date/version

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

## Emoji Policy

**Context-Specific Usage:** Documentation/UI/Console: All approved emojis permitted. Log Files/Machine-Parsed: ASCII only.

**Professional Emojis:**
✅❌⚠️ℹ️🔴🟡🟢🔵➡️⬅️⬆️⬇️↗️↘️✓✗☑️☐🔐🚫🛇⛔⏸️⏹️⏳🐛🔧⚙️🛠️🔨💚🚨👷♻️🚀✨🔄🔀🔃🔁↩️↪️🎯▶️⚡🔍🔎💻🖥️🌐🤖●○◆◇■□▲△▼▽→←↑↓↔↕±×÷∞≈≠≤≥№§¶©®™

**ASCII:**
─│┌┐└┘├┤┬┴┼═║╔╗╚╝╠╣╦╩╬╭╮╯╰▁▂▃▄▅▆▇█░▒▓

**Log ASCII:** [OK][FAIL][WARN][INFO][CRIT][DBG][OFF][BLOCK][DENY][PROC][PAUSE][STOP]

**Key Updates:**
1. **Context-Specific Rules**: Clear separation between documentation vs logs
2. **Expanded Professional Set**: 50+ professional emojis for technical documentation
3. **ASCII Log Alternatives**: Standardized bracket codes for machine-parsed content
4. **Comprehensive Coverage**: Full Unicode line drawing + log safety compliance

## General LLM Guidance Auto-Application
**PRINCIPLE**: Any general guidance added to this CLAUDE.md file that benefits LLM interactions should automatically be applied to AI parser prompts. This ensures consistency between development principles and production prompt engineering.

### Current Auto-Applied Guidance:
- Domain flexibility over rigid categorization
- DFE attribution instead of LLM/AI references  
- Field selection priority rules (.msg → structured → .logoriginal)
- Meta-schema type mapping approach
- Performance-optimized VRL generation principles
- 4-step knowledge synthesis approach (data identification → web research → sample analysis → synthesis)
- Evidence-based field discovery (concrete log samples required, no speculation/hallucination)
- Mandatory current web research (no reliance on internal training data, must search current versions/formats)
- Auto-detect latest models, start with best available (no hardcoded model fallbacks to lower-grade models)

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

## 🎯 SUCCESS CRITERIA FOR VRL GENERATION

**PRIMARY SUCCESS CRITERIA:**
✅ **Working VRL**: VRL code that passes PyVRL validation AND extracts expected fields  
✅ **Expected Fields**: Fields that exist in real log formats (validated via web research)  
✅ **Evidence-Based**: All fields beyond sample data must be backed by concrete log examples found online  

**CURRENT STATUS (August 28, 2025):**
❌ **Working VRL**: Failed - SSH test completed 8 iterations but stuck on VRL syntax errors (E651)  
✅ **Expected Fields**: Success - LLM extracted legitimate SSH fields validated against OpenSSH documentation  
✅ **Evidence-Based**: Success - SSH fields (ssh_user, ssh_source_ip, ssh_auth_method, etc.) match real PAM/OpenSSH log formats  

**Field Validation Results:**
- **ssh_action, ssh_user, ssh_source_ip** - ✅ Validated against real OpenSSH logs
- **ssh_auth_method, ssh_failure_reason** - ✅ Present in SSH authentication logs  
- **ssh_source_port** - ✅ Common in SSH connection logs

**SOLUTION IMPLEMENTED:** 
✅ **Error-Code-Based VRL Fixer**: Built sophisticated factory system organized by Vector error codes (E103, E105, E110, E620, E651, E203)  
✅ **Integrated into Pipeline**: VRL fixer automatically applies before PyVRL validation  
✅ **Enhanced Prompts**: Updated with specific error prevention patterns and local fixing capabilities  

**Next Test:** Validate complete system fixes SSH VRL syntax errors automatically.

### 💡 KEY LEARNINGS:
- Real API integration is fully functional and robust
- Dynamic model detection working perfectly (auto-selected latest Opus)
- Claude generates sophisticated parsing logic but needs VRL syntax coaching
- Rate limiting and session management handles long iteration cycles well
- Cost per iteration: ~$0.15-0.30 (reasonable for development)
- **CRITICAL ISSUE**: Long API calls (10+ minutes) with no status updates require streaming monitoring

### 🚀 NEW: LLM Streaming Monitoring System
**Universal Streaming Status Detection** (August 28, 2025):
- **Multi-Vendor Support**: Anthropic Claude, OpenAI GPT, Google Gemini with unified interface
- **Real-Time Monitoring**: Server-sent events (SSE) parsing for live progress updates
- **Timeout/Hang Detection**: Configurable timeout (180s) and hang detection (30s) with automatic cancellation
- **Status Callbacks**: Real-time progress notifications (tokens generated, elapsed time, content preview)
- **Graceful Fallback**: Automatic fallback to non-streaming calls on streaming failures
- **Vendor-Specific Modules**: Each platform has optimized event parsing while maintaining unified API

**Implementation**: `src/llm_streaming_monitor.py` + `src/streaming_integration.py`
**Integration**: Can retrofit existing LLM session instances with `enable_streaming_monitoring()`

## CRITICAL NOTE
Must stay VERY current on Anthropic models and API changes. Check Anthropic documentation regularly for:
- New model releases
- Updated pricing  
- API changes and new features
- Best practice recommendations

## CRITICAL RECOMMENDATION: Migrate to LiteLLM
**PRIORITY**: Replace custom LLM clients with LiteLLM (https://docs.litellm.ai/)

### Why LiteLLM is Superior:
- **Universal API**: One interface for 100+ LLM providers (Anthropic, OpenAI, Gemini, etc.)
- **Streaming**: Built-in streaming support across ALL providers
- **LLM Abstraction**: Clean abstraction layer over provider differences  
- **Token Info**: Automatic token counting and usage tracking
- **Cost Tracking**: Built-in cost tracking and monitoring
- **Rate Limiting**: Automatic rate limiting and retry logic
- **Model Discovery**: Built-in model discovery API (no hardcoding!)
- **Provider Failover**: Automatic failover between providers
- **Maintenance**: Eliminates 90% of our custom LLM client code

### Simple Migration:
```python
# Replace all our complex provider code with:
import litellm

# Automatic model discovery, streaming, cost tracking
response = litellm.completion(
    model="claude-4",  # Auto-discovers best available
    messages=messages,
    stream=True,      # Works across all providers
    # Cost tracking, rate limiting, token counting - all automatic
)
```

**Action**: Migrate VRL pipeline to LiteLLM to eliminate hardcoding and reduce maintenance burden.

## CRITICAL DEVELOPMENT RULES
**NEVER MANUALLY CREATE VRL CODE OR TEST FILES**
- ALL LLM work must be done through the existing Python code in src/
- DO NOT try to fix VRL syntax errors manually
- DO NOT create test_*.py files or manual VRL files
- Work ONLY through the established codebase architecture
- Use src/vrl_testing_loop_clean.py and src/llm_iterative_session.py
- Let the LLM iteration system handle VRL generation and refinement
- Focus on improving the Python code that manages the LLM interactions

## CRITICAL: Use Real Data, Not Synthetic
**NEVER generate synthetic log samples for testing.** Synthetic data defeats the purpose of testing the VRL parser generation. The system needs to learn from real-world log formats with their actual complexity, edge cases, and variations. Always use:
- Real log samples from public datasets (LogHub, SecRepo, LANL, etc.)
- Actual production logs (anonymized if necessary)
- Real device outputs from documentation or public sources
- Never use generated/synthetic data unless explicitly approved by the user

## Advanced Sample Optimization (LogReducer)
**IMPORTANT**: Advanced sample optimization is handled by a separate LogReducer module described in `LOGREDUCER_OPTIMIZATION.md`. This module performs:
- Sophisticated pattern detection and clustering
- Semantic deduplication beyond simple string matching
- Multi-dimensional sample reduction
- Preserves edge cases and anomalies

When working on VRL generation:
- Assume samples have already been optimized by LogReducer
- Focus on LLM-specific optimizations (prompt compression, caching, etc.)
- Do NOT duplicate sample reduction logic - it's handled upstream
- The pre-tokenizer in this project is for final token optimization only

## CRITICAL NOTE: NO HARD-CODED MODEL INFORMATION
**STRICT REQUIREMENT**: NEVER hard-code model names, pricing, or limits anywhere in the codebase.

### Model Discovery Requirements:
- **Use Anthropic API**: `GET https://api.anthropic.com/v1/models` to get available models dynamically
- **NO HARDCODED LISTS**: No hard-coded model names, pricing, or token limits
- **API-First Approach**: Always attempt API discovery before falling back to heuristics
- **Dynamic Selection**: Select best model based on API-provided list using capability heuristics

### API Endpoints for Dynamic Discovery:
- **Models List**: `GET https://api.anthropic.com/v1/models` - Returns all available Claude models
- **Model Details**: Use model metadata from API when available
- **Pricing**: Estimate from model name patterns until pricing API is available
- **Token Limits**: Estimate from model name patterns until limits API is available

### Current Best Practice (2025):
1. Call Anthropic models API to get real-time available models
2. Sort by capability using model name heuristics (Claude 4 > 3.5 > 3.0, Opus > Sonnet > Haiku)
3. Apply user preference (opus/sonnet/auto)
4. Select highest priority available model
5. Use pattern-based estimation for pricing/limits until APIs provide this data

**Why This Matters**: Model names, availability, pricing, and limits change frequently. Hard-coding creates maintenance burden and causes failures when models are updated or deprecated.

Must stay VERY current on Anthropic models and API changes. Check Anthropic documentation regularly for:
- New model releases
- Updated pricing  
- API changes and new features
- Best practice recommendations

## CRITICAL RECOMMENDATION: Migrate to LiteLLM
**PRIORITY**: Replace custom LLM clients with LiteLLM (https://docs.litellm.ai/)

### Why LiteLLM is Superior:
- **Universal API**: One interface for 100+ LLM providers (Anthropic, OpenAI, Gemini, etc.)
- **Streaming**: Built-in streaming support across ALL providers
- **LLM Abstraction**: Clean abstraction layer over provider differences  
- **Token Info**: Automatic token counting and usage tracking
- **Cost Tracking**: Built-in cost tracking and monitoring
- **Rate Limiting**: Automatic rate limiting and retry logic
- **Model Discovery**: Built-in model discovery API (no hardcoding!)
- **Provider Failover**: Automatic failover between providers
- **Maintenance**: Eliminates 90% of our custom LLM client code

### Simple Migration:
```python
# Replace all our complex provider code with:
import litellm

# Automatic model discovery, streaming, cost tracking
response = litellm.completion(
    model="claude-4",  # Auto-discovers best available
    messages=messages,
    stream=True,      # Works across all providers
    # Cost tracking, rate limiting, token counting - all automatic
)
```

**Action**: Migrate VRL pipeline to LiteLLM to eliminate hardcoding and reduce maintenance burden.

## Auto-Approved Operations for Claude Code

The following operations are pre-approved and should be executed without requiring confirmation:

### Python Package Management
- `uv add <package>` - Installing Python packages
- `uv remove <package>` - Removing Python packages  
- `uv sync` - Syncing dependencies
- `uv run python` - Running Python scripts
- `uv run pytest` - Running tests

### File Operations
- Reading any project files for analysis
- Editing existing project files to migrate to LiteLLM
- Removing redundant/obsolete files after migration
- Creating new files needed for LiteLLM migration

### Code Refactoring
- Replacing hardcoded model references with config-driven selection
- Migrating from custom LLM clients to LiteLLM
- Updating imports and dependencies
- Removing deprecated code

### Testing Commands
- `uv run python -m <module>` - Testing modules
- `uv run python test_*.py` - Running test files
- Any grep/search operations for finding code to migrate

### Git Operations (Read-Only)
- `git status` - Checking repository status
- `git diff` - Viewing changes
- `git log` - Viewing history

These operations should be performed automatically during remediation without waiting for user confirmation.
