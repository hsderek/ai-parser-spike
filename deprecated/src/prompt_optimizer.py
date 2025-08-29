#!/usr/bin/env python3
"""
Prompt Optimizer for External Configs and Iterative Refinement

Compresses external prompts and CSV data for efficient LLM usage.
"""

import re
import hashlib
from typing import Dict, List, Any, Optional
from pathlib import Path
from loguru import logger

class PromptOptimizer:
    """Optimize and compress prompts for LLM efficiency"""
    
    def __init__(self):
        self.prompt_cache = {}
        self.compressed_configs = {}
        
    def compress_external_configs(self, external_configs: Dict[str, str], 
                                 iteration: int = 1) -> Dict[str, str]:
        """
        Compress external configs based on iteration
        
        Args:
            external_configs: Original external configs
            iteration: Current iteration (1 = full, 2+ = compressed)
            
        Returns:
            Compressed configs dict
        """
        if iteration == 1:
            # First iteration - use full configs but with optimization
            return self._optimize_initial_configs(external_configs)
        else:
            # Subsequent iterations - heavily compress
            return self._compress_for_iteration(external_configs)
    
    def _optimize_initial_configs(self, configs: Dict[str, str]) -> Dict[str, str]:
        """Optimize initial configs while maintaining completeness"""
        optimized = {}
        
        # Optimize vector_vrl_prompt
        if 'vector_vrl_prompt' in configs:
            vrl_prompt = configs['vector_vrl_prompt']
            
            # Remove excessive whitespace
            vrl_prompt = re.sub(r'\n{3,}', '\n\n', vrl_prompt)
            
            # Remove verbose comments that don't add value
            vrl_prompt = re.sub(r'#\s*-{20,}.*?\n', '', vrl_prompt)
            
            # Extract only critical sections for VRL
            critical_sections = []
            lines = vrl_prompt.split('\n')
            in_critical = False
            
            for line in lines:
                # Keep error handling, syntax rules, and examples
                if any(keyword in line.upper() for keyword in [
                    'ERROR', 'MUST', 'NEVER', 'ALWAYS', 'CRITICAL',
                    'FALLIBLE', 'INFALLIBLE', '```VRL', 'PATTERN',
                    'CORRECT:', 'WRONG:', 'EXAMPLE:'
                ]):
                    in_critical = True
                elif line.strip() == '' and in_critical:
                    in_critical = False
                    
                if in_critical or any(keyword in line.upper() for keyword in ['ERROR', 'MUST', 'PATTERN']):
                    critical_sections.append(line)
            
            # Only keep if we extracted meaningful content
            if critical_sections:
                optimized['vector_vrl_prompt'] = '\n'.join(critical_sections)
            else:
                # Fallback: Take first 3000 chars
                optimized['vector_vrl_prompt'] = vrl_prompt[:3000]
            
            original_len = len(configs['vector_vrl_prompt'])
            optimized_len = len(optimized['vector_vrl_prompt'])
            logger.info(f"Compressed vector_vrl_prompt: {original_len} → {optimized_len} chars ({(1-optimized_len/original_len)*100:.1f}% reduction)")
        
        # Optimize parser_prompts
        if 'parser_prompts' in configs:
            parser_prompt = configs['parser_prompts']
            
            # Extract only field parsing logic and type mapping rules
            key_sections = []
            for section in parser_prompt.split('\n\n'):
                if any(keyword in section.upper() for keyword in [
                    'FIELD', 'TYPE', 'MAPPING', 'PRIORITY', 'SCHEMA',
                    'STRING_FAST', 'STRING_LOW', 'CARDINALITY'
                ]):
                    key_sections.append(section)
            
            optimized['parser_prompts'] = '\n\n'.join(key_sections[:5])  # Keep top 5 sections
            
            original_len = len(configs['parser_prompts'])
            optimized_len = len(optimized['parser_prompts'])
            logger.info(f"Compressed parser_prompts: {original_len} → {optimized_len} chars ({(1-optimized_len/original_len)*100:.1f}% reduction)")
        
        # Optimize type_maps CSV
        if 'type_maps' in configs:
            type_maps = configs['type_maps']
            lines = type_maps.strip().split('\n')
            
            # Keep header and representative examples
            if len(lines) > 20:
                # Keep header
                optimized_lines = [lines[0]]
                
                # Group by type category and take 2 examples each
                type_groups = {}
                for line in lines[1:]:
                    parts = line.split(',')
                    if len(parts) >= 2:
                        field_type = parts[1].strip()
                        if field_type not in type_groups:
                            type_groups[field_type] = []
                        type_groups[field_type].append(line)
                
                # Take 2 examples per type
                for field_type, examples in type_groups.items():
                    optimized_lines.extend(examples[:2])
                
                optimized['type_maps'] = '\n'.join(optimized_lines)
            else:
                optimized['type_maps'] = type_maps
            
            original_len = len(configs['type_maps'])
            optimized_len = len(optimized['type_maps'])
            logger.info(f"Compressed type_maps: {original_len} → {optimized_len} chars ({(1-optimized_len/original_len)*100:.1f}% reduction)")
        
        return optimized
    
    def _compress_for_iteration(self, configs: Dict[str, str]) -> Dict[str, str]:
        """Heavy compression for iteration 2+"""
        compressed = {}
        
        # For iterations, only keep error-specific guidance
        if 'vector_vrl_prompt' in configs:
            # Extract only VRL error handling patterns
            vrl_prompt = configs['vector_vrl_prompt']
            error_patterns = []
            
            for line in vrl_prompt.split('\n'):
                if any(keyword in line for keyword in [
                    'E103', 'E110', 'E651', 'fallible', 'infallible',
                    'if length(', 'exists(', '??', 'abort'
                ]):
                    error_patterns.append(line)
            
            if error_patterns:
                compressed['vector_vrl_prompt'] = "# VRL ERROR FIXES:\n" + '\n'.join(error_patterns[:20])
        
        # Minimal parser prompts
        if 'parser_prompts' in configs:
            compressed['parser_prompts'] = """# FIELD TYPES:
- string_fast: for IPs, IDs
- string_low_cardinality: for severity, status
- text: for message content
- integer/float: for numeric values"""
        
        # No type_maps needed for iterations
        # compressed['type_maps'] = ""  # Skip entirely
        
        return compressed
    
    def compress_feedback_prompt(self, iteration: int, errors: List[str], 
                                previous_vrl: str) -> str:
        """
        Create compressed feedback prompt
        
        Args:
            iteration: Current iteration
            errors: List of error messages
            previous_vrl: Previous VRL code that failed
            
        Returns:
            Compressed prompt focused on errors
        """
        prompt_parts = []
        
        # Focus on specific errors
        prompt_parts.append("Fix these VRL errors:")
        
        # Group and prioritize errors
        error_groups = {
            'fallible': [],
            'type': [],
            'syntax': [],
            'other': []
        }
        
        for error in errors[:10]:  # Max 10 errors
            if 'E103' in error or 'fallible' in error:
                error_groups['fallible'].append(error)
            elif 'type' in error.lower():
                error_groups['type'].append(error)
            elif 'syntax' in error.lower():
                error_groups['syntax'].append(error)
            else:
                error_groups['other'].append(error)
        
        # Add grouped errors with specific fixes
        if error_groups['fallible']:
            prompt_parts.append("\n## Fallible Operation Errors:")
            for err in error_groups['fallible'][:3]:
                prompt_parts.append(f"- {err[:200]}")
            prompt_parts.append("FIX: Check array length before access, use ?? for fallible ops")
        
        if error_groups['type']:
            prompt_parts.append("\n## Type Errors:")
            for err in error_groups['type'][:3]:
                prompt_parts.append(f"- {err[:200]}")
            prompt_parts.append("FIX: Use to_string(), to_int(), to_float() for conversions")
        
        # Add minimal VRL context
        if 'parts[' in previous_vrl:
            prompt_parts.append("\n## Array Access Pattern:")
            prompt_parts.append("```vrl")
            prompt_parts.append("# ALWAYS check length first:")
            prompt_parts.append("parts = split(.message, delimiter)")
            prompt_parts.append("if length(parts) > 1 {")
            prompt_parts.append("    field = parts[1]")
            prompt_parts.append("}")
            prompt_parts.append("```")
        
        return '\n'.join(prompt_parts)
    
    def get_compression_stats(self, original: str, compressed: str) -> Dict[str, Any]:
        """Calculate compression statistics"""
        return {
            'original_length': len(original),
            'compressed_length': len(compressed),
            'reduction_percent': (1 - len(compressed)/len(original)) * 100 if original else 0,
            'original_lines': original.count('\n'),
            'compressed_lines': compressed.count('\n')
        }


def optimize_for_llm_session(external_configs: Dict[str, str], 
                            iteration: int = 1) -> Dict[str, str]:
    """
    Main entry point for optimizing external configs
    
    Args:
        external_configs: Raw external configs
        iteration: Current iteration number
        
    Returns:
        Optimized configs
    """
    optimizer = PromptOptimizer()
    return optimizer.compress_external_configs(external_configs, iteration)