"""
Unified LiteLLM client for DFE AI Parser VRL
Handles all LLM interactions with automatic model selection
"""

import os
import time
import regex as re  # Enhanced regex library for better performance
from typing import Dict, List, Optional, Any, Generator
import litellm
from loguru import logger
from .model_selector import DFEModelSelector
from .prompts import build_vrl_generation_prompt, build_strategy_generation_prompt
from .error_handler import handle_llm_error, validate_llm_response


class DFELLMClient:
    """Unified LLM client using LiteLLM"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        # Pass config dict to model selector, it will handle loading from file
        self.model_selector = DFEModelSelector()
        self.current_model = None
        self.metadata = {}
        self.last_completion_cost = None  # Track actual LiteLLM costs
        
        # Configure LiteLLM
        litellm.drop_params = True  # Drop unsupported params
        litellm.set_verbose = False  # Reduce verbosity
        
        # Initialize with best available model
        self._select_model()
    
    def _select_model(self, 
                     platform: str = None, 
                     capability: str = None,
                     use_case: str = None) -> str:
        """Select and set the model to use"""
        model, metadata = self.model_selector.select_model(
            platform=platform,
            capability=capability,
            use_case=use_case
        )
        
        if not model:
            # Fallback to any available model
            logger.warning("No preferred model found, trying fallback")
            model, metadata = self.model_selector.select_model(
                capability="efficient"
            )
        
        if not model:
            raise ValueError("No available models found")
        
        self.current_model = model
        self.metadata = metadata
        logger.info(f"Using model: {model} ({metadata.get('capability', 'unknown')} mode)")
        
        return model
    
    def completion(self, 
                  messages: List[Dict[str, str]], 
                  max_tokens: int = 4000,
                  temperature: float = 0.7,
                  stream: bool = False,
                  **kwargs) -> Any:
        """
        Generate completion using LiteLLM
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            stream: Whether to stream the response
            **kwargs: Additional parameters for LiteLLM
            
        Returns:
            Completion response or generator if streaming
        """
        if not self.current_model:
            self._select_model()
        
        try:
            response = litellm.completion(
                model=self.current_model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                stream=stream,
                **kwargs
            )
            
            # Track actual cost from LiteLLM
            if not stream and hasattr(response, 'usage'):
                try:
                    cost = litellm.completion_cost(completion_response=response)
                    if cost and cost > 0:
                        self.last_completion_cost = cost
                        logger.debug(f"LiteLLM completion cost: ${cost:.4f}")
                except Exception as e:
                    logger.debug(f"Could not get completion cost: {e}")
                    self.last_completion_cost = None
            else:
                self.last_completion_cost = None
            
            if stream:
                return self._stream_response(response)
            else:
                return response
                
        except Exception as e:
            # Smart error handling
            error_info = handle_llm_error(e, operation="LLM completion")
            
            # Handle retryable errors
            if error_info["should_retry"] and not error_info["is_llm_issue"]:
                if error_info["error_category"] == "api":
                    logger.info("🔄 API error - trying different model")
                    self._select_model(capability="efficient")
                    time.sleep(5)
                    return self.completion(messages, max_tokens, temperature, stream, **kwargs)
                elif error_info["error_category"] == "network":
                    logger.info("🔄 Network error - retrying after delay")
                    time.sleep(3)
                    return self.completion(messages, max_tokens, temperature, stream, **kwargs)
            
            # Re-raise if not retryable or is actual LLM issue
            if error_info["is_llm_issue"]:
                logger.error(f"🤖 LLM generation error (not retryable): {e}")
            elif error_info["is_infrastructure_issue"]:
                logger.error(f"⚙️ Infrastructure error (fix required): {e}")
            
            raise
    
    def _stream_response(self, response: Generator) -> Generator:
        """Handle streaming response"""
        for chunk in response:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
    
    def generate_candidate_strategies(self,
                                    sample_logs: str,
                                    device_type: str = None,
                                    candidate_count: int = 3) -> List[Dict[str, str]]:
        """
        Generate multiple VRL parsing strategies using LLM analysis
        
        Args:
            sample_logs: Sample log data to analyze
            device_type: Optional device type hint
            candidate_count: Number of different strategies to generate
            
        Returns:
            List of strategy dicts with name, description, approach
        """
        # Use template-based prompt
        strategy_prompt = build_strategy_generation_prompt(
            sample_logs=sample_logs,
            device_type=device_type,
            candidate_count=candidate_count
        )

        messages = [{"role": "user", "content": strategy_prompt}]
        
        try:
            response = self.completion(messages, max_tokens=2000, temperature=0.8)
            content = response.choices[0].message.content.strip()
            
            # Extract JSON from response
            if content.startswith('['):
                import json
                strategies = json.loads(content)
                logger.info(f"Generated {len(strategies)} candidate strategies")
                return strategies
            else:
                logger.warning("Strategy generation didn't return JSON, using defaults")
                return self._get_default_strategies(candidate_count)
                
        except Exception as e:
            logger.warning(f"Strategy generation failed: {e}, using defaults")
            return self._get_default_strategies(candidate_count)
    
    def _get_default_strategies(self, count: int) -> List[Dict[str, str]]:
        """Fallback default strategies"""
        defaults = [
            {"name": "string_ops_only", "description": "Ultra-fast string operations only", "approach": "contains + split only", "vpi_target": "high"},
            {"name": "structured_parsing", "description": "Built-in parsers with string ops", "approach": "parse_syslog + string ops", "vpi_target": "moderate"},
            {"name": "hybrid_adaptive", "description": "Adaptive parsing based on patterns", "approach": "conditional parsing strategy", "vpi_target": "balanced"}
        ]
        return defaults[:count]
    
    def generate_vrl(self, 
                    sample_logs: str,
                    device_type: str = None,
                    stream: bool = True,
                    strategy: Dict[str, str] = None) -> str:
        """
        Generate VRL parser for sample logs
        
        Args:
            sample_logs: Sample log data
            device_type: Optional device type hint
            stream: Whether to stream the response
            strategy: Optional strategy dict for candidate differentiation
            
        Returns:
            Generated VRL code
        """
        # Use current model if available, otherwise select for VRL generation
        if not self.current_model:
            self._select_model(use_case="vrl_generation")
        
        # Build enhanced messages with strategy and model-specific guidance
        strategy_name = strategy.get("name") if strategy else None
        prompt_content = build_vrl_generation_prompt(
            sample_logs=sample_logs,
            device_type=device_type, 
            strategy=strategy_name,
            model=self.current_model
        )
        
        # Add strategy-specific instruction
        user_instruction = f"Generate VRL parser for the {device_type or 'log'} data above."
        if strategy:
            user_instruction += f"\n\nUSE STRATEGY: {strategy['name']} - {strategy['description']}"
            user_instruction += f"\nAPPROACH: {strategy['approach']}"
        user_instruction += "\n\nReturn only clean VRL code."
        
        messages = [
            {"role": "system", "content": prompt_content},
            {"role": "user", "content": user_instruction}
        ]
        
        # Generate completion with full LiteLLM streaming progress monitoring
        if stream:
            logger.info("🔄 Streaming VRL generation with real-time progress...")
            vrl_code = ""
            token_count = 0
            start_time = time.time()
            last_progress_time = start_time
            
            for chunk in self.completion(messages, max_tokens=8000, temperature=0.3, stream=True):
                vrl_code += chunk
                chunk_tokens = len(chunk.split())
                token_count += chunk_tokens
                
                current_time = time.time()
                elapsed = current_time - start_time
                
                # Show detailed progress every 100 tokens or every 5 seconds
                if (token_count % 100 == 0) or (current_time - last_progress_time > 5.0):
                    # Calculate generation rate
                    tokens_per_sec = token_count / max(elapsed, 0.1)
                    
                    # Estimate completion (rough estimate based on typical VRL length)
                    estimated_total_tokens = 1500  # Typical VRL length
                    progress_pct = min((token_count / estimated_total_tokens) * 100, 95)
                    
                    if tokens_per_sec > 0:
                        remaining_tokens = max(0, estimated_total_tokens - token_count)
                        eta_seconds = remaining_tokens / tokens_per_sec
                        eta_str = f" (ETA: {eta_seconds:.0f}s)" if eta_seconds > 5 else ""
                    else:
                        eta_str = ""
                    
                    logger.info(f"   📊 Progress: {token_count} tokens ({progress_pct:.0f}%) | {tokens_per_sec:.1f} tok/sec{eta_str}")
                    last_progress_time = current_time
                
                print(chunk, end="", flush=True)
            
            final_elapsed = time.time() - start_time
            final_rate = token_count / max(final_elapsed, 0.1)
            
            logger.info(f"✅ VRL generation complete!")
            logger.info(f"   📈 Final stats: {token_count} tokens in {final_elapsed:.1f}s ({final_rate:.1f} tok/sec)")
            print()
            return self._extract_vrl_code(vrl_code)
        else:
            logger.info("🔄 Generating VRL (non-streaming)...")
            response = self.completion(messages, max_tokens=8000, temperature=0.3)
            
            # Validate response content
            response_content = response.choices[0].message.content
            is_valid, validation_error = validate_llm_response(response_content, "VRL generation")
            
            if not is_valid:
                logger.error(f"📭 Invalid LLM response: {validation_error}")
                raise ValueError(f"LLM returned invalid content: {validation_error}")
            
            # Log completion info if available
            if hasattr(response, 'usage') and response.usage:
                logger.info(f"✅ VRL generated ({response.usage.completion_tokens} completion tokens)")
            
            return self._extract_vrl_code(response_content)
    
    def fix_vrl_error(self, 
                     vrl_code: str, 
                     error_message: str,
                     original_logs: str = None) -> str:
        """
        Fix VRL syntax error
        
        Args:
            vrl_code: VRL code with error
            error_message: Error message from validator
            original_logs: Optional original log samples
            
        Returns:
            Fixed VRL code
        """
        # Use same model as generation to avoid model switching issues
        logger.info("Using same model for error fixes to maintain consistency")
        
        # Extract detailed error information for LLM debugging
        error_code = self._extract_error_code(error_message)
        error_lines = self._extract_error_lines(error_message, vrl_code)
        problem_analysis = self._analyze_error_context(error_message, vrl_code)
        
        logger.info(f"🔍 Providing detailed debug info to LLM: {error_code}")
        
        messages = [
            {
                "role": "system", 
                "content": f"""You are a VRL expert specializing in syntax error debugging and fixing.

