"""
VRL Generation Prompts - Template-Based with Jinja2

Loads prompts from external template files with proper hierarchy:
- templates/: Base templates  
- strategies/: Strategy-specific prompts
- models/: Model-specific guidance
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Any
from jinja2 import Environment, FileSystemLoader, Template
from loguru import logger
from ..core.schema_tokenizer import get_schema_prompt


class DFEPromptManager:
    """Manages VRL generation prompts using Jinja2 templates"""
    
    def __init__(self):
        # Templates are in ../prompts/ directory
        self.prompt_dir = Path(__file__).parent.parent / "prompts"
        self.template_env = Environment(
            loader=FileSystemLoader(str(self.prompt_dir)),
            autoescape=False,  # VRL code doesn't need escaping
            trim_blocks=True,
            lstrip_blocks=True
        )
        logger.info(f"📝 Prompt manager initialized with templates from {self.prompt_dir}")
    
    def build_vrl_generation_prompt(self, 
                                   sample_logs: str,
                                   device_type: str = None,
                                   strategy: Dict[str, str] = None,
                                   model: str = None) -> str:
        """Build VRL generation prompt from templates"""
        
        try:
            # Load base template
            base_template = self.template_env.get_template("templates/base_vrl_generation.j2")
            
            # Get model-specific guidance
            model_specific = None
            if model:
                model_family = self._get_model_family(model)
                if model_family:
                    try:
                        model_template = self.template_env.get_template(f"models/{model_family}.j2")
                        model_specific = model_template.render()
                    except Exception as e:
                        logger.debug(f"No model-specific template for {model_family}: {e}")
            
            # Get schema prompt with token budget
            schema_prompt = get_schema_prompt(max_tokens=800)  # Reserve tokens for schemas
            
            # Render the prompt
            prompt = base_template.render(
                device_type=device_type,
                strategy=strategy,
                model_specific=model_specific,
                schema_info=schema_prompt,
                sample_logs=sample_logs[:6000]  # Reduced to make room for schema info
            )
            
            return prompt
            
        except Exception as e:
            logger.error(f"Failed to build prompt from templates: {e}")
            return self._get_fallback_prompt(sample_logs, device_type, strategy)
    
    def build_strategy_generation_prompt(self,
                                       sample_logs: str,
                                       device_type: str = None,
                                       candidate_count: int = 3) -> str:
        """Build strategy generation prompt from template"""
        
        try:
            template = self.template_env.get_template("templates/candidate_strategy_generation.j2")
            return template.render(
                sample_logs=sample_logs,
                device_type=device_type,
                candidate_count=candidate_count
            )
        except Exception as e:
            logger.error(f"Failed to build strategy prompt: {e}")
            return f"Generate {candidate_count} different VRL parsing strategies for {device_type or 'log'} data."
    
    def _get_model_family(self, model: str) -> Optional[str]:
        """Extract model family for template selection"""
        model_lower = model.lower()
        if "claude" in model_lower:
            return "claude"
        elif "gpt" in model_lower:
            return "gpt"
        elif "gemini" in model_lower:
            return "gemini"
        return None
    
    def _get_fallback_prompt(self, sample_logs: str, device_type: str = None, strategy: Dict[str, str] = None) -> str:
        """Fallback prompt if templates fail"""
        return f"""Generate VRL parser for {device_type or 'log'} data.

CRITICAL FIELD EXTRACTION RULES:
🎯 EXTRACT ONLY REAL DATA FROM LOGS - NO ARBITRARY FIELDS

❌ FORBIDDEN "Value Add" Fields:
- .device_type = "ssh"           # NOT in log data  
- .parser_stage = "baseline"     # Metadata, not log data
- .severity = "high"             # Not in log unless explicitly present

✅ EXTRACT ONLY ACTUAL LOG DATA:
- Timestamp from syslog header
- Hostname from syslog header  
- Process name/PID from syslog header
- Event types derived from message content
- IP addresses present in message
- Usernames present in message

EXTRACTION PRINCIPLE: If it's not visible in the raw log line, don't create it!

🚨 MANDATORY VRL TYPE SAFETY (Start every VRL with this):
```
message_str = if exists(.message) {{ to_string(.message) ?? "" }} else {{ "" }}
msg_string = if exists(.msg) {{ to_string(.msg) ?? "" }} else {{ "" }}  
primary_message = if message_str != "" {{ message_str }} else {{ msg_string }}
```

Use safe VRL syntax:
- Use primary_message for ALL contains() operations (prevents E110)
- Use ?? only on fallible operations (prevents E651)
- NO REGEX: Use only contains(), split(), starts_with(), ends_with()

Sample data:
{sample_logs[:5000]}

Return only VRL code that extracts fields visible in the log data."""


# Global prompt manager instance
_prompt_manager = DFEPromptManager()

def build_vrl_generation_prompt(sample_logs: str, 
                               device_type: str = None,
                               strategy: str = None,
                               model: str = None) -> str:
    """Build VRL generation prompt using template system"""
    strategy_dict = {"name": strategy} if strategy else None
    return _prompt_manager.build_vrl_generation_prompt(
        sample_logs=sample_logs,
        device_type=device_type,
        strategy=strategy_dict,
        model=model
    )

def build_strategy_generation_prompt(sample_logs: str,
                                   device_type: str = None, 
                                   candidate_count: int = 3) -> str:
    """Build strategy generation prompt using template system"""
    return _prompt_manager.build_strategy_generation_prompt(
        sample_logs=sample_logs,
        device_type=device_type,
        candidate_count=candidate_count
    )