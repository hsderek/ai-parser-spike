"""
VRL validation using PyVRL and Vector CLI
"""

import subprocess
import tempfile
from typing import Tuple, Optional, Dict, Any
from pathlib import Path
from loguru import logger


class VRLValidator:
    """VRL code validator"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        val_config = self.config.get("vrl_generation", {}).get("validation", {})
        
        self.use_pyvrl = val_config.get("pyvrl_enabled", True)
        self.use_vector = val_config.get("vector_cli_enabled", True)
        self.timeout = val_config.get("timeout", 30)
    
    def validate(self, vrl_code: str, sample_logs: str = None) -> Tuple[bool, Optional[str]]:
        """
        Validate VRL code
        
        Args:
            vrl_code: VRL code to validate
            sample_logs: Optional sample logs for testing
            
        Returns:
            Tuple of (is_valid, error_message)
        """
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
                pyvrl.compile(vrl_code)
                logger.debug("PyVRL validation passed")
                return True, None
            except pyvrl.CompileError as e:
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
        """Validate using Vector CLI"""
        try:
            # Create temporary files
            with tempfile.NamedTemporaryFile(mode='w', suffix='.vrl', delete=False) as vrl_file:
                vrl_file.write(vrl_code)
                vrl_path = vrl_file.name
            
            with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False) as log_file:
                log_file.write(sample_logs)
                log_path = log_file.name
            
            # Run Vector test
            cmd = [
                "vector", "test",
                "--runner", "vrl",
                "--vrl-script", vrl_path,
                "--input", log_path
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout
            )
            
            # Clean up temp files
            Path(vrl_path).unlink(missing_ok=True)
            Path(log_path).unlink(missing_ok=True)
            
            if result.returncode == 0:
                logger.debug("Vector CLI validation passed")
                return True, None
            else:
                error_msg = result.stderr or result.stdout
                logger.debug(f"Vector CLI validation failed: {error_msg}")
                return False, self._parse_vector_error(error_msg)
                
        except FileNotFoundError:
            logger.warning("Vector CLI not found, skipping Vector validation")
            return True, None
        except subprocess.TimeoutExpired:
            logger.warning("Vector validation timeout")
            return True, None
        except Exception as e:
            logger.error(f"Vector validation error: {e}")
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