🚨🚨🚨 ABSOLUTELY NO REGEX - WILL CAUSE IMMEDIATE FAILURE 🚨🚨🚨
❌ FORBIDDEN: parse_regex(), parse_regex!(), match(), match_array(), to_regex()
❌ FORBIDDEN: r"pattern", r'pattern', regex literals, \\w, \\d, \\S, [a-z]

✅ REQUIRED: Use ONLY contains(), split(), starts_with(), ends_with()
❌ NO bare return statements: Use abort "reason" instead  
✅ PROPER conditionals: Use if-else properly with braces

🚨 MANDATORY TYPE SAFETY FOR ALL STRING OPERATIONS (Fixes E110):
PATTERN: Before ANY string operation on a field, create type-safe variable:
```vrl
field_str = if exists(.field) {{ to_string(.field) ?? "" }} else {{ "" }}
```

THEN use field_str for ALL string operations:
✅ contains(field_str, "pattern")     # CORRECT
✅ split(field_str, " ")             # CORRECT  
✅ starts_with(field_str, "prefix")  # CORRECT

❌ NEVER use original field directly:
❌ contains(.field, "pattern")       # E110 error
❌ split(.field, " ")               # E110 error

ERROR DEBUGGING CONTEXT:
Error Type: {error_code}
Problem Lines: {error_lines} 
Analysis: {problem_analysis}

