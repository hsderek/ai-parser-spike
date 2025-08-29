"""
Working VRL Generator

Ensures we get at least one working VRL before attempting performance improvements.
Uses iterative fixing until Vector CLI produces actual output.
"""

import time
from typing import Tuple, List, Dict, Any
from loguru import logger

from .validator import DFEVRLValidator
from .error_fixer import DFEVRLErrorFixer
from ..llm.client import DFELLMClient


class WorkingVRLGenerator:
    """Generates VRL that is guaranteed to work with Vector CLI"""
    
    def __init__(self, llm_client: DFELLMClient, validator: DFEVRLValidator, error_fixer: DFEVRLErrorFixer):
        self.llm_client = llm_client
        self.validator = validator
        self.error_fixer = error_fixer
        self.max_attempts = 5  # Max attempts to get working VRL
    
    def generate_working_vrl(self, 
                           sample_logs: str,
                           device_type: str = None,
                           expected_fields: List[str] = None) -> Tuple[str, Dict[str, Any]]:
        """
        Generate VRL that is guaranteed to process events successfully
        
        Args:
            sample_logs: Sample log data
            device_type: Optional device type hint
            expected_fields: Fields that should be extracted
            
        Returns:
            Tuple of (working_vrl_code, generation_metadata)
        """
        logger.info(f"🎯 Generating WORKING VRL for {device_type or 'unknown'} device")
        logger.info("   Priority: Functional VRL before performance optimization")
        
        metadata = {
            "device_type": device_type,
            "attempts": 0,
            "working_achieved": False,
            "final_events_processed": 0,
            "validation_stages_passed": []
        }
        
        # Start with a simple, conservative VRL approach
        for attempt in range(1, self.max_attempts + 1):
            logger.info(f"\n📋 Working VRL Attempt {attempt}/{self.max_attempts}")
            
            # Generate VRL with increasing conservatism
            if attempt == 1:
                # First attempt: Standard generation
                vrl_code = self._generate_standard_vrl(sample_logs, device_type)
            elif attempt == 2:
                # Second attempt: Simplified approach
                vrl_code = self._generate_simplified_vrl(sample_logs, device_type)
            elif attempt == 3:
                # Third attempt: Ultra-conservative
                vrl_code = self._generate_conservative_vrl(sample_logs, device_type)
            else:
                # Final attempts: Minimal working VRL
                vrl_code = self._generate_minimal_vrl(device_type)
            
            metadata["attempts"] = attempt
            
            # Full validation pipeline
            logger.info("   Testing VRL...")
            
            # Stage 1: Syntax validation (PyVRL)
            syntax_valid, syntax_error = self.validator._validate_with_pyvrl(vrl_code)
            if not syntax_valid:
                logger.warning(f"   ❌ Syntax failed: {self._extract_error_code(syntax_error)}")
                
                # Try local fixes
                fixed_vrl = self.error_fixer.fix_locally(vrl_code, syntax_error)
                if fixed_vrl:
                    vrl_code = fixed_vrl
                    logger.info("   🔧 Applied local syntax fix")
                    
                    # Re-test syntax
                    syntax_valid, syntax_error = self.validator._validate_with_pyvrl(vrl_code)
                
                if not syntax_valid:
                    logger.warning(f"   ❌ Still syntax errors after fixes")
                    continue
            
            logger.info("   ✅ Syntax validation passed")
            metadata["validation_stages_passed"].append("syntax")
            
            # Stage 2: Vector CLI processing validation
            vector_valid, vector_error = self.validator._validate_with_vector(vrl_code, sample_logs)
            if not vector_valid:
                logger.warning(f"   ❌ Vector CLI failed: {vector_error[:100]}...")
                continue
            
            logger.info("   ✅ Vector CLI processing passed")
            metadata["validation_stages_passed"].append("processing")
            
            # Stage 3: Field extraction validation (if expected fields provided)
            if expected_fields:
                field_valid, field_error = self.validator._validate_field_extraction_vector(
                    vrl_code, sample_logs, expected_fields
                )
                if not field_valid:
                    logger.warning(f"   ❌ Field extraction failed: {field_error[:100]}...")
                    continue
                
                logger.info("   ✅ Field extraction passed")
                metadata["validation_stages_passed"].append("fields")
            
            # SUCCESS: We have working VRL!
            logger.success(f"🎉 WORKING VRL achieved in {attempt} attempts!")
            metadata["working_achieved"] = True
            
            return vrl_code, metadata
        
        # Failed to get working VRL
        logger.error(f"❌ Failed to generate working VRL after {self.max_attempts} attempts")
        return "", metadata
    
    def _generate_standard_vrl(self, sample_logs: str, device_type: str) -> str:
        """Generate standard VRL with full features"""
        return self.llm_client.generate_vrl(
            sample_logs=sample_logs,
            device_type=device_type,
            stream=False
        )
    
    def _generate_simplified_vrl(self, sample_logs: str, device_type: str) -> str:
        """Generate simplified VRL with basic features only"""
        simplified_strategy = {
            "name": "simplified_working",
            "description": "Simplified approach focused on basic field extraction only",
            "approach": "Use only guaranteed-working VRL functions, minimal logic"
        }
        
        return self.llm_client.generate_vrl(
            sample_logs=sample_logs,
            device_type=device_type,
            stream=False,
            strategy=simplified_strategy
        )
    
    def _generate_conservative_vrl(self, sample_logs: str, device_type: str) -> str:
        """Generate ultra-conservative VRL with minimal operations"""
        conservative_strategy = {
            "name": "conservative_working",
            "description": "Ultra-conservative approach using only basic string operations",
            "approach": "Only contains() and simple field assignments, no complex parsing"
        }
        
        return self.llm_client.generate_vrl(
            sample_logs=sample_logs,
            device_type=device_type,
            stream=False,
            strategy=conservative_strategy
        )
    
    def _generate_minimal_vrl(self, device_type: str) -> str:
        """Generate minimal VRL that will definitely work"""
        return f"""
# Minimal working VRL for {device_type or 'unknown'} device
.device_type = "{device_type or 'unknown'}"

# Basic message processing
message_str = to_string(.message) ?? ""

# Simple event classification
if contains(message_str, "error") || contains(message_str, "Error") {{
    .event_type = "error"
    .severity = "high"
}} else if contains(message_str, "warn") || contains(message_str, "Warn") {{
    .event_type = "warning"  
    .severity = "medium"
}} else {{
    .event_type = "info"
    .severity = "low"
}}

# Always set these fields to ensure output
.processed = true
.parser_version = "minimal_working"
"""
    
    def _extract_error_code(self, error_message: str) -> str:
        """Extract error code from error message"""
        if not error_message:
            return "unknown"
        
        import re
        match = re.search(r'error\[E(\d+)\]', error_message)
        if match:
            return f"E{match.group(1)}"
        
        # Extract first word as error type
        return error_message.split()[0] if error_message.split() else "unknown"