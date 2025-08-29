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


class DFELLMClient:
    """Unified LLM client using LiteLLM"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.model_selector = DFEModelSelector(config)
        self.current_model = None
        self.metadata = {}
        
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
            
            if stream:
                return self._stream_response(response)
            else:
                return response
                
        except Exception as e:
            logger.error(f"LLM completion failed: {e}")
            
            # Try with a different model
            if "rate_limit" in str(e).lower():
                logger.info("Rate limited, switching to different model")
                self._select_model(capability="efficient")
                time.sleep(5)
                return self.completion(messages, max_tokens, temperature, stream, **kwargs)
            
            raise
    
    def _stream_response(self, response: Generator) -> Generator:
        """Handle streaming response"""
        for chunk in response:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
    
    def generate_vrl(self, 
                    sample_logs: str,
                    device_type: str = None,
                    stream: bool = True) -> str:
        """
        Generate VRL parser for sample logs
        
        Args:
            sample_logs: Sample log data
            device_type: Optional device type hint
            stream: Whether to stream the response
            
        Returns:
            Generated VRL code
        """
        # Select appropriate model for VRL generation
        self._select_model(use_case="vrl_generation")
        
        # Build messages
        messages = self._build_vrl_messages(sample_logs, device_type)
        
        # Generate completion
        if stream:
            vrl_code = ""
            for chunk in self.completion(messages, max_tokens=8000, temperature=0.3, stream=True):
                vrl_code += chunk
                print(chunk, end="", flush=True)
            print()
            return vrl_code
        else:
            response = self.completion(messages, max_tokens=8000, temperature=0.3)
            return response.choices[0].message.content
    
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
        # Use efficient model for fixes
        self._select_model(capability="efficient")
        
        messages = [
            {
                "role": "system",
                "content": """You are a VRL (Vector Remap Language) expert focused on high-performance parsing.

CRITICAL: NO REGEX FUNCTIONS - Use only string operations for 50-100x better performance.
❌ FORBIDDEN: parse_regex(), match(), parse_regex_all(), match_array(), to_regex()
✅ USE ONLY: contains(), split(), upcase(), downcase(), starts_with(), ends_with(), parse_syslog!()

Fix the syntax error while maintaining performance requirements."""
            },
            {
                "role": "user",
                "content": f"""Fix this VRL syntax error:

Error: {error_message}

VRL Code:
```vrl
{vrl_code}
```

Return only the fixed VRL code without explanation. Remember: NO REGEX functions."""
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