Fix the VRL to be syntactically correct while maintaining functionality.
CRITICAL: Maintain performance - NO REGEX EVER."""
            },
            {
                "role": "user",
                "content": f"""URGENT: Fix this VRL {error_code} error with detailed context provided.

SPECIFIC ERROR:
{error_message}

CURRENT VRL CODE:
```vrl
{vrl_code}
```

DEBUGGING HELP:
- Error occurs at: {error_lines}
- Context analysis: {problem_analysis}
- Must fix {error_code} error specifically

Return ONLY the corrected VRL code that eliminates this error."""
            }
        ]
        
        response = self.completion(messages, max_tokens=8000, temperature=0.1)
        return self._extract_vrl_code(response.choices[0].message.content)
    
    def _build_vrl_messages(self, sample_logs: str, device_type: str = None) -> List[Dict[str, str]]:
        """Build messages for VRL generation"""
        
        # Detect if syslog parsing is needed
        has_unparsed_syslog = self._detect_syslog_in_samples(sample_logs)
        
        # Build dynamic syslog guidance based on detection
        if has_unparsed_syslog:
            syslog_guidance = """
SYSLOG PARSING DETECTED:
✅ Sample data contains unparsed syslog format - use parse_syslog!(.message) to extract headers
✅ After parsing: work with the extracted .message field for content parsing"""
            syslog_rule = "1. Use parse_syslog!() for unparsed syslog format in .message"
        else:
            syslog_guidance = """
