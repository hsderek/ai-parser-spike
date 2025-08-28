"""
Core VRL generator using LiteLLM
"""

import time
from typing import Optional, Dict, Any, Tuple
from pathlib import Path
from loguru import logger

from ..llm.client import LLMClient
from ..config.loader import ConfigLoader
from .validator import VRLValidator
from .error_fixer import VRLErrorFixer


class VRLGenerator:
    """Main VRL generator class"""
    
    def __init__(self, config_path: str = None):
        self.config = ConfigLoader.load(config_path)
        self.llm_client = LLMClient(self.config)
        self.validator = VRLValidator(self.config)
        self.error_fixer = VRLErrorFixer(self.llm_client)
        
        # Get generation settings
        gen_config = self.config.get("vrl_generation", {})
        self.max_iterations = gen_config.get("max_iterations", 10)
        self.iteration_delay = gen_config.get("iteration_delay", 2)
    
    def generate(self, 
                sample_logs: str,
                device_type: str = None,
                validate: bool = True,
                fix_errors: bool = True) -> Tuple[str, Dict[str, Any]]:
        """
        Generate VRL parser for sample logs
        
        Args:
            sample_logs: Sample log data
            device_type: Optional device type hint
            validate: Whether to validate generated VRL
            fix_errors: Whether to attempt fixing validation errors
            
        Returns:
            Tuple of (vrl_code, metadata)
        """
        logger.info(f"Starting VRL generation for {device_type or 'unknown'} device")
        
        metadata = {
            "device_type": device_type,
            "model_used": self.llm_client.get_model_info(),
            "iterations": 0,
            "errors_fixed": 0,
            "validation_passed": False
        }
        
        # Generate initial VRL
        logger.info("Generating initial VRL code...")
        vrl_code = self.llm_client.generate_vrl(sample_logs, device_type)
        metadata["iterations"] = 1
        
        if not validate:
            return vrl_code, metadata
        
        # Validation loop
        for iteration in range(self.max_iterations):
            logger.info(f"Validation iteration {iteration + 1}/{self.max_iterations}")
            
            # Validate VRL
            is_valid, error_message = self.validator.validate(vrl_code, sample_logs)
            
            if is_valid:
                logger.success("VRL validation passed!")
                metadata["validation_passed"] = True
                break
            
            if not fix_errors:
                logger.warning(f"Validation failed: {error_message}")
                break
            
            # Attempt to fix error
            logger.info(f"Fixing error: {error_message}")
            fixed_vrl = self.error_fixer.fix(vrl_code, error_message, sample_logs)
            
            if fixed_vrl and fixed_vrl != vrl_code:
                vrl_code = fixed_vrl
                metadata["errors_fixed"] += 1
                metadata["iterations"] += 1
            else:
                logger.warning("Unable to fix error, stopping iterations")
                break
            
            # Rate limiting
            time.sleep(self.iteration_delay)
        
        return vrl_code, metadata
    
    def generate_from_file(self, 
                          log_file: str,
                          device_type: str = None,
                          validate: bool = True,
                          fix_errors: bool = True) -> Tuple[str, Dict[str, Any]]:
        """
        Generate VRL from log file
        
        Args:
            log_file: Path to log file
            device_type: Optional device type hint
            
        Returns:
            Tuple of (vrl_code, metadata)
        """
        log_path = Path(log_file)
        
        if not log_path.exists():
            raise FileNotFoundError(f"Log file not found: {log_file}")
        
        # Auto-detect device type from filename if not provided
        if not device_type:
            device_type = self._detect_device_type(log_path.name)
        
        # Read log samples
        with open(log_path, 'r') as f:
            sample_logs = f.read()
        
        return self.generate(sample_logs, device_type, validate, fix_errors)
    
    def _detect_device_type(self, filename: str) -> Optional[str]:
        """Auto-detect device type from filename"""
        filename_lower = filename.lower()
        
        # Common patterns
        patterns = {
            "ssh": ["ssh", "sshd", "openssh"],
            "apache": ["apache", "httpd", "access", "error"],
            "cisco": ["cisco", "asa", "ios", "nexus"],
            "windows": ["windows", "win", "evtx"],
            "linux": ["linux", "syslog", "messages"],
            "firewall": ["firewall", "pfsense", "fortinet"],
            "nginx": ["nginx"],
            "docker": ["docker", "container"],
            "kubernetes": ["k8s", "kubernetes", "kube"]
        }
        
        for device_type, keywords in patterns.items():
            if any(keyword in filename_lower for keyword in keywords):
                logger.info(f"Auto-detected device type: {device_type}")
                return device_type
        
        return None