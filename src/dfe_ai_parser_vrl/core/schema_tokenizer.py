"""
Schema CSV Pre-Tokenizer

Optimizes common_header.csv and type_maps.csv for prompt inclusion.
Summarizes large schemas to fit within token budgets while preserving
essential information for field conflict prevention and type mapping.
"""

import csv
from typing import Dict, List, Any, Tuple
from pathlib import Path
from loguru import logger


class SchemaTokenizer:
    """Pre-tokenizes schema CSV files for efficient prompt inclusion"""
    
    def __init__(self, schemas_dir: str = None):
        if schemas_dir is None:
            schemas_dir = Path(__file__).parent.parent / "config" / "schemas"
        
        self.schemas_dir = Path(schemas_dir)
        self.common_header_path = self.schemas_dir / "common_header.csv"
        self.type_maps_path = self.schemas_dir / "type_maps.csv"
    
    def get_optimized_schema_prompt(self, max_tokens: int = 1000) -> str:
        """
        Get optimized schema information for prompts
        
        Args:
            max_tokens: Maximum tokens to use for schema info
            
        Returns:
            Optimized schema prompt text
        """
        # Load and analyze schemas
        reserved_fields = self._load_reserved_fields()
        meta_types = self._load_meta_types()
        
        # Calculate token usage (rough estimate: 4 chars = 1 token)
        current_size = len(str(reserved_fields)) + len(str(meta_types))
        estimated_tokens = current_size // 4
        
        if estimated_tokens <= max_tokens:
            # Schemas are small enough, include full information
            return self._build_full_schema_prompt(reserved_fields, meta_types)
        else:
            # Schemas are large, pre-tokenize with summaries
            logger.info(f"Schema size {estimated_tokens} tokens > {max_tokens}, applying pre-tokenization")
            return self._build_summarized_schema_prompt(reserved_fields, meta_types, max_tokens)
    
    def _load_reserved_fields(self) -> List[Dict[str, str]]:
        """Load reserved fields from common_header.csv"""
        reserved_fields = []
        
        try:
            if self.common_header_path.exists():
                with open(self.common_header_path, 'r', encoding='utf-8-sig') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        if row.get('column'):
                            reserved_fields.append({
                                'name': row.get('column', ''),
                                'type': row.get('type', ''),
                                'comment': row.get('comment', '')
                            })
        except Exception as e:
            logger.warning(f"Could not load common_header.csv: {e}")
        
        return reserved_fields
    
    def _load_meta_types(self) -> List[Dict[str, str]]:
        """Load meta schema types from type_maps.csv"""
        meta_types = []
        
        try:
            if self.type_maps_path.exists():
                with open(self.type_maps_path, 'r', encoding='utf-8-sig') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        if row.get('type'):
                            meta_types.append({
                                'type': row.get('type', ''),
                                'comment': row.get('comment', ''),
                                'clickhouse_type': row.get('clickhouse_type', ''),
                                'opensearch_type': row.get('opensearch_type', '')
                            })
        except Exception as e:
            logger.warning(f"Could not load type_maps.csv: {e}")
        
        return meta_types
    
    def _build_full_schema_prompt(self, reserved_fields: List[Dict], meta_types: List[Dict]) -> str:
        """Build full schema prompt when token budget allows"""
        
        prompt_parts = []
        
        # Reserved fields section
        prompt_parts.append("🚨 FORBIDDEN FIELD NAMES (Common Header Schema):")
        prompt_parts.append("❌ RESERVED by DFE Infrastructure - CANNOT be used in VRL:")
        prompt_parts.append("")
        
        for field in reserved_fields:
            comment = f" # {field['comment']}" if field['comment'] else ""
            prompt_parts.append(f"- {field['name']}{comment}")
        
        prompt_parts.append("")
        prompt_parts.append("✅ USE ALTERNATIVE NAMES: Prefix with source type (.ssh_*, .apache_*)")
        prompt_parts.append("")
        
        # Meta types section  
        prompt_parts.append("🎯 META SCHEMA TYPE MAPPING:")
        prompt_parts.append("Assign appropriate meta schema types to extracted fields:")
        prompt_parts.append("")
        
        for meta_type in meta_types:
            comment = f" # {meta_type['comment']}" if meta_type['comment'] else ""
            prompt_parts.append(f"• {meta_type['type']}{comment}")
        
        prompt_parts.append("")
        prompt_parts.append("RETURN FORMAT: For each field, specify both name and meta schema type")
        
        return "\n".join(prompt_parts)
    
    def _build_summarized_schema_prompt(self, reserved_fields: List[Dict], meta_types: List[Dict], max_tokens: int) -> str:
        """Build summarized schema prompt for large schemas"""
        
        prompt_parts = []
        
        # Summarized reserved fields (key categories only)
        key_reserved = ['timestamp', 'event_hash', 'logoriginal', 'org_id', 'tags.*']
        prompt_parts.append("🚨 FORBIDDEN FIELD NAMES (Summary):")
        prompt_parts.append("❌ Key reserved fields (and variations):")
        for field in key_reserved:
            prompt_parts.append(f"- {field}")
        prompt_parts.append(f"- Plus {len(reserved_fields) - len(key_reserved)} other reserved fields")
        prompt_parts.append("")
        
        # Summarized meta types (essential ones only)
        essential_types = [
            'string_fast', 'string_fast_lowcardinality', 'text', 
            'int32', 'ipv4', 'timestamp'
        ]
        prompt_parts.append("🎯 KEY META SCHEMA TYPES:")
        for meta_type in meta_types:
            if meta_type['type'] in essential_types:
                comment = f" # {meta_type['comment']}" if meta_type['comment'] else ""
                prompt_parts.append(f"• {meta_type['type']}{comment}")
        
        prompt_parts.append(f"• Plus {len(meta_types) - len(essential_types)} other specialized types")
        prompt_parts.append("")
        prompt_parts.append("NAMING RULE: Prefix fields with source type (.ssh_*, .apache_*)")
        
        return "\n".join(prompt_parts)


# Global instance
_schema_tokenizer = SchemaTokenizer()

def get_schema_prompt(max_tokens: int = 1000) -> str:
    """Get optimized schema prompt for field naming and type mapping"""
    return _schema_tokenizer.get_optimized_schema_prompt(max_tokens)