DFE PRE-PARSED CONTEXT:
🔧 Sample data appears pre-parsed - syslog headers already extracted by DFE
📝 .message contains ONLY the message content (not full syslog line)
❌ DO NOT use parse_syslog!() - headers already parsed"""
            syslog_rule = "1. DO NOT use parse_syslog!() - syslog headers already parsed by DFE"
            
        system_prompt = f"""You are an expert in Vector Remap Language (VRL) for high-performance log parsing in HyperSec DFE.

CRITICAL DATA STRUCTURE UNDERSTANDING:{syslog_guidance}
📝 .logoriginal = Contains full raw log (use as LAST RESORT only)
📝 Structured fields (.timestamp, .hostname, etc.) may already exist

CRITICAL PERFORMANCE REQUIREMENTS:
⚠️  NO REGEX FUNCTIONS - They are 50-100x slower than string operations
❌ FORBIDDEN: parse_regex(), match(), parse_regex_all(), match_array(), to_regex()
✅ USE ONLY: contains(), split(), upcase(), downcase(), starts_with(), ends_with()

Performance Tiers:
• String operations: 350-400 events/CPU% (REQUIRED)
• Built-in parsers: 200-300 events/CPU% (use parse_json!, parse_csv! for structured data)
• Regex operations: 3-10 events/CPU% (FORBIDDEN)

VRL Generation Rules:
{syslog_rule}
2. Use parse_json!() for JSON content in .message
3. Use parse_csv!() for CSV content in .message  
4. For custom parsing: ONLY contains(), split(), slice() operations on .message
5. Parse timestamps with parse_timestamp!() if needed
6. Handle errors with null coalescing (??)
7. Use infallible functions (!) where possible

Example Pattern (NO REGEX, DFE Context):
```vrl
{self._get_example_vrl(has_unparsed_syslog)}
```

Output only clean VRL code without explanations."""
        
        user_prompt = f"""Generate a VRL parser for these logs:

{f'Device Type: {device_type}' if device_type else ''}

Sample Logs:
```
{sample_logs[:10000]}  # Limit sample size
```

