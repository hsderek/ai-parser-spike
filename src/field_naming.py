"""
Field naming convention utilities for consistent field naming across parsers
"""
import re
from enum import Enum
from typing import Optional


class FieldNamingConvention(Enum):
    """Supported field naming conventions"""
    SNAKE_CASE = "snake_case"      # lowercase_with_underscores (default)
    CAMEL_CASE = "camelCase"        # lowerCamelCase
    PASCAL_CASE = "PascalCase"      # UpperCamelCase
    KEBAB_CASE = "kebab-case"       # lowercase-with-hyphens
    ORIGINAL = "original"            # Keep original field names as-is
    

def normalize_field_name(
    field_name: str,
    convention: FieldNamingConvention = FieldNamingConvention.SNAKE_CASE,
    preserve_special_chars: bool = False
) -> str:
    """
    Normalize a field name according to the specified naming convention.
    
    Args:
        field_name: The original field name
        convention: The naming convention to apply
        preserve_special_chars: Whether to preserve special characters like @ or .
        
    Returns:
        The normalized field name
    """
    if convention == FieldNamingConvention.ORIGINAL:
        return field_name
    
    # Handle special prefixes
    special_prefix = ""
    if preserve_special_chars and field_name.startswith(("@", ".", "_")):
        special_prefix = field_name[0]
        field_name = field_name[1:]
    
    # Clean the field name - remove special characters except underscores
    if not preserve_special_chars:
        field_name = re.sub(r'[^a-zA-Z0-9_]', '_', field_name)
    
    # Split the field name into words
    # Handle various formats: camelCase, PascalCase, snake_case, kebab-case, dot.notation
    words = []
    
    # First split by underscores, hyphens, dots, and spaces
    parts = re.split(r'[_\-\.\s]+', field_name)
    
    for part in parts:
        if not part:
            continue
        # Split camelCase and PascalCase
        camel_parts = re.findall(r'[A-Z]?[a-z]+|[A-Z]+(?=[A-Z][a-z]|\b)', part)
        if camel_parts:
            words.extend(camel_parts)
        else:
            # If no camelCase pattern found, add the part as is
            words.append(part)
    
    # Convert all words to lowercase
    words = [w.lower() for w in words if w]
    
    if not words:
        return field_name  # Return original if we couldn't parse it
    
    # Apply the naming convention
    if convention == FieldNamingConvention.SNAKE_CASE:
        result = "_".join(words)
    elif convention == FieldNamingConvention.CAMEL_CASE:
        result = words[0] + "".join(w.capitalize() for w in words[1:])
    elif convention == FieldNamingConvention.PASCAL_CASE:
        result = "".join(w.capitalize() for w in words)
    elif convention == FieldNamingConvention.KEBAB_CASE:
        result = "-".join(words)
    else:
        result = "_".join(words)  # Default to snake_case
    
    return special_prefix + result


def apply_naming_convention_to_fields(
    fields: list,
    convention: FieldNamingConvention = FieldNamingConvention.SNAKE_CASE
) -> list:
    """
    Apply naming convention to a list of ExtractedField objects.
    
    Args:
        fields: List of ExtractedField objects
        convention: The naming convention to apply
        
    Returns:
        The list of fields with normalized names
    """
    for field in fields:
        original_name = field.name
        field.name = normalize_field_name(original_name, convention)
        
        # Store the original name if it changed
        if field.name != original_name:
            if not hasattr(field, 'metadata'):
                field.metadata = {}
            field.metadata['original_name'] = original_name
    
    return fields


# Common field name mappings for consistency
FIELD_NAME_ALIASES = {
    # Timestamp variations
    "@timestamp": "timestamp",
    "eventTime": "event_time",
    "dateTime": "datetime",
    "timeStamp": "timestamp",
    "logTime": "log_time",
    
    # Host variations
    "hostName": "hostname",
    "serverName": "server_name",
    "machineName": "machine_name",
    
    # IP address variations
    "srcIP": "src_ip",
    "dstIP": "dst_ip",
    "sourceIP": "source_ip",
    "destIP": "dest_ip",
    "clientIP": "client_ip",
    "remoteAddr": "remote_addr",
    
    # User variations
    "userId": "user_id",
    "userName": "username",
    "userID": "user_id",
    
    # Message variations
    "logMessage": "log_message",
    "eventMessage": "event_message",
    "errorMessage": "error_message",
    
    # Level/severity variations
    "logLevel": "log_level",
    "severityLevel": "severity_level",
    "errorLevel": "error_level",
}


def standardize_field_name(field_name: str) -> str:
    """
    Standardize common field names to consistent naming.
    
    Args:
        field_name: The field name to standardize
        
    Returns:
        The standardized field name
    """
    # First check if there's a direct alias
    if field_name in FIELD_NAME_ALIASES:
        return FIELD_NAME_ALIASES[field_name]
    
    # Otherwise apply snake_case normalization
    return normalize_field_name(field_name, FieldNamingConvention.SNAKE_CASE)