#!/usr/bin/env python3
"""
Vector VRL Testing Loop
Uses local vector installation to test VRL parser code iteratively
"""
import json
import subprocess
import tempfile
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import shutil
import time
from dataclasses import dataclass

from .logging_config import get_logger


@dataclass
class VRLTestResult:
    """Result from testing VRL code with Vector"""
    success: bool
    parsed_records: List[Dict[str, Any]]
    errors: List[str]
    warnings: List[str]
    execution_time: float
    vector_version: str


class VectorVRLTester:
    """
    Tests VRL parser code using actual Vector installation.
    Runs Vector in a tight loop to validate each iteration.
    """
    
    def __init__(self):
        self.logger = get_logger("VectorVRLTester")
        self.vector_command = self._find_vector_command()
        
        if not self.vector_command:
            self.logger.warning("Vector not found. Install with: curl --proto '=https' --tlsv1.2 -sSf https://sh.vector.dev | bash")
    
    def _find_vector_command(self) -> Optional[str]:
        """Find the vector command on the system"""
        # Check if vector is in PATH
        if shutil.which("vector"):
            return "vector"
        
        # Check common installation paths
        common_paths = [
            "/usr/local/bin/vector",
            "/usr/bin/vector",
            "$HOME/.vector/bin/vector",
            "/opt/vector/bin/vector"
        ]
        
        for path in common_paths:
            expanded_path = Path(path).expanduser()
            if expanded_path.exists() and expanded_path.is_file():
                return str(expanded_path)
        
        return None
    
    def test_vrl_code(
        self,
        vrl_code: str,
        sample_data: List[Dict[str, Any]],
        max_iterations: int = 3,
        fix_errors: bool = True
    ) -> VRLTestResult:
        """
        Test VRL code with actual Vector in a loop.
        
        Args:
            vrl_code: The VRL parser code to test
            sample_data: Sample log records (as dicts) to process
            max_iterations: Maximum iterations to try fixing errors
            fix_errors: Whether to attempt automatic error fixes
            
        Returns:
            VRLTestResult with parsed data and any errors
        """
        if not self.vector_command:
            return VRLTestResult(
                success=False,
                parsed_records=[],
                errors=["Vector is not installed"],
                warnings=[],
                execution_time=0.0,
                vector_version="unknown"
            )
        
        # Get Vector version
        vector_version = self._get_vector_version()
        
        iteration = 0
        current_vrl = vrl_code
        last_error = None
        
        while iteration < max_iterations:
            iteration += 1
            self.logger.info(f"Testing VRL parser - Iteration {iteration}/{max_iterations}")
            
            start_time = time.time()
            result = self._run_vector_test(current_vrl, sample_data)
            execution_time = time.time() - start_time
            
            if result["success"]:
                self.logger.info(f"✅ VRL parser validated successfully in {execution_time:.2f}s")
                return VRLTestResult(
                    success=True,
                    parsed_records=result["parsed_records"],
                    errors=[],
                    warnings=result.get("warnings", []),
                    execution_time=execution_time,
                    vector_version=vector_version
                )
            
            # Test failed - log the error
            error_msg = result.get("error", "Unknown error")
            self.logger.warning(f"❌ Iteration {iteration} failed: {error_msg}")
            
            if not fix_errors or iteration >= max_iterations:
                break
            
            # Try to fix common VRL errors
            self.logger.info(f"Attempting to fix VRL error...")
            current_vrl = self._fix_common_vrl_errors(current_vrl, error_msg)
            
            if current_vrl == vrl_code:  # No changes made, can't fix
                self.logger.error("Unable to automatically fix VRL error")
                break
            
            last_error = error_msg
        
        # All iterations failed
        return VRLTestResult(
            success=False,
            parsed_records=[],
            errors=[last_error] if last_error else ["VRL validation failed"],
            warnings=[],
            execution_time=execution_time if 'execution_time' in locals() else 0.0,
            vector_version=vector_version
        )
    
    def _run_vector_test(self, vrl_code: str, sample_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Run a single Vector test with the given VRL code and sample data.
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Write sample data as NDJSON
            input_file = temp_path / "input.ndjson"
            with open(input_file, 'w') as f:
                for record in sample_data:
                    f.write(json.dumps(record) + '\n')
            
            # Write VRL transform
            vrl_file = temp_path / "transform.vrl"
            with open(vrl_file, 'w') as f:
                f.write(vrl_code)
            
            # Create Vector config
            config_file = temp_path / "vector.yaml"
            config = self._create_vector_config(input_file, vrl_file, temp_path / "output.ndjson")
            with open(config_file, 'w') as f:
                f.write(config)
            
            # Run Vector
            try:
                # First validate the config
                validate_cmd = [self.vector_command, "validate", "--config-dir", str(config_file.parent)]
                validate_result = subprocess.run(
                    validate_cmd,
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                if validate_result.returncode != 0:
                    return {
                        "success": False,
                        "error": self._parse_vector_error(validate_result.stderr)
                    }
                
                # Run Vector to process the data
                run_cmd = [
                    self.vector_command,
                    "--config", str(config_file),
                    "--quiet"
                ]
                
                process = subprocess.Popen(
                    run_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                
                # Give Vector time to process
                time.sleep(2)
                
                # Terminate Vector
                process.terminate()
                try:
                    stdout, stderr = process.communicate(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    stdout, stderr = process.communicate()
                
                # Read output
                output_file = temp_path / "output.ndjson"
                if output_file.exists():
                    parsed_records = []
                    with open(output_file, 'r') as f:
                        for line in f:
                            if line.strip():
                                parsed_records.append(json.loads(line))
                    
                    return {
                        "success": True,
                        "parsed_records": parsed_records,
                        "warnings": self._extract_warnings(stderr)
                    }
                else:
                    return {
                        "success": False,
                        "error": "No output generated - " + stderr[:500]
                    }
                    
            except subprocess.TimeoutExpired:
                return {
                    "success": False,
                    "error": "Vector execution timed out"
                }
            except Exception as e:
                return {
                    "success": False,
                    "error": f"Vector execution failed: {str(e)}"
                }
    
    def _create_vector_config(self, input_file: Path, vrl_file: Path, output_file: Path) -> str:
        """Create a Vector configuration for testing VRL"""
        return f"""
sources:
  test_input:
    type: file
    include:
      - "{input_file}"
    start_at_beginning: true
    encoding:
      codec: json

transforms:
  vrl_parser:
    type: remap
    inputs:
      - test_input
    file: "{vrl_file}"
    drop_on_error: false

sinks:
  test_output:
    type: file
    inputs:
      - vrl_parser
    path: "{output_file}"
    encoding:
      codec: json
"""
    
    def _get_vector_version(self) -> str:
        """Get the Vector version"""
        try:
            result = subprocess.run(
                [self.vector_command, "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                # Parse version from output like "vector 0.34.0 (x86_64-unknown-linux-gnu 1234567 2023-12-01)"
                version_line = result.stdout.strip()
                parts = version_line.split()
                if len(parts) >= 2:
                    return parts[1]
            return "unknown"
        except:
            return "unknown"
    
    def _parse_vector_error(self, error_output: str) -> str:
        """Parse Vector error output to extract meaningful error message"""
        lines = error_output.strip().split('\n')
        
        # Look for error patterns
        for line in lines:
            if "error" in line.lower():
                return line.strip()
            if "failed" in line.lower():
                return line.strip()
        
        # Return first non-empty line if no specific error found
        for line in lines:
            if line.strip():
                return line.strip()
        
        return "Unknown Vector error"
    
    def _extract_warnings(self, stderr: str) -> List[str]:
        """Extract warning messages from Vector stderr"""
        warnings = []
        for line in stderr.split('\n'):
            if 'warn' in line.lower() or 'warning' in line.lower():
                warnings.append(line.strip())
        return warnings
    
    def _fix_common_vrl_errors(self, vrl_code: str, error_msg: str) -> str:
        """
        Attempt to fix common VRL errors automatically.
        
        Common issues:
        - Missing '!' for type assertions
        - Incorrect function names
        - Missing exists() checks
        - Wrong field access syntax
        """
        original_vrl = vrl_code
        
        # Fix missing '!' in type assertions
        if "fallible" in error_msg.lower() or "must be infallible" in error_msg.lower():
            # Add '!' to common functions that need it
            vrl_code = vrl_code.replace('string(', 'string!(')
            vrl_code = vrl_code.replace('to_int(', 'to_int!(')
            vrl_code = vrl_code.replace('to_float(', 'to_float!(')
            vrl_code = vrl_code.replace('parse_timestamp(', 'parse_timestamp!(')
        
        # Fix field access syntax
        if "undefined" in error_msg.lower() or "does not exist" in error_msg.lower():
            # Ensure fields are accessed with proper exists() checks
            import re
            # Find field accesses without exists() check
            pattern = r'\.([a-zA-Z_][a-zA-Z0-9_]*)\s*='
            matches = re.findall(pattern, vrl_code)
            for field in matches:
                if f'exists(.{field})' not in vrl_code:
                    # Wrap assignment in exists() check
                    old_pattern = f'.{field} ='
                    new_pattern = f'if exists(.{field}) {{\n  .{field} ='
                    vrl_code = vrl_code.replace(old_pattern, new_pattern)
                    # Add closing brace (simplified - may need manual adjustment)
                    vrl_code += '\n}'
        
        # Fix parse_regex syntax
        if "parse_regex" in error_msg.lower():
            vrl_code = vrl_code.replace('parse_regex(', 'parse_regex!(')
        
        # Fix timestamp parsing
        if "timestamp" in error_msg.lower():
            vrl_code = vrl_code.replace('to_timestamp(', 'parse_timestamp!(')
        
        if vrl_code != original_vrl:
            self.logger.info("Applied automatic VRL fixes")
        
        return vrl_code


def test_vrl_with_vector(vrl_code: str, sample_file: Path) -> bool:
    """
    Convenience function to test VRL code with sample data.
    
    Args:
        vrl_code: The VRL parser code to test
        sample_file: Path to NDJSON file with sample data
        
    Returns:
        True if VRL code is valid and processes successfully
    """
    tester = VectorVRLTester()
    
    # Load sample data
    samples = []
    with open(sample_file, 'r') as f:
        for line in f:
            if line.strip():
                samples.append(json.loads(line))
    
    # Test the VRL code
    result = tester.test_vrl_code(vrl_code, samples[:5])  # Test with first 5 samples
    
    if result.success:
        print(f"✅ VRL validation successful!")
        print(f"   Vector version: {result.vector_version}")
        print(f"   Execution time: {result.execution_time:.2f}s")
        print(f"   Records processed: {len(result.parsed_records)}")
        
        if result.parsed_records:
            # Show first parsed record
            first_record = result.parsed_records[0]
            original_fields = len(samples[0]) if samples else 0
            new_fields = len(first_record) - original_fields
            print(f"   New fields added: {new_fields}")
    else:
        print(f"❌ VRL validation failed!")
        for error in result.errors:
            print(f"   Error: {error}")
    
    return result.success