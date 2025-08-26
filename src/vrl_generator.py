from typing import List, Dict, Any
from datetime import datetime
from .config import Config
from .models import ExtractedField


class VRLGenerator:
    def __init__(self, config: Config):
        self.config = config
    
    def generate(self, fields: List[ExtractedField], parser_research: Dict[str, Any]) -> str:
        header = self._generate_header()
        transforms = []
        
        for field in fields:
            transform = self._generate_field_transform(field)
            if transform:
                transforms.append(transform)
        
        cleanup = self._generate_cleanup(fields)
        
        vrl_code = f"""{header}

{chr(10).join(transforms)}

{cleanup}
"""
        return vrl_code
    
    def _generate_header(self) -> str:
        return f"""#---
# Filename: generated_parser.vrl
# Purpose: AI-generated VRL parser for structured log data
# Description: Optimized VRL transforms for extracting high-value fields
#              Generated using CPU-efficient string operations per VECTOR-VRL guidelines
# Version: 1.0.0
# Changelog: |
#   ## [1.0.0] - {datetime.now().strftime('%Y-%m-%d')}
#   - Initial AI-generated parser
# Copyright: © 2025 HyperSec Pty Ltd
# Licence: "HyperSec EULA © 2025"
# Flow: >
#   input -> field_extraction -> type_conversion -> cleanup -> output
#---"""
    
    def _generate_field_transform(self, field: ExtractedField) -> str:
        if field.type == "string" or field.type == "string_fast":
            return self._generate_string_extraction(field)
        elif field.type in ["int64", "int32"]:
            return self._generate_int_extraction(field)
        elif field.type in ["float64", "float32"]:
            return self._generate_float_extraction(field)
        elif field.type == "datetime":
            return self._generate_datetime_extraction(field)
        elif field.type == "ipv4":
            return self._generate_ip_extraction(field)
        elif field.type == "boolean":
            return self._generate_boolean_extraction(field)
        else:
            return self._generate_generic_extraction(field)
    
    def _generate_string_extraction(self, field: ExtractedField) -> str:
        field_path = self._get_field_path(field.name)
        safe_name = self._safe_field_name(field.name)
        
        if "message" in field.name.lower() or "msg" in field.name.lower():
            return f"""# Extract message field - high value string field
if exists({field_path}) {{
    .{safe_name} = string!({field_path})
}}"""
        else:
            return f"""# Extract {field.name} as string
if exists({field_path}) {{
    .{safe_name} = string!({field_path})
}}"""
    
    def _generate_int_extraction(self, field: ExtractedField) -> str:
        field_path = self._get_field_path(field.name)
        safe_name = self._safe_field_name(field.name)
        
        return f"""# Extract {field.name} as integer with error handling
if exists({field_path}) {{
    .{safe_name}, .{safe_name}_err = to_int({field_path})
    if .{safe_name}_err != null {{
        del(.{safe_name}_err)
        .{safe_name} = 0
    }}
}}"""
    
    def _generate_float_extraction(self, field: ExtractedField) -> str:
        field_path = self._get_field_path(field.name)
        safe_name = self._safe_field_name(field.name)
        
        return f"""# Extract {field.name} as float with error handling
if exists({field_path}) {{
    .{safe_name}, .{safe_name}_err = to_float({field_path})
    if .{safe_name}_err != null {{
        del(.{safe_name}_err)
        .{safe_name} = 0.0
    }}
}}"""
    
    def _generate_datetime_extraction(self, field: ExtractedField) -> str:
        field_path = self._get_field_path(field.name)
        safe_name = self._safe_field_name(field.name)
        
        return f"""# Extract {field.name} as timestamp with fallback parsing
if exists({field_path}) {{
    .{safe_name}, .{safe_name}_err = parse_timestamp(string!({field_path}), format: "%Y-%m-%dT%H:%M:%S%.3fZ")
    if .{safe_name}_err != null {{
        .{safe_name}, .{safe_name}_err = parse_timestamp(string!({field_path}), format: "%Y-%m-%d %H:%M:%S")
        if .{safe_name}_err != null {{
            del(.{safe_name}_err)
            .{safe_name} = now()
        }}
    }}
}}"""
    
    def _generate_ip_extraction(self, field: ExtractedField) -> str:
        field_path = self._get_field_path(field.name)
        safe_name = self._safe_field_name(field.name)
        
        return f"""# Extract {field.name} as IP address using fast string validation
if exists({field_path}) {{
    .{safe_name}_raw = string!({field_path})
    # Fast IP validation using string operations (not regex)
    if contains(.{safe_name}_raw, ".") && length(.{safe_name}_raw) >= 7 && length(.{safe_name}_raw) <= 15 {{
        .{safe_name} = .{safe_name}_raw
    }}
    del(.{safe_name}_raw)
}}"""
    
    def _generate_boolean_extraction(self, field: ExtractedField) -> str:
        field_path = self._get_field_path(field.name)
        safe_name = self._safe_field_name(field.name)
        
        return f"""# Extract {field.name} as boolean with string handling
if exists({field_path}) {{
    if is_boolean({field_path}) {{
        .{safe_name} = bool!({field_path})
    }} else {{
        .{safe_name}_str = downcase(string!({field_path}))
        .{safe_name} = contains(.{safe_name}_str, "true") || contains(.{safe_name}_str, "yes") || .{safe_name}_str == "1"
        del(.{safe_name}_str)
    }}
}}"""
    
    def _generate_generic_extraction(self, field: ExtractedField) -> str:
        field_path = self._get_field_path(field.name)
        safe_name = self._safe_field_name(field.name)
        
        return f"""# Extract {field.name} with type preservation
if exists({field_path}) {{
    .{safe_name} = {field_path}
}}"""
    
    def _get_field_path(self, field_name: str) -> str:
        if "." in field_name and not field_name.startswith("."):
            parts = field_name.split(".")
            return "." + ".".join(parts)
        elif not field_name.startswith("."):
            return f".{field_name}"
        else:
            return field_name
    
    def _safe_field_name(self, field_name: str) -> str:
        safe_name = field_name.replace(".", "_").replace("[", "_").replace("]", "").replace("-", "_")
        if safe_name.startswith("_"):
            safe_name = safe_name[1:]
        return safe_name
    
    def _generate_cleanup(self, fields: List[ExtractedField]) -> str:
        return f"""# Cleanup temporary fields and optimize memory usage
# Remove any remaining error fields
del(..*_err)

# Performance optimization: fields processed = {len(fields)}
# Estimated CPU cost: {sum(1 for f in fields if f.cpu_cost.value == 'low')} low + {sum(1 for f in fields if f.cpu_cost.value == 'medium')} medium + {sum(1 for f in fields if f.cpu_cost.value == 'high')} high cost operations"""