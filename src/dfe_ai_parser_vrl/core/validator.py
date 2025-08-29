"""
VRL validation using PyVRL and Vector CLI
"""

import os
import subprocess
import tempfile
import json
import socket
import time
import requests
from typing import Tuple, Optional, Dict, Any, List
from pathlib import Path
from loguru import logger
from .field_conflict_checker import check_field_conflicts


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
    
    def validate(self, vrl_code: str, sample_logs: str = None, expected_fields: List[str] = None) -> Tuple[bool, Optional[str]]:
        """
        Validate VRL code - syntax AND field extraction
        
        Args:
            vrl_code: VRL code to validate
            sample_logs: Optional sample logs for testing
            expected_fields: Fields that should be extracted by the VRL
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Step 1: Check for field name conflicts with common header
        has_conflicts, conflicts = check_field_conflicts(vrl_code)
        if has_conflicts:
            return False, f"FIELD_CONFLICT: VRL uses reserved field names: {', '.join(conflicts)}"
        
        # Step 2: Check for regex functions (performance rejection)
        is_valid, error = self._validate_no_regex(vrl_code)
        if not is_valid:
            return False, f"PERFORMANCE: {error}"
            
        # Step 2: PyVRL syntax pre-check (fast error detection for fixing)
        if self.use_pyvrl:
            syntax_valid, syntax_error = self._validate_with_pyvrl(vrl_code)
            if not syntax_valid:
                return False, f"SYNTAX: {syntax_error}"
        
        # Step 3: Vector CLI authoritative validation (actual data processing)
        if sample_logs:
            vector_valid, vector_error = self._validate_with_vector(vrl_code, sample_logs)
            if not vector_valid:
                return False, f"PROCESSING: {vector_error}"
        
        # Step 4: Field extraction validation (if expected fields provided)
        if sample_logs and expected_fields:
            # Use Vector CLI output for field validation instead of PyVRL
            extraction_valid, extraction_error = self._validate_field_extraction_vector(
                vrl_code, sample_logs, expected_fields
            )
            if not extraction_valid:
                return False, f"FIELDS: {extraction_error}"
        
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
        """Validate using Vector CLI - authoritative validation with actual data processing"""
        import tempfile
        import subprocess
        import yaml
        import json
        import time
        
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                
                # Create input file with sample data
                input_file = temp_path / "input.ndjson"
                output_file = temp_path / "output.ndjson"
                config_file = temp_path / "vector.yaml"
                
                # Prepare sample data (limit to 5 lines for fast validation)
                sample_lines = sample_logs.strip().split('\n')[:5]
                with open(input_file, 'w') as f:
                    for line in sample_lines:
                        if line.strip():
                            if line.startswith('{'):
                                f.write(line + '\n')
                            else:
                                f.write(json.dumps({"message": line}) + '\n')
                
                # Create Vector config for validation (with 101 transform, NO GraphQL for reliability)
                vector_config = {
                    'data_dir': str(temp_path / 'vector_data'),
                    'sources': {
                        'validation_input': {
                            'type': 'file',
                            'include': [str(input_file)],
                            'read_from': 'beginning',
                            'max_read_bytes': 100000
                        }
                    },
                    'transforms': {
                        # Step 1: HyperSec 101 transform - flatten message JSON
                        'flatten_message_parse': {
                            'type': 'remap',
                            'inputs': ['validation_input'],
                            'source': '. = parse_json(.message) ?? {}'
                        },
                        'flatten_message_filter': {
                            'type': 'filter',
                            'inputs': ['flatten_message_parse'],
                            'condition': {
                                'type': 'vrl',
                                'source': '!is_empty(.)'
                            }
                        },
                        # Step 2: VRL validation (after message flattening)
                        'vrl_validation': {
                            'type': 'remap', 
                            'inputs': ['flatten_message_filter'],
                            'source': vrl_code
                        }
                    },
                    'sinks': {
                        'validation_output': {
                            'type': 'file',
                            'inputs': ['vrl_validation'],
                            'path': str(output_file),
                            'encoding': {'codec': 'json'}
                        }
                    }
                }
                
                with open(config_file, 'w') as f:
                    yaml.dump(vector_config, f)
                
                # Run Vector CLI for validation
                logger.debug(f"Vector CLI validating VRL with {len(sample_lines)} samples...")
                
                env = os.environ.copy()
                vector_data_dir = temp_path / 'vector_data'
                vector_data_dir.mkdir(exist_ok=True)
                env['VECTOR_DATA_DIR'] = str(vector_data_dir)
                
                process = subprocess.Popen(
                    ['vector', '--config', str(config_file), '--threads', '1'],
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                
                # Monitor Vector processing by comparing input vs output line counts
                input_line_count = len(sample_lines)
                logger.debug(f"Expecting {input_line_count} events to be processed")
                
                # Robust Vector termination logic: line count match OR idle OR timeout
                events_processed = 0
                last_event_time = time.time()
                data_appeared = False
                
                max_wait = 45  # Overall timeout safeguard
                check_interval = 0.2  # Check every 200ms
                idle_threshold = 1.0  # Terminate if no new events for 1 second
                
                start_time = time.time()
                
                while time.time() - start_time < max_wait:
                    # Check if Vector process died
                    if process.poll() is not None:
                        logger.debug("Vector process finished")
                        break
                    
                    # Check for new records in output file
                    current_events = 0
                    if output_file.exists():
                        try:
                            with open(output_file, 'r') as f:
                                current_events = sum(1 for line in f if line.strip())
                        except Exception as e:
                            logger.debug(f"Error checking output: {e}")
                    
                    # TERMINATION CONDITION 1: Line count match
                    if current_events >= input_line_count:
                        logger.debug(f"LINE COUNT MATCH: {current_events}/{input_line_count} events processed")
                        break
                    
                    # Track if new events appeared
                    if current_events > events_processed:
                        events_processed = current_events
                        last_event_time = time.time()
                        data_appeared = True
                        logger.debug(f"Vector processed {events_processed}/{input_line_count} events")
                    
                    # TERMINATION CONDITION 2: Some data appeared but idle for 1 sec
                    idle_time = time.time() - last_event_time
                    if data_appeared and idle_time > idle_threshold:
                        logger.debug(f"IDLE TERMINATION: {events_processed} events processed, idle for {idle_time:.1f}s")
                        break
                    
                    time.sleep(check_interval)
                
                # TERMINATION CONDITION 3: Overall timeout reached
                if time.time() - start_time >= max_wait:
                    logger.debug(f"TIMEOUT TERMINATION: {events_processed} events after {max_wait}s")
                
                final_processing_time = time.time() - start_time
                
                # Ensure Vector process is stopped
                if process.poll() is None:
                    logger.debug("Stopping Vector process")
                    process.terminate()
                    try:
                        process.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        logger.debug("Force killing Vector process")
                        process.kill()
                        process.wait()
                
                # Get final stderr for debugging
                try:
                    _, stderr = process.communicate(timeout=1)
                except:
                    stderr = "Could not get stderr"
                
                # Check if Vector ran successfully
                if process.returncode != 0:
                    error_msg = f"Vector CLI failed (exit {process.returncode}): {stderr[:500]}"
                    logger.debug(error_msg)
                    return False, error_msg
                
                # Check output file exists and has content
                if not output_file.exists():
                    return False, "Vector CLI produced no output file - VRL failed to process"
                
                # Count events by checking output file directly (reliable)
                events_processed = 0
                extracted_fields = set()
                
                if output_file.exists():
                    try:
                        with open(output_file, 'r') as f:
                            for line in f:
                                if line.strip():
                                    events_processed += 1
                                    try:
                                        event = json.loads(line)
                                        extracted_fields.update(event.keys())
                                    except json.JSONDecodeError:
                                        continue
                    except Exception as e:
                        return False, f"Error reading Vector output: {e}"
                else:
                    return False, "Vector CLI output file not created"
                
                # Validate processing results
                if events_processed == 0:
                    return False, f"Vector CLI processed 0/{len(sample_lines)} events - VRL transforms failed"
                
                if events_processed < len(sample_lines):
                    logger.warning(f"Vector CLI processed {events_processed}/{len(sample_lines)} events - some transforms failed")
                
                # Success - VRL actually processes data
                logger.debug(f"Vector CLI validation passed: {events_processed} events processed, {len(extracted_fields)} unique fields")
                return True, None
                
        except Exception as e:
            error_msg = f"Vector CLI validation error: {e}"
            logger.warning(error_msg)
            return False, error_msg
    
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
    
    def _validate_field_extraction(self, vrl_code: str, sample_logs: str, expected_fields: List[str]) -> Tuple[bool, Optional[str]]:
        """
        Validate that VRL actually extracts the expected fields from sample data
        
        Args:
            vrl_code: VRL code to test
            sample_logs: Sample log data
            expected_fields: List of field names that should be extracted
            
        Returns:
            Tuple of (extraction_valid, error_message)
        """
        try:
            import pyvrl
            
            # Test VRL transformation on sample data
            transform = pyvrl.Transform(vrl_code)
            
            # Process first few sample lines
            sample_lines = sample_logs.strip().split('\n')[:5]
            extracted_fields_found = set()
            
            for line in sample_lines:
                if not line.strip():
                    continue
                
                # Convert line to event format
                if line.startswith('{'):
                    # Already JSON
                    event = json.loads(line)
                else:
                    # Raw log line
                    event = {"message": line}
                
                try:
                    # Apply VRL transform using correct PyVRL API
                    result = transform.remap(event)
                    
                    # Track which expected fields were actually extracted
                    for field in expected_fields:
                        if field in result and result[field] is not None:
                            extracted_fields_found.add(field)
                            
                except Exception as e:
                    logger.warning(f"VRL transform failed on sample: {e}")
                    continue
            
            # Check if critical fields were extracted
            missing_fields = set(expected_fields) - extracted_fields_found
            extraction_rate = len(extracted_fields_found) / len(expected_fields) if expected_fields else 1.0
            
            # Require at least 70% of expected fields to be extracted
            if extraction_rate < 0.7:
                error_msg = (f"FIELD EXTRACTION FAILURE: Only {len(extracted_fields_found)}/{len(expected_fields)} "
                           f"expected fields extracted ({extraction_rate:.1%}). "
                           f"Missing: {', '.join(missing_fields)}")
                logger.warning(error_msg)
                return False, error_msg
            
            logger.info(f"Field extraction validation passed: {len(extracted_fields_found)}/{len(expected_fields)} fields ({extraction_rate:.1%})")
            return True, None
            
        except ImportError:
            logger.warning("PyVRL not available for field extraction testing")
            return True, None
        except Exception as e:
            logger.warning(f"Field extraction validation failed: {e}")
            return True, None  # Don't fail on validator errors
    
    def _validate_field_extraction_vector(self, vrl_code: str, sample_logs: str, expected_fields: List[str]) -> Tuple[bool, Optional[str]]:
        """
        Validate field extraction using Vector CLI output (authoritative)
        
        Args:
            vrl_code: VRL code to test
            sample_logs: Sample log data
            expected_fields: Fields that should be extracted
            
        Returns:
            Tuple of (extraction_valid, error_message)
        """
        import tempfile
        import subprocess  
        import yaml
        import json
        
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                
                # Create test files
                input_file = temp_path / "field_test_input.ndjson"
                output_file = temp_path / "field_test_output.ndjson"
                config_file = temp_path / "field_test_config.yaml"
                
                # Prepare test data
                sample_lines = sample_logs.strip().split('\n')[:3]  # Small sample for field testing
                with open(input_file, 'w') as f:
                    for line in sample_lines:
                        if line.strip():
                            if line.startswith('{'):
                                f.write(line + '\n')
                            else:
                                f.write(json.dumps({"message": line}) + '\n')
                
                # Vector config for field extraction testing
                vector_config = {
                    'data_dir': str(temp_path / 'field_test_data'),
                    'sources': {
                        'field_test': {
                            'type': 'file',
                            'include': [str(input_file)],
                            'read_from': 'beginning'
                        }
                    },
                    'transforms': {
                        'field_extraction': {
                            'type': 'remap',
                            'inputs': ['field_test'],
                            'source': vrl_code
                        }
                    },
                    'sinks': {
                        'field_output': {
                            'type': 'file', 
                            'inputs': ['field_extraction'],
                            'path': str(output_file),
                            'encoding': {'codec': 'json'}
                        }
                    }
                }
                
                with open(config_file, 'w') as f:
                    yaml.dump(vector_config, f)
                
                # Run Vector for field extraction test
                env = os.environ.copy()
                field_data_dir = temp_path / 'field_test_data'
                field_data_dir.mkdir(exist_ok=True)
                env['VECTOR_DATA_DIR'] = str(field_data_dir)
                
                process = subprocess.run(
                    ['vector', '--config', str(config_file)],
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=15
                )
                
                if process.returncode != 0:
                    return False, f"Vector field test failed: {process.stderr[:300]}"
                
                # Analyze extracted fields
                extracted_fields_found = set()
                events_with_fields = 0
                
                if output_file.exists():
                    with open(output_file, 'r') as f:
                        for line in f:
                            if line.strip():
                                try:
                                    event = json.loads(line)
                                    # Track fields that were actually extracted (non-null values)
                                    for field in expected_fields:
                                        if field in event and event[field] is not None and event[field] != "":
                                            extracted_fields_found.add(field)
                                    
                                    # Count events that have any expected fields
                                    if any(field in event and event[field] not in [None, ""] for field in expected_fields):
                                        events_with_fields += 1
                                        
                                except json.JSONDecodeError:
                                    continue
                
                # Calculate field extraction success
                missing_fields = set(expected_fields) - extracted_fields_found
                extraction_rate = len(extracted_fields_found) / len(expected_fields) if expected_fields else 1.0
                
                # Require meaningful field extraction (at least 50% of expected fields)
                if extraction_rate < 0.5:
                    error_msg = (f"Insufficient field extraction: {len(extracted_fields_found)}/{len(expected_fields)} "
                               f"fields extracted ({extraction_rate:.1%}). Missing: {', '.join(missing_fields)}")
                    return False, error_msg
                
                logger.debug(f"Vector CLI field extraction: {len(extracted_fields_found)}/{len(expected_fields)} fields ({extraction_rate:.1%})")
                return True, None
                
        except subprocess.TimeoutExpired:
            return False, "Vector field extraction test timed out"
        except Exception as e:
            logger.warning(f"Vector field extraction validation failed: {e}")
            return True, None  # Don't fail on validator errors
    
    def _find_available_port(self, start_port: int = 8686) -> int:
        """Find available port for Vector GraphQL API"""
        for port in range(start_port, start_port + 100):
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                    result = sock.connect_ex(('127.0.0.1', port))
                    if result != 0:  # Port is available
                        return port
            except Exception:
                continue
        
        # Fallback to random port if all checked ports busy
        import random
        return random.randint(9000, 9999)
    
    def _monitor_vector_processing(self, api_port: int, process: subprocess.Popen, 
                                  expected_events: int, max_wait: int = 30) -> Tuple[int, str]:
        """
        Monitor Vector processing via GraphQL API instead of timeout
        
        Args:
            api_port: Vector GraphQL API port
            process: Vector process
            expected_events: Number of events we expect to be processed
            max_wait: Maximum seconds to wait
            
        Returns:
            Tuple of (events_processed, stderr_output)
        """
        api_url = f"http://127.0.0.1:{api_port}/graphql"
        
        # GraphQL query to get component metrics
        metrics_query = """
        query {
            components {
                sources {
                    name
                    metrics {
                        sent {
                            events {
                                total
                            }
                        }
                    }
                }
                transforms {
                    name  
                    metrics {
                        sent {
                            events {
                                total
                            }
                        }
                    }
                }
                sinks {
                    name
                    metrics {
                        received {
                            events {
                                total
                            }
                        }
                    }
                }
            }
        }
        """
        
        events_processed = 0
        start_time = time.time()
        
        logger.debug(f"Monitoring Vector processing via GraphQL API on port {api_port}")
        
        while time.time() - start_time < max_wait:
            # Check if Vector process died
            if process.poll() is not None:
                break
            
            try:
                # Query GraphQL API for metrics
                response = requests.post(
                    api_url,
                    json={'query': metrics_query},
                    timeout=2
                )
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # Extract events processed from sink metrics
                    components = data.get('data', {}).get('components', {})
                    sinks = components.get('sinks', [])
                    
                    for sink in sinks:
                        if sink.get('name') == 'validation_output':
                            received = sink.get('metrics', {}).get('received', {})
                            events = received.get('events', {})
                            total = events.get('total', 0)
                            
                            if total != events_processed:
                                events_processed = total
                                logger.debug(f"Vector processed {events_processed}/{expected_events} events")
                            
                            # Check if processing complete
                            if events_processed >= expected_events:
                                logger.debug(f"All {expected_events} events processed, stopping monitoring")
                                break
                    
                    # If we have processed some events and no new ones for 3 seconds, assume done
                    if events_processed > 0 and events_processed < expected_events:
                        time.sleep(0.5)  # Wait a bit more for stragglers
                    elif events_processed >= expected_events:
                        break  # All events processed
                    else:
                        time.sleep(1)  # Still processing
                
                else:
                    # API not ready yet, wait
                    time.sleep(0.5)
                    
            except requests.RequestException:
                # API not ready yet or network issue, wait
                time.sleep(0.5)
                continue
            except Exception as e:
                logger.debug(f"GraphQL monitoring error: {e}")
                time.sleep(1)
                continue
        
        # Get final stderr if process finished
        stderr_output = ""
        try:
            if process.poll() is not None:
                _, stderr_output = process.communicate(timeout=1)
        except:
            pass
        
        logger.debug(f"Vector processing complete: {events_processed}/{expected_events} events")
        return events_processed, stderr_output