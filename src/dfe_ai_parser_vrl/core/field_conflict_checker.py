"""
Field Conflict Checker

Prevents VRL from generating fields that conflict with common_header.csv
reserved field names. Ensures VRL output fields don't collide with DFE infrastructure.
"""

import csv
from typing import Set, List, Tuple, Dict, Any
from pathlib import Path
from loguru import logger


class FieldConflictChecker:
    """Checks VRL output fields against reserved common header fields"""
    
    def __init__(self, 
                 common_header_path: str = None, 
                 type_maps_path: str = None):
        
        # Default paths to schema directory
        if common_header_path is None:
            common_header_path = Path(__file__).parent.parent / "config" / "schemas" / "common_header.csv"
        if type_maps_path is None:
            type_maps_path = Path(__file__).parent.parent / "config" / "schemas" / "type_maps.csv"
        self.common_header_path = Path(common_header_path)
        self.type_maps_path = Path(type_maps_path)
        self.reserved_fields: Set[str] = set()
        self.field_info: Dict[str, Dict[str, str]] = {}
        self.meta_schema_types: Dict[str, Dict[str, str]] = {}
        
        self._load_reserved_fields()
        self._load_meta_schema_types()
    
    def _load_reserved_fields(self):
        """Load reserved field names from common_header.csv"""
        try:
            if not self.common_header_path.exists():
                logger.warning(f"common_header.csv not found at {self.common_header_path}")
                return
            
            with open(self.common_header_path, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    field_name = row.get('column', '').strip()
                    if field_name:
                        self.reserved_fields.add(field_name)
                        self.field_info[field_name] = {
                            'type': row.get('type', ''),
                            'comment': row.get('comment', ''),
                            'default': row.get('default', '')
                        }
            
            logger.info(f"✅ Loaded {len(self.reserved_fields)} reserved field names from common_header.csv")
            
        except Exception as e:
            logger.error(f"Failed to load common_header.csv: {e}")
    
    def _load_meta_schema_types(self):
        """Load meta schema types from type_maps.csv"""
        try:
            if not self.type_maps_path.exists():
                logger.warning(f"type_maps.csv not found at {self.type_maps_path}")
                return
            
            with open(self.type_maps_path, 'r', encoding='utf-8-sig') as f:  # Handle BOM
                reader = csv.DictReader(f)
                for row in reader:
                    type_name = row.get('type', '').strip()
                    if type_name:
                        self.meta_schema_types[type_name] = {
                            'clickhouse_type': row.get('clickhouse_type', ''),
                            'opensearch_type': row.get('opensearch_type', ''),
                            'comment': row.get('comment', '')
                        }
            
            logger.info(f"✅ Loaded {len(self.meta_schema_types)} meta schema types from type_maps.csv")
            
        except Exception as e:
            logger.error(f"Failed to load type_maps.csv: {e}")
    
    def get_type_mapping_guidance(self) -> str:
        """Generate prompt guidance for meta schema type selection"""
        
        # Key type categories with usage guidance
        type_guidance = """
🎯 META SCHEMA TYPE MAPPING (from type_maps.csv):

Choose the appropriate meta schema type based on field usage patterns:

STRING TYPES:
• string: General purpose strings
• string_fast: Heavily queried strings (IPs, usernames, event types) 
• string_lowcardinality: Limited unique values (status, severity levels)
• string_fast_lowcardinality: Heavily queried + limited values (log levels)
• text: Large text content (log messages, descriptions)

NUMERIC TYPES:
• int32: Standard integers (ports, counts)
• int64: Large integers (timestamps as epochs)
• float64: Floating point numbers

SPECIAL TYPES:
• ipv4/ipv6: IP addresses
• timestamp: Time series data (main timestamps)  
• datetime: Other date/time fields
• boolean: True/false values
• json: JSON objects/structures

SELECTION GUIDELINES:
1. **High Query Frequency** → Use *_fast types (IPs, usernames, event types)
2. **Low Cardinality** → Use *_lowcardinality types (status, severity, log levels)
3. **Large Text** → Use text type (log messages, descriptions)
4. **Network Data** → Use ipv4/ipv6 for IP addresses
5. **Time Data** → Use timestamp/datetime appropriately

Example Field Type Mapping:
- .ssh_username → string_fast (heavily queried)
- .ssh_event_type → string_fast_lowcardinality (queried + limited values)
- .ssh_source_ip → ipv4 (IP address)
- .ssh_source_port → int32 (port number)
- .ssh_message_content → text (large text field)
"""
        
        return type_guidance
    
    def check_vrl_field_conflicts(self, vrl_code: str) -> Tuple[bool, List[str]]:
        """
        Check VRL code for field name conflicts with common header
        
        Note: Reserved fields with "." indicate nested JSON structure, not literal dots
        e.g., "tags.collector.host" = {"tags": {"collector": {"host": "value"}}}
        
        Args:
            vrl_code: VRL code to check
            
        Returns:
            Tuple of (has_conflicts, conflict_list)
        """
        conflicts = []
        
        # Extract field assignments from VRL code
        import re
        
        # Pattern to match field assignments: .field_name = 
        field_pattern = r'\.(\w+(?:\.\w+)*)\s*='
        matches = re.findall(field_pattern, vrl_code)
        
        # Check each VRL field against reserved list
        for vrl_field in matches:
            # Check for exact matches first (top-level fields)
            if vrl_field in self.reserved_fields:
                field_info = self.field_info.get(vrl_field, {})
                conflict_desc = f"{vrl_field} (reserved: {field_info.get('comment', 'common header field')})"
                conflicts.append(conflict_desc)
                continue
            
            # Check for nested JSON conflicts
            # VRL field like "tags" conflicts with reserved "tags.collector.host"
            for reserved_field in self.reserved_fields:
                if '.' in reserved_field:
                    # Reserved field has nested structure
                    reserved_parts = reserved_field.split('.')
                    
                    # Check if VRL field conflicts with any part of nested structure
                    if vrl_field == reserved_parts[0]:  # Top-level conflict
                        field_info = self.field_info.get(reserved_field, {})
                        conflict_desc = f"{vrl_field} (conflicts with nested reserved field: {reserved_field})"
                        conflicts.append(conflict_desc)
                        break
                    
                    # Check if VRL has nested field that conflicts
                    if '.' in vrl_field:
                        vrl_parts = vrl_field.split('.')
                        # Check if nested paths overlap
                        if len(vrl_parts) >= len(reserved_parts):
                            if vrl_parts[:len(reserved_parts)] == reserved_parts:
                                field_info = self.field_info.get(reserved_field, {})
                                conflict_desc = f"{vrl_field} (exact conflict with reserved: {reserved_field})"
                                conflicts.append(conflict_desc)
                                break
        
        has_conflicts = len(conflicts) > 0
        
        if has_conflicts:
            logger.warning(f"🚨 FIELD CONFLICTS detected: {len(conflicts)} reserved fields used")
            for conflict in conflicts:
                logger.warning(f"   ❌ {conflict}")
        
        return has_conflicts, conflicts
    
    def get_conflict_prevention_prompt(self) -> str:
        """Generate prompt text to prevent field conflicts"""
        
        # Get key reserved fields for prompt
        key_reserved = [
            'timestamp', 'timestamp_*', 'event_hash', 'logoriginal', 'logjson', 
            'org_id', 'tags.*'
        ]
        
        prompt = f"""
🚨 CRITICAL: FORBIDDEN FIELD NAMES (Common Header Conflicts)

The following field names are RESERVED by DFE common header and CANNOT be used:

❌ FORBIDDEN VRL OUTPUT FIELDS:
{chr(10).join(f'- .{field}' for field in key_reserved)}
- And {len(self.reserved_fields) - len(key_reserved)} other reserved fields

✅ USE ALTERNATIVE FIELD NAMES:
- .log_timestamp (NOT .timestamp)
- .event_id (NOT .event_hash) 
- .source_log (NOT .logoriginal)
- .event_category (NOT .tags.event.category)
- .parsed_username (NOT .username if reserved)

FIELD NAMING RULE:
If unsure about a field name, prefix with source type: .ssh_username, .ssh_event_type, .ssh_source_ip

This prevents conflicts with DFE infrastructure fields.
"""
        
        return prompt
    
    def suggest_alternative_field_name(self, conflicting_field: str) -> str:
        """Suggest alternative field name for conflicts"""
        
        alternatives = {
            'timestamp': 'log_timestamp',
            'event_hash': 'event_id', 
            'logoriginal': 'source_log',
            'org_id': 'organization_id',
            'username': 'parsed_username',
            'hostname': 'source_hostname'
        }
        
        if conflicting_field in alternatives:
            return alternatives[conflicting_field]
        
        # Default: add source prefix
        return f"parsed_{conflicting_field}"
    
    def fix_field_conflicts_in_vrl(self, vrl_code: str) -> str:
        """Automatically fix field name conflicts in VRL code"""
        
        fixed_vrl = vrl_code
        
        # Find conflicts
        has_conflicts, conflicts = self.check_vrl_field_conflicts(vrl_code)
        
        if not has_conflicts:
            return fixed_vrl
        
        # Fix each conflict
        import re
        
        for conflict_desc in conflicts:
            field_name = conflict_desc.split(' ')[0]  # Extract field name
            alternative = self.suggest_alternative_field_name(field_name)
            
            # Replace .field_name = with .alternative =
            pattern = fr'\.{re.escape(field_name)}\s*='
            replacement = f'.{alternative} ='
            
            fixed_vrl = re.sub(pattern, replacement, fixed_vrl)
            logger.info(f"   🔧 Fixed conflict: .{field_name} → .{alternative}")
        
        return fixed_vrl


# Global instance
_field_checker = FieldConflictChecker()

def check_field_conflicts(vrl_code: str) -> Tuple[bool, List[str]]:
    """Check VRL for field name conflicts"""
    return _field_checker.check_vrl_field_conflicts(vrl_code)

def get_field_conflict_prevention_prompt() -> str:
    """Get prompt text to prevent field conflicts"""
    return _field_checker.get_conflict_prevention_prompt()

def fix_field_conflicts(vrl_code: str) -> str:
    """Fix field name conflicts in VRL"""
    return _field_checker.fix_field_conflicts_in_vrl(vrl_code)