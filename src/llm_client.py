import asyncio
import json
import random
from typing import List, Dict, Any, Optional
import anthropic
from .config import Config
from .logging_config import get_logger, log_llm_usage
from .models import SampleData, DataSource, ExtractedField, LLMUsage, ParserSource


class LLMClient:
    def __init__(self, config: Config):
        self.config = config
        self.logger = get_logger("LLMClient")
        self.client = anthropic.Anthropic(api_key=config.anthropic_api_key)
        self.usage = LLMUsage()
        
        # Auto-detect best available model
        self.model_name = self._detect_best_model(config.llm_model_preference)
        self.input_cost_per_token, self.output_cost_per_token = self._get_model_pricing(self.model_name)
        
        # Model token limits (from Anthropic docs 2025)
        self.model_limits = self._get_model_limits(self.model_name)
        
        self.logger.info(f"Initialized LLM client with model: {self.model_name}")
        self.logger.info(f"Context limit: {self.model_limits['context_tokens']:,} tokens, Output limit: {self.model_limits['output_tokens']:,} tokens")
        print(f"Using LLM model: {self.model_name}")
        print(f"Model context limit: {self.model_limits['context_tokens']:,} tokens")
        print(f"Model output limit: {self.model_limits['output_tokens']:,} tokens")
    
    def _detect_best_model(self, preference: str) -> str:
        """Detect the best available Claude model at runtime"""
        # Latest models as of August 2025 - Claude 4.1 series should be available
        # Check Anthropic's console for most current model versions
        opus_models = [
            "claude-4-opus-20250801",     # Latest Claude 4.1 Opus (if available)
            "claude-3-5-opus-20241022",   # Claude 3.5 Opus 
            "claude-3-opus-20240229",     # Fallback to 3.0 Opus
        ]
        
        sonnet_models = [
            "claude-4-sonnet-20250801",   # Latest Claude 4.1 Sonnet (if available)
            "claude-3-5-sonnet-20241022", # Latest Sonnet v2
            "claude-3-5-sonnet-20240620", # Original Sonnet 3.5
            "claude-3-sonnet-20240229"    # Original Sonnet 3.0
        ]
        
        if preference.lower() == "sonnet":
            candidates = sonnet_models + opus_models  # Prefer Sonnet (cheaper, very capable)
        elif preference.lower() == "opus": 
            candidates = opus_models + sonnet_models  # Prefer Opus (most capable)
        else:  # auto - default to latest Opus for highest quality (as per user preference)
            candidates = opus_models + sonnet_models
        
        # In production, this should test each model for availability
        # For now, return first candidate
        return candidates[0]
    
    def _get_model_pricing(self, model_name: str) -> tuple:
        """Get pricing for the selected model (input_cost, output_cost per token)"""
        # Updated pricing as of August 2025 - Claude 4.1 pricing TBD
        pricing = {
            # Claude 4.1 models (estimated pricing - check Anthropic for actual rates)
            "claude-4-opus-20250801": (18.00 / 1_000_000, 90.00 / 1_000_000),      # Estimated 4.1 Opus
            "claude-4-sonnet-20250801": (4.00 / 1_000_000, 20.00 / 1_000_000),     # Estimated 4.1 Sonnet
            
            # Claude 3.5 models (current known pricing)
            "claude-3-5-opus-20241022": (15.00 / 1_000_000, 75.00 / 1_000_000),
            "claude-3-opus-20240229": (15.00 / 1_000_000, 75.00 / 1_000_000),
            
            # Sonnet models (excellent price/performance)
            "claude-3-5-sonnet-20241022": (3.00 / 1_000_000, 15.00 / 1_000_000),
            "claude-3-5-sonnet-20240620": (3.00 / 1_000_000, 15.00 / 1_000_000),
            "claude-3-sonnet-20240229": (3.00 / 1_000_000, 15.00 / 1_000_000),
        }
        
        # Default to Sonnet pricing if model not found  
        return pricing.get(model_name, (3.00 / 1_000_000, 15.00 / 1_000_000))
    
    def _get_model_limits(self, model_name: str) -> Dict[str, int]:
        """Get token limits for the selected model (from Anthropic docs 2025)"""
        limits = {
            # Claude 4.1 models
            "claude-4-opus-20250801": {"context_tokens": 200000, "output_tokens": 32000},
            "claude-4-sonnet-20250801": {"context_tokens": 200000, "output_tokens": 64000},
            
            # Claude 3.5 models  
            "claude-3-5-opus-20241022": {"context_tokens": 200000, "output_tokens": 32000},
            "claude-3-opus-20240229": {"context_tokens": 200000, "output_tokens": 32000},
            
            # Sonnet models
            "claude-3-5-sonnet-20241022": {"context_tokens": 200000, "output_tokens": 64000},
            "claude-3-5-sonnet-20240620": {"context_tokens": 200000, "output_tokens": 64000},
            "claude-3-sonnet-20240229": {"context_tokens": 200000, "output_tokens": 64000},
            
            # Haiku models
            "claude-3-5-haiku-20241022": {"context_tokens": 200000, "output_tokens": 8192},
        }
        
        # Default to Sonnet limits if model not found
        return limits.get(model_name, {"context_tokens": 200000, "output_tokens": 64000})
    
    def _estimate_token_count(self, text: str) -> int:
        """
        Estimate token count using Claude's approximate rule: ~4 characters per token
        This is a rough approximation - actual tokenization can vary
        """
        # Claude tokenizer approximation: ~4 characters per token for English text
        # This is conservative - JSON and structured data might be different
        return max(1, len(text) // 4)
    
    def _smart_sample_data(self, sample_data: SampleData, target_tokens: int) -> SampleData:
        """
        Intelligently sample data to fit within token limits while preserving diversity
        """
        original_text = sample_data.original_sample
        current_tokens = self._estimate_token_count(original_text)
        
        if current_tokens <= target_tokens:
            return sample_data  # No sampling needed
        
        print(f"Token protection: Estimated {current_tokens:,} tokens, target {target_tokens:,}")
        print("Applying smart sampling to reduce input size...")
        
        try:
            # Parse NDJSON lines
            lines = [line.strip() for line in original_text.strip().split('\n') if line.strip()]
            json_objects = []
            
            for line in lines:
                try:
                    obj = json.loads(line)
                    json_objects.append(obj)
                except json.JSONDecodeError:
                    continue
            
            if not json_objects:
                # Fallback to simple text truncation
                target_chars = target_tokens * 4
                truncated_text = original_text[:target_chars]
                return SampleData(
                    original_sample=truncated_text,
                    field_analysis=sample_data.field_analysis,
                    data_source_hints=sample_data.data_source_hints,
                    common_patterns=sample_data.common_patterns
                )
            
            # Smart sampling strategy:
            # 1. Always include first few samples for consistency
            # 2. Sample randomly from the rest to preserve diversity
            # 3. Include samples with unique field combinations
            
            sampled_objects = []
            
            # Strategy 1: Always include first 2-3 samples for consistency
            guaranteed_samples = min(3, len(json_objects))
            sampled_objects.extend(json_objects[:guaranteed_samples])
            remaining_objects = json_objects[guaranteed_samples:]
            
            # Strategy 2: Smart sampling based on unique field combinations
            if remaining_objects:
                # Group by unique field sets to ensure diversity
                field_signatures = {}
                for i, obj in enumerate(remaining_objects):
                    # Create signature from field names
                    signature = tuple(sorted(obj.keys()))
                    if signature not in field_signatures:
                        field_signatures[signature] = []
                    field_signatures[signature].append((i, obj))
                
                # Sample from each unique field signature
                for signature, objects in field_signatures.items():
                    # Take one random sample from each unique field pattern
                    if objects:
                        _, sampled_obj = random.choice(objects)
                        sampled_objects.append(sampled_obj)
            
            # Strategy 3: If still under target, add more random samples
            remaining_budget = target_tokens - self._estimate_token_count(
                '\n'.join(json.dumps(obj, separators=(',', ':')) for obj in sampled_objects)
            )
            
            if remaining_budget > 1000 and remaining_objects:  # Leave room for other prompt text
                available_objects = [obj for obj in remaining_objects 
                                   if obj not in [s for s in sampled_objects]]
                
                while available_objects and remaining_budget > 500:
                    candidate = random.choice(available_objects)
                    candidate_tokens = self._estimate_token_count(
                        json.dumps(candidate, separators=(',', ':'))
                    )
                    
                    if candidate_tokens <= remaining_budget:
                        sampled_objects.append(candidate)
                        remaining_budget -= candidate_tokens
                        available_objects.remove(candidate)
                    else:
                        break
            
            # Rebuild sample data
            sampled_text = '\n'.join(json.dumps(obj, separators=(',', ':')) for obj in sampled_objects)
            final_tokens = self._estimate_token_count(sampled_text)
            
            print(f"Smart sampling complete: {len(sampled_objects)} samples, ~{final_tokens:,} tokens")
            print(f"Preserved {len(sampled_objects)}/{len(json_objects)} samples ({len(sampled_objects)/len(json_objects)*100:.1f}%)")
            
            return SampleData(
                original_sample=sampled_text,
                field_analysis=sample_data.field_analysis,
                data_source_hints=sample_data.data_source_hints,
                common_patterns=sample_data.common_patterns
            )
            
        except Exception as e:
            print(f"Smart sampling failed: {e}")
            # Fallback to simple truncation
            target_chars = target_tokens * 4
            truncated_text = original_text[:target_chars]
            print(f"Falling back to simple truncation: {len(truncated_text):,} characters")
            
            return SampleData(
                original_sample=truncated_text,
                field_analysis=sample_data.field_analysis,
                data_source_hints=sample_data.data_source_hints,
                common_patterns=sample_data.common_patterns
            )
    
    async def identify_data_source(self, sample_data: SampleData) -> Optional[DataSource]:
        self.logger.info("Starting data source identification")
        
        # Apply token protection - reserve 80% for input, 20% for system/response
        max_input_tokens = int(self.model_limits['context_tokens'] * 0.8)
        
        # Sample data if needed to fit within token limits
        # Apply more aggressive sampling if we're approaching limits
        target_factor = 0.3 if self._should_apply_aggressive_sampling() else 0.5
        protected_sample_data = self._smart_sample_data(sample_data, int(max_input_tokens * target_factor))
        
        # Count samples from the original_sample text
        sample_count = len([line for line in protected_sample_data.original_sample.strip().split('\n') if line.strip()])
        self.logger.debug(f"Using {sample_count} samples for data source identification")
        prompt = self._build_data_source_prompt(protected_sample_data)
        
        try:
            self.logger.debug(f"Making LLM API call to {self.model_name}")
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.client.messages.create(
                    model=self.model_name,
                    max_tokens=1000,
                    messages=[{"role": "user", "content": prompt}]
                )
            )
            
            # Try to get response headers if available
            headers = getattr(response, 'response', {}).get('headers', {}) if hasattr(response, 'response') else {}
            self._track_usage(response.usage, headers)
            
            # Log LLM usage
            log_llm_usage(
                model=self.model_name,
                tokens=response.usage.input_tokens + response.usage.output_tokens,
                cost=self._calculate_cost(response.usage.input_tokens, response.usage.output_tokens),
                operation="data_source_identification"
            )
            
            # Handle different response content types
            text_content = ""
            for block in response.content:
                if hasattr(block, 'text'):
                    text_content = block.text
                    break
            
            result = self._parse_data_source_response(text_content)
            self.logger.info(f"Data source identified: {result.name if result else 'Unknown'}")
            return result
        except Exception as e:
            self.logger.error(f"Error identifying data source: {e}")
            print(f"Error identifying data source: {e}")
            return None
    
    async def research_parsers(self, data_source: Optional[DataSource], fields: List[ExtractedField]) -> Dict[str, Any]:
        """Research existing parsers and provide source attribution"""
        if not data_source:
            return {}
        
        self.logger.info(f"Starting parser research for data source: {data_source.name}")
        
        # Apply token protection for parser research
        max_input_tokens = int(self.model_limits['context_tokens'] * 0.8)
        
        # If we have too many fields, sample them intelligently
        if len(fields) > 20:  # Reasonable threshold for field analysis
            self.logger.debug(f"Token protection: Sampling {len(fields)} fields down to 20 for parser research")
            print(f"Token protection: Sampling {len(fields)} fields down to 20 for parser research")
            # Prioritize high-value fields
            high_value_fields = [f for f in fields if f.is_high_value]
            other_fields = [f for f in fields if not f.is_high_value]
            
            # Keep all high-value fields if reasonable, otherwise sample
            if len(high_value_fields) <= 15:
                sampled_fields = high_value_fields
                remaining_slots = min(20 - len(high_value_fields), len(other_fields))
                sampled_fields.extend(random.sample(other_fields, remaining_slots))
            else:
                sampled_fields = random.sample(high_value_fields, 15)
                sampled_fields.extend(random.sample(other_fields, 5))
            
            fields = sampled_fields
            self.logger.debug(f"Sampled to {len(fields)} fields for research")
        
        prompt = self._build_parser_research_prompt(data_source, fields)
        
        try:
            self.logger.debug(f"Making parser research API call to {self.model_name}")
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.client.messages.create(
                    model=self.model_name,
                    max_tokens=2000,
                    messages=[{"role": "user", "content": prompt}]
                )
            )
            
            # Try to get response headers if available
            headers = getattr(response, 'response', {}).get('headers', {}) if hasattr(response, 'response') else {}
            self._track_usage(response.usage, headers)
            
            # Log LLM usage
            log_llm_usage(
                model=self.model_name,
                tokens=response.usage.input_tokens + response.usage.output_tokens,
                cost=self._calculate_cost(response.usage.input_tokens, response.usage.output_tokens),
                operation="parser_research"
            )
            
            # Handle different response content types
            text_content = ""
            for block in response.content:
                if hasattr(block, 'text'):
                    text_content = block.text
                    break
            
            result = self._parse_parser_research_response(text_content)
            self.logger.info("Parser research completed successfully")
            return result
        except Exception as e:
            self.logger.error(f"Error researching parsers: {e}")
            print(f"Error researching parsers: {e}")
            return {}
    
    async def generate_explanation_narrative(
        self, 
        data_source: Optional[DataSource], 
        fields: List[ExtractedField], 
        parser_source: Optional[ParserSource] = None,
        performance_tier: Optional[int] = None
    ) -> str:
        """Generate a human-readable explanation of the parsing results and decisions"""
        
        self.logger.info("Generating explanatory narrative for parsing results")
        
        prompt = self._build_narrative_prompt(data_source, fields, parser_source, performance_tier)
        
        try:
            self.logger.debug("Making narrative generation API call")
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.client.messages.create(
                    model=self.model_name,
                    max_tokens=800,  # Longer response for narrative
                    messages=[{"role": "user", "content": prompt}]
                )
            )
            
            # Track usage
            headers = getattr(response, 'response', {}).get('headers', {}) if hasattr(response, 'response') else {}
            self._track_usage(response.usage, headers)
            
            # Log LLM usage
            log_llm_usage(
                model=self.model_name,
                tokens=response.usage.input_tokens + response.usage.output_tokens,
                cost=self._calculate_cost(response.usage.input_tokens, response.usage.output_tokens),
                operation="narrative_generation"
            )
            
            # Extract text content
            text_content = ""
            for block in response.content:
                if hasattr(block, 'text'):
                    text_content = block.text
                    break
            
            self.logger.info("Narrative generation completed successfully")
            return text_content.strip()
            
        except Exception as e:
            self.logger.error(f"Error generating narrative: {e}")
            # Return a fallback narrative
            return self._generate_fallback_narrative(data_source, fields, parser_source, performance_tier)
    
    def _build_data_source_prompt(self, sample_data: SampleData) -> str:
        return f"""Analyze this NDJSON sample data and identify the most likely data source type.

Sample data structure:
{sample_data.original_sample}

Field analysis:
{sample_data.field_analysis}

Data source hints found: {sample_data.data_source_hints}
Common patterns: {sample_data.common_patterns}

Please identify:
1. The most likely data source type (e.g., "Apache Access Logs", "Kubernetes Logs", "Syslog", "AWS CloudTrail", etc.)
2. Confidence level (0.0-1.0)
3. Brief description of why you think this is the data source
4. List of common field names typically found in this data source
5. Known parsing tools or libraries commonly used for this data source

Respond in this JSON format:
{{
    "name": "data_source_name",
    "confidence": 0.85,
    "description": "Brief explanation",
    "common_fields": ["field1", "field2", "field3"],
    "known_parsers": ["parser1", "parser2"]
}}"""

    def _build_parser_research_prompt(self, data_source: DataSource, fields: List[ExtractedField]) -> str:
        field_names = [f.name for f in fields]
        
        return f"""Research existing parsers and field naming conventions for {data_source.name}.

Fields to parse: {field_names}

Please provide comprehensive research including:

1. **Internet-Available Parsers**: 
   - Identify specific parsers, libraries, or projects available online for {data_source.name}
   - Include project names, GitHub repos, or well-known parsing solutions
   - Note which parsers are most commonly referenced or recommended

2. **Standard Field Names**: Used by popular tools (ELK stack, Splunk, QRadar, etc.)

3. **Existing Parsing Logic**: 
   - Regex patterns or parsing logic from established sources
   - VRL examples if available from Vector community
   - Performance-optimized approaches from production systems

4. **Source Attribution**:
   - Clearly identify which recommendations come from internet sources
   - Provide specific parser names, projects, or documentation sources
   - Rate confidence in source reliability (high/medium/low)

5. **Performance Recommendations**: Based on real-world implementations

Focus on:
- CPU-efficient parsing approaches from proven sources
- Standard naming conventions from established tools
- Attribution to specific internet-available parsers when applicable

Respond in JSON format:
{{
    "parser_sources": [
        {{
            "name": "parser_name_or_project",
            "type": "internet|documentation|custom", 
            "confidence": 0.9,
            "description": "Brief description of source and reliability"
        }}
    ],
    "field_recommendations": [
        {{
            "field": "field_name",
            "standard_name": "recommended_name",
            "parsing_approach": "string|regex|builtin",
            "performance_tier": "low|medium|high",
            "source": "which parser/project this recommendation comes from",
            "example_code": "VRL example if available"
        }}
    ],
    "overall_approach": {{
        "base_parser": "primary internet source to reference (if any)",
        "custom_enhancements": ["list of custom optimizations needed"],
        "source_type": "internet|custom|hybrid"
    }}
}}"""

    def _parse_data_source_response(self, response: str) -> Optional[DataSource]:
        try:
            import json
            
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                data = json.loads(response[json_start:json_end])
                return DataSource(**data)
        except Exception:
            pass
        
        return None
    
    def _parse_parser_research_response(self, response: str) -> Dict[str, Any]:
        """Parse the enhanced parser research response with source attribution"""
        try:
            # Try to extract JSON from the response
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                research_data = json.loads(response[json_start:json_end])
                
                # Extract parser source information
                parser_source = None
                if 'overall_approach' in research_data and 'parser_sources' in research_data:
                    approach = research_data['overall_approach']
                    sources = research_data['parser_sources']
                    
                    if sources:
                        source_names = [s.get('name', '') for s in sources]
                        source_confidence = sum(s.get('confidence', 0) for s in sources) / len(sources)
                        
                        parser_source = ParserSource(
                            type=approach.get('source_type', 'custom'),
                            sources=source_names,
                            confidence=source_confidence,
                            description=f"Based on {len(sources)} internet sources: {', '.join(source_names[:3])}"
                        )
                
                return {
                    "research_data": research_data,
                    "parser_source": parser_source,
                    "research_notes": response
                }
            else:
                # Fallback to text analysis if JSON parsing fails
                return {
                    "research_notes": response,
                    "parser_source": self._infer_parser_sources_from_text(response)
                }
        except json.JSONDecodeError:
            # Fallback to text analysis if JSON parsing fails
            return {
                "research_notes": response,
                "parser_source": self._infer_parser_sources_from_text(response)
            }
    
    def _infer_parser_sources_from_text(self, text: str) -> Optional[ParserSource]:
        """Infer parser sources from response text when JSON parsing fails"""
        try:
            text_lower = text.lower()
            
            # Common parser/tool indicators
            known_sources = [
                ("splunk", "Splunk parsing rules"),
                ("elasticsearch", "Elasticsearch ingest pipeline"),
                ("logstash", "Logstash configuration"),
                ("fluentd", "Fluentd parser plugin"),
                ("vector", "Vector VRL transforms"),
                ("grok", "Grok pattern library"),
                ("beats", "Elastic Beats processors"),
                ("qradar", "IBM QRadar DSM"),
                ("sentinel", "Microsoft Sentinel parser"),
                ("github", "GitHub project or repository")
            ]
            
            found_sources = []
            for keyword, description in known_sources:
                if keyword in text_lower:
                    found_sources.append(description)
            
            if found_sources:
                source_type = "internet" if any("github" in s.lower() or "project" in s.lower() for s in found_sources) else "documentation"
                return ParserSource(
                    type=source_type,
                    sources=found_sources,
                    confidence=0.6,  # Medium confidence from text inference
                    description=f"Inferred from text analysis: {', '.join(found_sources[:3])}"
                )
            
            return None
        except Exception:
            return None
    
    def _track_usage(self, usage, response_headers=None):
        """Track token usage from Anthropic API response"""
        self.usage.api_calls += 1
        self.usage.input_tokens += usage.input_tokens
        self.usage.output_tokens += usage.output_tokens
        self.usage.total_tokens = self.usage.input_tokens + self.usage.output_tokens
        
        # Calculate cost
        input_cost = self.usage.input_tokens * self.input_cost_per_token
        output_cost = self.usage.output_tokens * self.output_cost_per_token
        self.usage.estimated_cost_usd = input_cost + output_cost
        
        # Check rate limit headers for runtime token limit detection
        if response_headers:
            try:
                tokens_limit = response_headers.get('anthropic-ratelimit-tokens-limit')
                tokens_remaining = response_headers.get('anthropic-ratelimit-tokens-remaining')
                
                if tokens_limit and tokens_remaining:
                    limit = int(tokens_limit)
                    remaining = int(tokens_remaining)
                    usage_pct = ((limit - remaining) / limit) * 100
                    
                    if usage_pct > 80:
                        print(f"⚠️  Token usage warning: {usage_pct:.1f}% of rate limit used")
                        print(f"   Remaining: {remaining:,} / {limit:,} tokens")
                        
                    # Update model limits based on runtime detection if different
                    if limit != self.model_limits['context_tokens']:
                        print(f"🔄 Updated model token limit: {self.model_limits['context_tokens']:,} → {limit:,}")
                        self.model_limits['context_tokens'] = limit
                        
            except (ValueError, TypeError) as e:
                pass  # Ignore header parsing errors
    
    def _should_apply_aggressive_sampling(self) -> bool:
        """Determine if we should apply more aggressive token protection"""
        # Check if we're approaching token limits or have limited remaining quota
        return self.usage.total_tokens > (self.model_limits['context_tokens'] * 0.7)
    
    def get_usage(self) -> LLMUsage:
        """Get current usage statistics"""
        return self.usage
    
    def _build_narrative_prompt(
        self, 
        data_source: Optional[DataSource], 
        fields: List[ExtractedField], 
        parser_source: Optional[ParserSource] = None,
        performance_tier: Optional[int] = None
    ) -> str:
        """Build prompt for generating explanatory narrative"""
        
        # Build field summary
        field_summary = []
        for field in fields[:10]:  # Limit to first 10 fields to keep prompt manageable
            field_summary.append(f"- {field.name}: {field.type} ({field.description})")
        
        field_text = "\n".join(field_summary)
        if len(fields) > 10:
            field_text += f"\n... and {len(fields) - 10} additional fields"
        
        data_source_text = f"{data_source.name} (confidence: {data_source.confidence})" if data_source else "Unknown data source"
        parser_source_text = f"Based on {parser_source.type} sources" if parser_source else "Custom parser generation"
        performance_text = f"Estimated performance tier: {performance_tier}" if performance_tier else "Performance not assessed"
        
        return f"""Generate a clear, user-friendly explanation of this VRL parser generation result.

Data Source: {data_source_text}
Parser Approach: {parser_source_text}
{performance_text}

Key Fields Identified:
{field_text}

Please write a 2-3 paragraph narrative that explains:
1. What type of log data this parser handles and why DFE identified it as such
2. The key fields extracted and their importance for monitoring, analysis, and operational use
3. Performance considerations and optimization decisions made by DFE  
4. Any parser sources that were referenced or if this is a custom DFE solution

Write in a professional but accessible tone appropriate for the data domain. Use these as GUIDANCE (not rigid constraints) to adapt language to common data source types:
- Security logs: Focus on "security fields", "monitoring", "alerting", "forensic analysis"
- Cloud Infrastructure: Focus on "infrastructure fields", "performance monitoring", "resource optimization"
- Telecommunications: Focus on "network fields", "service monitoring", "performance analysis"
- Battlespace/Military: Focus on "operational fields", "situational awareness", "mission planning" 
- Travel/PNR: Focus on "passenger fields", "compliance", "operational tracking"
- IoT/Industrial: Focus on "sensor fields", "telemetry", "predictive maintenance"
- Financial: Focus on "transaction fields", "compliance monitoring", "fraud detection"
- Healthcare: Focus on "clinical fields", "patient care", "regulatory compliance"
- Energy/Utilities: Focus on "operational fields", "grid monitoring", "efficiency optimization"
- Automotive/Fleet: Focus on "vehicle fields", "fleet management", "predictive maintenance"
- Maritime: Focus on "vessel fields", "logistics", "regulatory compliance"
- Aviation: Focus on "flight fields", "safety monitoring", "performance analysis"
- E-commerce: Focus on "transaction fields", "business intelligence", "fraud prevention"
- Media/Content: Focus on "content fields", "analytics", "content optimization"
- Smart Cities: Focus on "infrastructure fields", "city operations", "citizen services"
- Generic/Unknown: Use "operational fields", "monitoring fields", "data elements"

However, ADAPT FLEXIBLY to the actual data source - these are guides, not constraints. If the data doesn't fit these categories, use appropriate domain-specific language based on the actual content and context.

IMPORTANT: Always attribute analysis and decisions to "DFE" (Data Fusion Engine) rather than "LLM" or "AI" to maintain professional branding."""
    
    def _generate_fallback_narrative(
        self, 
        data_source: Optional[DataSource], 
        fields: List[ExtractedField], 
        parser_source: Optional[ParserSource] = None,
        performance_tier: Optional[int] = None
    ) -> str:
        """Generate a basic narrative when LLM call fails"""
        
        data_source_name = data_source.name if data_source else "structured log data"
        field_count = len(fields)
        high_value_fields = len([f for f in fields if f.is_high_value])
        
        source_info = ""
        if parser_source and parser_source.type == "internet":
            source_info = " The parser leverages patterns from established open-source parsers and industry standards."
        elif parser_source and parser_source.type == "custom":
            source_info = " This is a custom-generated parser tailored specifically to your data patterns."
        
        performance_info = ""
        if performance_tier:
            if performance_tier <= 2:
                performance_info = " The parser is optimized for high-performance processing with efficient field extraction."
            elif performance_tier <= 4:
                performance_info = " The parser provides good performance while maintaining comprehensive field coverage."
            else:
                performance_info = " The parser prioritizes thoroughness over speed for complex data patterns."
        
        # Determine appropriate domain language based on data source
        domain_context = self._get_domain_context(data_source_name.lower() if data_source else "")
        
        return f"""This VRL parser was generated by DFE for {data_source_name}, extracting {field_count} key fields including {high_value_fields} high-value {domain_context['field_type']}.{source_info}{performance_info}

DFE optimized the parser to extract essential information for {domain_context['use_cases']}. Field types have been optimized based on expected query patterns - frequently searched fields use fast string types while large text content is configured for full-text search capabilities."""
    
    def _get_domain_context(self, data_source_name: str) -> Dict[str, str]:
        """Get domain-appropriate language based on data source"""
        
        # Security/Cybersecurity indicators
        security_keywords = ['firewall', 'asa', 'palo', 'fortinet', 'pfsense', 'ids', 'ips', 'siem', 'security', 'auth', 'vpn', 'waf', 'proxy', 'antivirus', 'edr', 'soc']
        if any(keyword in data_source_name for keyword in security_keywords):
            return {
                'field_type': 'security and operational fields',
                'use_cases': 'monitoring, alerting, and forensic analysis'
            }
        
        # Cloud Infrastructure indicators
        cloud_keywords = ['aws', 'azure', 'gcp', 'cloudtrail', 'cloudwatch', 'kubernetes', 'k8s', 'docker', 'container', 'ec2', 'lambda', 's3', 'rds']
        if any(keyword in data_source_name for keyword in cloud_keywords):
            return {
                'field_type': 'infrastructure and performance fields',
                'use_cases': 'performance monitoring and resource optimization'
            }
        
        # Telecommunications indicators
        telecom_keywords = ['telecom', 'network', 'router', 'switch', 'bgp', 'ospf', 'snmp', '5g', '4g', 'lte', 'radio', 'cellular', 'voip', 'sip']
        if any(keyword in data_source_name for keyword in telecom_keywords):
            return {
                'field_type': 'network and performance fields',
                'use_cases': 'service monitoring and performance analysis'
            }
        
        # IoT/Industrial indicators (expanded)
        iot_keywords = ['iot', 'sensor', 'device', 'telemetry', 'industrial', 'scada', 'plc', 'mqtt', 'modbus', 'bacnet', 'opcua', 'zigbee', 'lorawan']
        if any(keyword in data_source_name for keyword in iot_keywords):
            return {
                'field_type': 'sensor and telemetry fields',
                'use_cases': 'monitoring and predictive maintenance'
            }
        
        # Energy/Utilities indicators
        energy_keywords = ['power', 'grid', 'utility', 'electric', 'gas', 'water', 'energy', 'meter', 'substation', 'turbine', 'generator', 'solar', 'wind']
        if any(keyword in data_source_name for keyword in energy_keywords):
            return {
                'field_type': 'operational and monitoring fields',
                'use_cases': 'grid monitoring and efficiency optimization'
            }
        
        # Automotive/Fleet indicators
        automotive_keywords = ['vehicle', 'fleet', 'automotive', 'car', 'truck', 'gps', 'telematics', 'can', 'obd', 'ecu', 'connected car']
        if any(keyword in data_source_name for keyword in automotive_keywords):
            return {
                'field_type': 'vehicle and telematics fields',
                'use_cases': 'fleet management and predictive maintenance'
            }
        
        # Aviation indicators
        aviation_keywords = ['aviation', 'aircraft', 'flight', 'airline', 'radar', 'atc', 'ads-b', 'acars', 'airport', 'runway', 'navigation']
        if any(keyword in data_source_name for keyword in aviation_keywords):
            return {
                'field_type': 'flight and operations fields',
                'use_cases': 'safety monitoring and performance analysis'
            }
        
        # Maritime/Shipping indicators
        maritime_keywords = ['maritime', 'ship', 'vessel', 'cargo', 'port', 'ais', 'shipping', 'container', 'logistics', 'marine']
        if any(keyword in data_source_name for keyword in maritime_keywords):
            return {
                'field_type': 'vessel and cargo fields',
                'use_cases': 'logistics optimization and regulatory compliance'
            }
        
        # Healthcare indicators
        healthcare_keywords = ['healthcare', 'medical', 'hospital', 'patient', 'clinical', 'ehr', 'emr', 'hl7', 'fhir', 'pharmacy', 'lab']
        if any(keyword in data_source_name for keyword in healthcare_keywords):
            return {
                'field_type': 'clinical and operational fields',
                'use_cases': 'patient care and regulatory compliance'
            }
        
        # E-commerce indicators
        ecommerce_keywords = ['ecommerce', 'retail', 'shopping', 'cart', 'order', 'inventory', 'pos', 'payment gateway', 'marketplace', 'catalog']
        if any(keyword in data_source_name for keyword in ecommerce_keywords):
            return {
                'field_type': 'transaction and user fields',
                'use_cases': 'business intelligence and fraud prevention'
            }
        
        # Media/Content indicators
        media_keywords = ['media', 'content', 'streaming', 'cdn', 'video', 'audio', 'broadcast', 'social media', 'cms', 'analytics']
        if any(keyword in data_source_name for keyword in media_keywords):
            return {
                'field_type': 'content and user fields',
                'use_cases': 'analytics and content optimization'
            }
        
        # Smart Cities indicators
        smartcity_keywords = ['smart city', 'traffic', 'parking', 'street light', 'waste', 'environmental', 'public transport', 'municipal']
        if any(keyword in data_source_name for keyword in smartcity_keywords):
            return {
                'field_type': 'urban infrastructure fields',
                'use_cases': 'city operations and citizen services'
            }
        
        # Military/Defence indicators  
        military_keywords = ['battlespace', 'military', 'defence', 'defense', 'tactical', 'mission', 'unit', 'ops', 'radar', 'comms', 'c4i']
        if any(keyword in data_source_name for keyword in military_keywords):
            return {
                'field_type': 'operational and tactical fields',
                'use_cases': 'situational awareness and mission planning'
            }
        
        # Travel/PNR indicators
        travel_keywords = ['pnr', 'passenger', 'booking', 'reservation', 'travel', 'hotel', 'immigration', 'customs', 'border']
        if any(keyword in data_source_name for keyword in travel_keywords):
            return {
                'field_type': 'passenger and itinerary fields',
                'use_cases': 'compliance and operational tracking'
            }
        
        # Financial indicators (expanded)
        financial_keywords = ['financial', 'transaction', 'payment', 'banking', 'swift', 'iso20022', 'atm', 'credit card', 'trading', 'fintech', 'blockchain']
        if any(keyword in data_source_name for keyword in financial_keywords):
            return {
                'field_type': 'transaction and compliance fields',
                'use_cases': 'compliance monitoring and fraud detection'
            }
        
        # Default/Generic
        return {
            'field_type': 'operational and monitoring fields',
            'use_cases': 'analysis, monitoring, and operational insights'
        }