Generate complete VRL code that parses these logs."""
        
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
    
    def _extract_vrl_code(self, content: str) -> str:
        """Extract VRL code from response"""
        # Remove markdown code blocks if present
        if "```vrl" in content:
            start = content.find("```vrl") + 6
            end = content.find("```", start)
            if end != -1:
                return content[start:end].strip()
        elif "```" in content:
            start = content.find("```") + 3
            end = content.find("```", start)
            if end != -1:
                return content[start:end].strip()
        
        return content.strip()
    
    def _extract_error_code(self, error_message: str) -> str:
        """Extract VRL error code for debugging"""
        if not error_message:
            return "UNKNOWN"
        
        import re
        
        # Look for Vector error codes (E103, E651, etc.)
        match = re.search(r'error\[E(\d+)\]', error_message)
        if match:
            return f"E{match.group(1)}"
        
        # Look for error types
        if "syntax error" in error_message.lower():
            return "E203_SYNTAX"
        elif "fallible" in error_message.lower():
            return "E103_FALLIBLE"
        elif "coalescing" in error_message.lower():
            return "E651_COALESCING"
        elif "predicate" in error_message.lower():
            return "E110_PREDICATE"
        
        # Extract first word as error type
        words = error_message.split()
        return words[0] if words else "UNKNOWN"
    
    def _extract_error_lines(self, error_message: str, vrl_code: str) -> str:
        """Extract specific lines mentioned in error for debugging"""
        import re
        
        # Look for line numbers in error message
        line_matches = re.findall(r'(?:line\s+|┌─\s+:)(\d+)', error_message)
        
        if not line_matches:
            return "Error location not specified"
        
        vrl_lines = vrl_code.split('\n')
        problem_lines = []
        
        for line_num_str in line_matches:
            try:
                line_num = int(line_num_str)
                if 1 <= line_num <= len(vrl_lines):
                    line_content = vrl_lines[line_num - 1]
                    problem_lines.append(f"Line {line_num}: {line_content.strip()}")
            except ValueError:
                continue
        
        return "; ".join(problem_lines) if problem_lines else "Could not extract error lines"
    
    def _analyze_error_context(self, error_message: str, vrl_code: str) -> str:
        """Analyze error context to provide debugging insights"""
        
        analysis_points = []
        
        # Analyze common error patterns
        if "return" in error_message and "unexpected" in error_message:
            analysis_points.append("ISSUE: Bare return statement not allowed in VRL")
            analysis_points.append("FIX: Remove return statement or use abort instead")
        
        if "RBrace" in error_message and "unexpected" in error_message:
            analysis_points.append("ISSUE: Mismatched braces in conditional structure")
            analysis_points.append("FIX: Check if-else brace matching")
        
        if "fallible" in error_message.lower():
            analysis_points.append("ISSUE: Using fallible operation without error handling")
            analysis_points.append("FIX: Add ?? null or use infallible version with !")
        
        if "coalescing" in error_message.lower():
            analysis_points.append("ISSUE: Unnecessary ?? operator on infallible operation")
            analysis_points.append("FIX: Remove ?? operator from string literals and safe operations")
        
        if "any" in error_message and "string" in error_message:
            analysis_points.append("ISSUE: Variable has ambiguous type (any vs string)")
            analysis_points.append("FIX: Use to_string(.field) ?? \"\" to ensure string type")
        
        # Count problem areas in VRL
        lines = vrl_code.split('\n')
        
        # Check for common problem patterns
        return_count = sum(1 for line in lines if 'return' in line.strip())
        if return_count > 0:
            analysis_points.append(f"FOUND: {return_count} return statements that may need fixing")
        
        brace_open = sum(1 for line in lines if '{' in line)
        brace_close = sum(1 for line in lines if '}' in line) 
        if brace_open != brace_close:
            analysis_points.append(f"FOUND: Brace mismatch - {brace_open} open, {brace_close} close")
        
        fallible_ops = sum(1 for line in lines if any(op in line for op in ['split(', 'parse_']))
        null_coalescing = sum(1 for line in lines if '??' in line)
        if fallible_ops > null_coalescing:
            analysis_points.append(f"FOUND: {fallible_ops} fallible ops, {null_coalescing} with ?? - may need more error handling")
        
        return "; ".join(analysis_points) if analysis_points else "No specific context analysis available"
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get information about current model"""
        return {
            "model": self.current_model,
            "platform": self.metadata.get("platform"),
            "capability": self.metadata.get("capability"),
            "family": self.metadata.get("family")
        }
    
    def _detect_syslog_in_samples(self, sample_logs: str) -> bool:
        """
        Detect if sample logs contain unparsed syslog format in fields other than .logoriginal/.logjson
        
        Returns:
            True if syslog parsing should be recommended, False otherwise
        """
        # Common syslog patterns:
        # RFC3164: <priority>timestamp hostname tag: message
        # RFC5424: <priority>version timestamp hostname appname procid msgid message
        syslog_patterns = [
            # RFC3164 format: "Dec 10 06:55:46 hostname sshd[1234]: message"
            r'\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}\s+\w+\s+\w+\[?\d*\]?:',
            
            # RFC5424 format: "2023-12-10T06:55:46.123Z hostname appname 1234 - message"
            r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})\s+\w+\s+\w+\s+\d+\s+[-\w]*\s+',
            
            # Priority tag: "<123>Dec 10..."
            r'<\d{1,3}>\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}',
            
            # Timestamp + hostname + process[pid] pattern
            r'\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}\s+[\w.-]+\s+[\w.-]+\[\d+\]:',
        ]
        
        # Use enhanced regex library with threading for pattern matching
        from ..utils.streaming import concurrent_regex_search_threadpool
        
        # Sample first 20 lines for efficient detection
        lines = sample_logs.strip().split('\n')[:20]
        lines = [line for line in lines if line.strip()]  # Remove empty lines
        
        # Filter out JSON structure lines
        valid_lines = [
            line for line in lines 
            if not (line.strip().startswith('{') or '{"logoriginal"' in line or '{"logjson"' in line)
        ]
        
        lines_checked = len(valid_lines)
        if lines_checked == 0:
            return False
        
        # Use concurrent regex search with enhanced regex library
        match_results = concurrent_regex_search_threadpool(valid_lines, syslog_patterns)
        syslog_matches = sum(match_results)
        
        # If >30% of checked lines look like syslog, recommend syslog parsing
        syslog_ratio = syslog_matches / max(lines_checked, 1)
        should_use_syslog = syslog_ratio > 0.3
        
        logger.debug(f"Syslog detection: {syslog_matches}/{lines_checked} lines checked ({syslog_ratio:.1%}), recommend syslog parsing: {should_use_syslog}")
        
        return should_use_syslog
    
    def _get_example_vrl(self, has_unparsed_syslog: bool) -> str:
        """Get appropriate VRL example based on syslog detection"""
        if has_unparsed_syslog:
            return '''# GOOD: Parse syslog first, then work with message content
parsed = parse_syslog!(.message)
.timestamp = parsed.timestamp
.hostname = parsed.hostname
.message_content = parsed.message

# Then parse the message content with string operations
if contains(.message_content, "Invalid user") {
    parts = split(.message_content, " ")
    .event_type = "invalid_user"
    .username = parts[2]
}

# BAD: Regex (FORBIDDEN)
# matches = parse_regex(.message_content, r"Invalid user (\w+)")'''
        else:
            return '''# GOOD: String operations on pre-parsed message content
if contains(.message, "Invalid user") {
    parts = split(.message, " ")
    .event_type = "invalid_user"
    .username = parts[2]
    if contains(.message, "from ") {
        from_parts = split(.message, "from ")
        if length(from_parts) > 1 {
            .source_ip = split(from_parts[1], " ")[0]
        }
    }
}

# BAD: Using parse_syslog (headers already parsed)
# parsed = parse_syslog!(.message)  # WRONG - no syslog header in .message

# BAD: Regex (FORBIDDEN)  
# matches = parse_regex(.message, r"Invalid user (\w+)")'''