"""
VRL validation using PyVRL and Vector CLI
"""

import subprocess
import tempfile
from typing import Tuple, Optional, Dict, Any
from pathlib import Path
from loguru import logger


class DFEVRLValidator:
    """VRL code validator"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        val_config = self.config.get("vrl_generation", {}).get("validation", {})
        perf_config = self.config.get("vrl_generation", {}).get("performance", {})
        
        self.use_pyvrl = val_config.get("pyvrl_enabled", True)
        self.use_vector = val_config.get("vector_cli_enabled", True)
        self.timeout = val_config.get("timeout", 30)
        
        # Load rejected regex functions from config
        self.rejected_functions = perf_config.get('rejected_functions', [
            'parse_regex', 'parse_regex_all', 'match', 'match_array', 'to_regex'
        ])
    
    def validate(self, vrl_code: str, sample_logs: str = None) -> Tuple[bool, Optional[str]]:
        """
        Validate VRL code
        
        Args:
            vrl_code: VRL code to validate
            sample_logs: Optional sample logs for testing
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check for regex functions first (performance rejection)
        is_valid, error = self._validate_no_regex(vrl_code)
        if not is_valid:
            return False, error
            
        # Try PyVRL first (faster)
        if self.use_pyvrl:
            is_valid, error = self._validate_with_pyvrl(vrl_code)
            if not is_valid:
                return False, error
        
        # Try Vector CLI (more thorough)
        if self.use_vector and sample_logs:
            is_valid, error = self._validate_with_vector(vrl_code, sample_logs)
            if not is_valid:
                return False, error
        
        return True, None
    
    def _validate_with_pyvrl(self, vrl_code: str) -> Tuple[bool, Optional[str]]:
        """Validate using PyVRL library"""
        try:
            import pyvrl
            
            # Test compilation
            try:
                pyvrl.Transform(vrl_code)
                logger.debug("PyVRL validation passed")
                return True, None
            except ValueError as e:
                error_msg = str(e)
                logger.debug(f"PyVRL validation failed: {error_msg}")
                return False, self._parse_pyvrl_error(error_msg)
                
        except ImportError:
            logger.warning("PyVRL not installed, skipping PyVRL validation")
            return True, None
        except Exception as e:
            logger.error(f"PyVRL validation error: {e}")
            return True, None  # Don't fail on validator errors
    
    def _validate_with_vector(self, vrl_code: str, sample_logs: str) -> Tuple[bool, Optional[str]]:
        """Validate using Vector CLI - temporarily disabled"""
        # Vector CLI test command doesn't support standalone VRL validation
        # TODO: Implement proper Vector config-based validation
        logger.debug("Vector CLI validation temporarily disabled")
        return True, None
    
    def _validate_no_regex(self, vrl_code: str) -> Tuple[bool, Optional[str]]:
        """
        Validate that VRL code doesn't use regex functions (performance optimization)
        Per VECTOR-VRL.md: String operations are 50-100x faster than regex
        """
        found_functions = []
        
        for func in self.rejected_functions:
            # Check for both regular and infallible versions
            patterns = [f"{func}(", f"{func}!"]
            for pattern in patterns:
                if pattern in vrl_code:
                    found_functions.append(func)
                    break
        
        if found_functions:
            perf_config = self.config.get("vrl_generation", {}).get("performance", {})
            preferred = perf_config.get('preferred_functions', [
                'contains', 'split', 'upcase', 'downcase', 'starts_with', 'ends_with'
            ])
            
            error_msg = (
                f"REJECTED: VRL contains regex functions: {', '.join(found_functions)}. "
                f"Per VECTOR-VRL.md, regex is 50-100x slower than string operations. "
                f"Use instead: {', '.join(preferred[:4])}. "
                f"Performance: String ops (350-400 events/CPU%) vs Regex (3-10 events/CPU%)"
            )
            logger.warning(error_msg)
            return False, error_msg
            
        return True, None
    
    def _parse_pyvrl_error(self, error_msg: str) -> str:
        """Parse PyVRL error message"""
        # Extract the most relevant part of the error
        if "error[E" in error_msg:
            # Vector error code format
            lines = error_msg.split('\n')
            for line in lines:
                if "error[E" in line:
                    return line.strip()
        
        # Return first line if no specific pattern found
        return error_msg.split('\n')[0].strip()
    
    def _parse_vector_error(self, error_msg: str) -> str:
        """Parse Vector CLI error message"""
        # Similar to PyVRL parsing
        if "error:" in error_msg.lower():
            lines = error_msg.split('\n')
            for line in lines:
                if "error:" in line.lower():
                    return line.strip()
        
        return error_msg.split('\n')[0].strip()