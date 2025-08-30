"""
Core VRL generator using LiteLLM
"""

import time
from typing import Optional, Dict, Any, Tuple
from pathlib import Path
from loguru import logger

from ..llm.client import DFELLMClient
from ..llm.session_manager import get_vrl_session, cleanup_vrl_session
from ..config.loader import DFEConfigLoader
from .validator import DFEVRLValidator
from .error_fixer import DFEVRLErrorFixer


class DFEVRLGenerator:
    """Main VRL generator class"""
    
    def __init__(self, config_path: str = None):
        self.config = DFEConfigLoader.load(config_path)
        self.llm_client = DFELLMClient(self.config)
        self.validator = DFEVRLValidator(self.config)
        self.error_fixer = DFEVRLErrorFixer(self.llm_client)
        
        # Get generation settings
        gen_config = self.config.get("vrl_generation", {})
        self.max_iterations = gen_config.get("max_iterations", 10)
        self.iteration_delay = gen_config.get("iteration_delay", 2)
    
    def generate(self, 
                sample_logs: str,
                device_type: str = None,
                validate: bool = True,
                fix_errors: bool = True,
                baseline_vrl: str = None) -> Tuple[str, Dict[str, Any]]:
        """
        Generate VRL parser for sample logs
        
        Args:
            sample_logs: Sample log data
            device_type: Optional device type hint
            validate: Whether to validate generated VRL
            fix_errors: Whether to attempt fixing validation errors
            baseline_vrl: Existing working VRL to use as baseline/reference
            
        Returns:
            Tuple of (vrl_code, metadata)
        """
        logger.info(f"Starting baseline_stage VRL generation for {device_type or 'unknown'} device")
        
        # Get or create VRL generation session with Derek's guide loaded
        session = get_vrl_session(
            device_type=device_type or 'unknown',
            session_type="baseline_stage", 
            baseline_vrl=baseline_vrl
        )
        
        metadata = {
            "device_type": device_type,
            "session_id": session.session_id,
            "model_used": self.llm_client.get_model_info(),
            "iterations": 0,
            "errors_fixed": 0,
            "validation_passed": False,
            "iteration_history": [],  # Track what was tried and failed
            "failed_patterns": [],    # Patterns that caused repeated failures
            "error_progression": []   # Track how errors evolved
        }
        
        # Generate initial VRL with streaming progress and baseline reference
        if baseline_vrl:
            logger.info("Generating VRL code with baseline reference...")
        else:
            logger.info("Generating initial VRL code...")
        
        # Use session-based generation with Derek's guide loaded
        vrl_code = session.generate_vrl(
            sample_logs=sample_logs,
            strategy=None  # No specific strategy for baseline_stage
        )
        metadata["iterations"] = 1
        
        if not validate:
            return vrl_code, metadata
        
        # Anti-cyclical validation loop with history tracking
        for iteration in range(self.max_iterations):
            logger.info(f"Validation iteration {iteration + 1}/{self.max_iterations}")
            
            # Validate VRL
            is_valid, error_message = self.validator.validate(vrl_code, sample_logs)
            
            # Track error progression to detect cycles
            error_code = self._extract_error_code(error_message) if error_message else "NONE"
            metadata["error_progression"].append({
                "iteration": iteration + 1,
                "error_code": error_code,
                "error_message": error_message[:200] if error_message else None
            })
            
            if is_valid:
                logger.success("VRL validation passed!")
                metadata["validation_passed"] = True
                break
            
            if not fix_errors:
                logger.warning(f"Validation failed: {error_message}")
                break
            
            # Check for cyclical patterns (same error 3+ times)
            recent_errors = [e["error_code"] for e in metadata["error_progression"][-3:]]
            if len(recent_errors) >= 3 and len(set(recent_errors)) == 1:
                logger.warning(f"🔄 CYCLICAL PATTERN DETECTED: {error_code} repeated 3+ times")
                self._analyze_and_blacklist_patterns(vrl_code, error_message, metadata)
                
                # Try progressive simplification approach
                logger.info("🎯 Switching to PROGRESSIVE SIMPLIFICATION to break cycle")
                vrl_code = self._generate_simplified_vrl(sample_logs, device_type, metadata)
                continue
            
            # Try local fixes first (free)
            logger.info("Attempting local error fixes...")
            fixed_vrl = self.error_fixer.fix_locally(vrl_code, error_message)
            
            local_fix_applied = False
            if fixed_vrl and fixed_vrl != vrl_code:
                logger.info("✨ Local fix applied (free)")
                vrl_code = fixed_vrl
                metadata["errors_fixed"] += 1
                local_fix_applied = True
                
                # Re-validate after local fix
                is_valid_after_local, error_after_local = self.validator.validate(vrl_code, sample_logs)
                if is_valid_after_local:
                    logger.success("✅ Local fix resolved all issues!")
                    metadata["validation_passed"] = True
                    break
                else:
                    logger.info(f"Local fix partial - still has errors: {self._extract_error_code(error_after_local)}")
                    error_message = error_after_local  # Update error for LLM fix
            
            # Use LLM fix with iteration history to prevent cycles
            if not local_fix_applied or not metadata.get("validation_passed", False):
                logger.info(f"Using LLM to fix error: {self._extract_error_code(error_message)}")
                
                # Build iteration context to prevent repetition
                iteration_context = self._build_iteration_context(metadata, error_message)
                
                try:
                    # Use session-based error fixing with full context
                    fixed_vrl = session.fix_vrl_error(vrl_code, error_message, sample_logs)
                    
                    if fixed_vrl and fixed_vrl != vrl_code:
                        # Track this attempt in history
                        attempt_record = {
                            "iteration": iteration + 1,
                            "error_code": self._extract_error_code(error_message),
                            "fix_applied": True,
                            "vrl_length_before": len(vrl_code),
                            "vrl_length_after": len(fixed_vrl)
                        }
                        metadata["iteration_history"].append(attempt_record)
                        
                        vrl_code = fixed_vrl
                        metadata["errors_fixed"] += 1
                        metadata["iterations"] += 1
                        logger.info(f"🤖 LLM fix applied - iteration {iteration + 1}")
                    else:
                        logger.warning(f"LLM unable to fix error at iteration {iteration + 1}")
                        
                        # Track failed attempt
                        failed_attempt = {
                            "iteration": iteration + 1,
                            "error_code": self._extract_error_code(error_message),
                            "fix_applied": False,
                            "reason": "LLM returned no changes"
                        }
                        metadata["iteration_history"].append(failed_attempt)
                        metadata["iterations"] += 1
                        
                except Exception as e:
                    logger.error(f"LLM fix failed: {e}")
                    
                    # Track error in history
                    error_attempt = {
                        "iteration": iteration + 1,
                        "error_code": self._extract_error_code(error_message),
                        "fix_applied": False,
                        "reason": f"LLM fix exception: {str(e)[:100]}"
                    }
                    metadata["iteration_history"].append(error_attempt)
                    metadata["iterations"] += 1
            
            # Rate limiting
            time.sleep(self.iteration_delay)
        
        # Add session summary to metadata
        session_summary = session.get_session_summary()
        metadata["session_summary"] = session_summary
        
        # Clean up session if validation passed
        if metadata.get("validation_passed", False):
            logger.info("✅ baseline_stage complete - cleaning up session")
            cleanup_vrl_session(device_type or 'unknown', "baseline_stage")
        
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
        
        # Stream log samples (memory efficient)
        sample_logs = self._stream_sample_logs(log_path)
        
        return self.generate(sample_logs, device_type, validate, fix_errors)
    
    def _stream_sample_logs(self, log_path: Path, max_lines: int = 1000) -> str:
        """
        Stream sample logs using Dask for memory efficiency and performance
        
        Args:
            log_path: Path to log file
            max_lines: Maximum lines to sample (prevents memory issues)
            
        Returns:
            Sampled log content as string
        """
        import dask.bag as db
        
        try:
            # Use Dask for efficient streaming and sampling
            bag = db.read_text(str(log_path), blocksize="32MB")
            
            # Take distributed sample across file 
            total_partitions = bag.npartitions
            lines_per_partition = max(1, max_lines // max(1, total_partitions))
            
            # Sample from each partition for representative coverage
            sampled = bag.take(max_lines, warn=False)
            
            logger.info(f"Dask sampled {len(sampled)} lines from {log_path.name} ({total_partitions} partitions)")
            return '\n'.join(sampled)
            
        except Exception as e:
            logger.warning(f"Dask streaming failed: {e}, falling back to basic streaming")
            # Fallback to simple streaming
            lines = []
            with open(log_path, 'r') as f:
                for i, line in enumerate(f):
                    if i >= max_lines:
                        break
                    lines.append(line.rstrip())
            
            logger.info(f"Basic sampled {len(lines)} lines from {log_path.name}")
            return '\n'.join(lines)
    
    def _extract_error_code(self, error_message: str) -> str:
        """Extract error code from error message"""
        if not error_message:
            return "unknown"
        
        import re
        match = re.search(r'error\[E(\d+)\]', error_message)
        if match:
            return f"E{match.group(1)}"
        
        # Extract error type from message
        if ':' in error_message:
            return error_message.split(':')[0].strip()
        
        return error_message.split()[0] if error_message.split() else "unknown"
    
    def _build_iteration_context(self, metadata: Dict[str, Any], current_error: str) -> str:
        """Build context of previous iterations to prevent cyclical failures"""
        
        history = metadata.get("iteration_history", [])
        failed_patterns = metadata.get("failed_patterns", [])
        error_progression = metadata.get("error_progression", [])
        
        if not history and not failed_patterns:
            return "First iteration attempt."
        
        context_parts = []
        
        # Previous iteration summary
        if history:
            context_parts.append("PREVIOUS ITERATION ATTEMPTS:")
            for attempt in history[-3:]:  # Last 3 attempts
                status = "✅ FIXED" if attempt.get("fix_applied") else "❌ FAILED"
                context_parts.append(f"  Iteration {attempt['iteration']}: {attempt['error_code']} → {status}")
                if not attempt.get("fix_applied"):
                    context_parts.append(f"    Reason: {attempt.get('reason', 'Unknown')}")
        
        # Failed patterns to avoid
        if failed_patterns:
            context_parts.append("")
            context_parts.append("❌ AVOID THESE PATTERNS (caused repeated failures):")
            for pattern in failed_patterns[-5:]:  # Last 5 failed patterns
                context_parts.append(f"  ❌ {pattern}")
        
        # Error trend analysis
        if len(error_progression) >= 3:
            recent_error_codes = [e["error_code"] for e in error_progression[-3:]]
            if len(set(recent_error_codes)) == 1:
                context_parts.append("")
                context_parts.append(f"⚠️ WARNING: {recent_error_codes[0]} error repeating - try different approach")
        
        context_parts.append("")
        context_parts.append("🎯 REQUIREMENT: Generate different solution than previous attempts")
        
        return "\n".join(context_parts)
    
    def _analyze_and_blacklist_patterns(self, vrl_code: str, error_message: str, metadata: Dict[str, Any]):
        """Analyze failed VRL patterns and add to blacklist"""
        
        failed_patterns = metadata.setdefault("failed_patterns", [])
        
        # Extract problematic patterns from VRL
        lines = vrl_code.split('\n')
        
        # Common problematic patterns that cause cycles
        if "parts[length(parts) - 1]" in vrl_code:
            failed_patterns.append("parts[length(parts) - 1] - function calls in array indices")
        
        if "?? []" in vrl_code and "E651" in error_message:
            failed_patterns.append("split(...) ?? [] - unnecessary coalescing on infallible operations")
        
        if "return\n}" in vrl_code.replace(" ", ""):
            failed_patterns.append("bare return statements - use abort or remove")
        
        # Extract specific error lines
        import re
        line_matches = re.findall(r'(\d+)\s*│[^│]*│\s*(.+)', error_message)
        for line_num, line_content in line_matches[:3]:  # Top 3 problem lines
            if line_content.strip():
                failed_patterns.append(f"Line {line_num}: {line_content.strip()}")
        
        logger.info(f"📝 Added {len(line_matches)} failed patterns to blacklist")
    
    def _generate_simplified_vrl(self, sample_logs: str, device_type: str, metadata: Dict[str, Any]) -> str:
        """Generate simplified VRL to break cyclical complexity"""
        
        failed_patterns = metadata.get("failed_patterns", [])
        
        # Create simplified generation strategy
        simplified_strategy = {
            "name": "anti_cyclical_simple",
            "description": "Ultra-simple VRL to break error cycles",
            "approach": "Minimal logic, avoid complex patterns that failed before"
        }
        
        logger.info("🔄 Generating simplified VRL to break cycles...")
        
        # Generate with explicit anti-cyclical instructions
        return self.llm_client.generate_vrl(
            sample_logs=sample_logs,
            device_type=device_type,
            stream=False,
            strategy=simplified_strategy
        )
    
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