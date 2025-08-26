#!/usr/bin/env python3
"""
Complete Vector-based pipeline for generating and testing VRL parsers
Outputs actual Vector-processed data to samples-parsed/
"""
import json
import subprocess
import tempfile
import time
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import shutil

from .logging_config import get_logger
from .vector_vrl_tester import VectorVRLTester, VRLTestResult


class VectorPipeline:
    """
    End-to-end pipeline using actual Vector for VRL testing and data processing.
    No simulation - only real Vector output goes to samples-parsed.
    """
    
    def __init__(self):
        self.logger = get_logger("VectorPipeline")
        self.vrl_tester = VectorVRLTester()
        self.parsed_dir = Path("samples-parsed")
        self.parsed_dir.mkdir(exist_ok=True)
    
    def process_with_vrl(
        self,
        sample_file: Path,
        vrl_code: str,
        parser_result: Dict[str, Any]
    ) -> bool:
        """
        Process sample file with VRL code using actual Vector.
        Saves output to samples-parsed/ directory.
        
        Args:
            sample_file: Path to input NDJSON file
            vrl_code: Generated VRL parser code
            parser_result: Parser generation result metadata
            
        Returns:
            True if processing was successful
        """
        self.logger.info(f"Processing {sample_file.name} with Vector")
        
        # Load sample data
        samples = []
        with open(sample_file, 'r') as f:
            for line in f:
                if line.strip():
                    samples.append(json.loads(line))
        
        if not samples:
            self.logger.error("No samples found in input file")
            return False
        
        # Test and refine VRL code with Vector
        self.logger.info("Testing VRL code with Vector...")
        test_result = self.vrl_tester.test_vrl_code(
            vrl_code,
            samples,
            max_iterations=3,
            fix_errors=True
        )
        
        if not test_result.success:
            self.logger.error(f"VRL validation failed: {test_result.errors}")
            return False
        
        # Process all samples with validated VRL
        self.logger.info("Processing full dataset with validated VRL...")
        full_result = self._process_full_dataset(sample_file, vrl_code)
        
        if not full_result["success"]:
            self.logger.error(f"Full processing failed: {full_result.get('error')}")
            return False
        
        # Save outputs to samples-parsed
        base_name = sample_file.stem
        
        # 1. Save the Vector-processed output (actual parsed data)
        output_file = self.parsed_dir / f"{base_name}-parsed.ndjson"
        with open(output_file, 'w') as f:
            for record in full_result["parsed_records"]:
                f.write(json.dumps(record) + '\n')
        self.logger.info(f"✅ Saved parsed output to {output_file}")
        
        # 2. Save the final VRL code that worked
        vrl_file = self.parsed_dir / f"{base_name}.vrl"
        with open(vrl_file, 'w') as f:
            f.write(vrl_code)
        self.logger.info(f"✅ Saved VRL code to {vrl_file}")
        
        # 3. Save result metadata
        result_file = self.parsed_dir / f"{base_name}-result.json"
        
        # Calculate field statistics from actual Vector output
        original_fields = set(samples[0].keys()) if samples else set()
        processed_fields = set(full_result["parsed_records"][0].keys()) if full_result["parsed_records"] else set()
        new_fields = processed_fields - original_fields
        
        metadata = {
            "source_file": str(sample_file),
            "output_file": str(output_file),
            "vrl_file": str(vrl_file),
            "vector_version": test_result.vector_version,
            "processing_time": test_result.execution_time,
            "records_processed": len(full_result["parsed_records"]),
            "original_fields": sorted(list(original_fields)),
            "new_fields_added": sorted(list(new_fields)),
            "total_fields": len(processed_fields),
            "parser_info": {
                "type": "vector_vrl",
                "attribution": parser_result.get("narrative", "Generated VRL parser"),
                "method": "vector_processing",
                "iterations_to_validate": full_result.get("iterations", 1)
            },
            "vrl_validation": {
                "success": True,
                "warnings": test_result.warnings,
                "auto_fixes_applied": full_result.get("fixes_applied", [])
            }
        }
        
        with open(result_file, 'w') as f:
            json.dump(metadata, f, indent=2)
        self.logger.info(f"✅ Saved metadata to {result_file}")
        
        # Print summary
        self.logger.info(f"""
📊 Vector Processing Complete:
   Input: {len(samples)} records
   Output: {len(full_result['parsed_records'])} records
   Original fields: {len(original_fields)}
   New fields added: {len(new_fields)}
   Files created:
     - {output_file.name} (parsed data)
     - {vrl_file.name} (VRL code) 
     - {result_file.name} (metadata)
        """)
        
        return True
    
    def _process_full_dataset(
        self,
        sample_file: Path,
        vrl_code: str
    ) -> Dict[str, Any]:
        """
        Process the complete dataset with Vector.
        Returns the actual Vector-processed output.
        """
        if not self.vrl_tester.vector_command:
            return {
                "success": False,
                "error": "Vector is not installed"
            }
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Copy input file
            temp_input = temp_path / "input.ndjson"
            shutil.copy(sample_file, temp_input)
            
            # Write VRL transform
            vrl_file = temp_path / "transform.vrl"
            with open(vrl_file, 'w') as f:
                f.write(vrl_code)
            
            # Create Vector config
            output_file = temp_path / "output.ndjson"
            config_file = temp_path / "vector.yaml"
            config = f"""
# Vector configuration for VRL processing
sources:
  input:
    type: file
    include:
      - "{temp_input}"
    read_from: beginning
    encoding:
      codec: json

transforms:
  vrl_parser:
    type: remap
    inputs:
      - input
    file: "{vrl_file}"
    drop_on_error: false

sinks:
  output:
    type: file
    inputs:
      - vrl_parser
    path: "{output_file}"
    encoding:
      codec: json
"""
            
            with open(config_file, 'w') as f:
                f.write(config)
            
            # Run Vector
            try:
                # Run Vector and wait for completion
                cmd = [
                    self.vrl_tester.vector_command,
                    "--config", str(config_file),
                    "--quiet"
                ]
                
                self.logger.debug(f"Running Vector: {' '.join(cmd)}")
                
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                
                # Wait for processing
                time.sleep(3)
                
                # Stop Vector
                process.terminate()
                try:
                    stdout, stderr = process.communicate(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    stdout, stderr = process.communicate()
                
                # Read the actual Vector output
                if output_file.exists():
                    parsed_records = []
                    with open(output_file, 'r') as f:
                        for line in f:
                            if line.strip():
                                try:
                                    parsed_records.append(json.loads(line))
                                except json.JSONDecodeError as e:
                                    self.logger.warning(f"Failed to parse Vector output line: {e}")
                    
                    if parsed_records:
                        return {
                            "success": True,
                            "parsed_records": parsed_records,
                            "iterations": 1
                        }
                    else:
                        return {
                            "success": False,
                            "error": "Vector produced no output"
                        }
                else:
                    return {
                        "success": False,
                        "error": f"Vector did not create output file. stderr: {stderr[:500]}"
                    }
                    
            except Exception as e:
                return {
                    "success": False,
                    "error": f"Vector execution failed: {str(e)}"
                }


def generate_samples_parsed_with_vector(
    sample_file: Path,
    vrl_code: str,
    parser_metadata: Dict[str, Any]
) -> bool:
    """
    Convenience function to generate samples-parsed output using Vector.
    
    Args:
        sample_file: Input NDJSON file
        vrl_code: Generated VRL parser code
        parser_metadata: Metadata from parser generation
        
    Returns:
        True if successful
    """
    pipeline = VectorPipeline()
    return pipeline.process_with_vrl(sample_file, vrl_code, parser_metadata)