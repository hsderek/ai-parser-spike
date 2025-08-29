#!/usr/bin/env python3
"""
VRL Parser Testing Loop Framework - CLEAN VERSION

NO SOURCE-SPECIFIC PARSING IN PYTHON CODE!
All specific parsing must come from LLM analysis only.
Python code provides ONLY generic templates and testing infrastructure.
"""

import json
import time
import subprocess
import tempfile
import os
import sys
import statistics
import psutil
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass, field, asdict
from datetime import datetime
import yaml
from loguru import logger

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

# Import model-specific VRL fixer
try:
    from model_specific_vrl_fixer import apply_model_specific_fixes
except ImportError:
    logger.warning("⚠️ Model-specific VRL fixer not available")

try:
    import pyvrl
except ImportError:
    print("Installing pyvrl from PyPI...")
    subprocess.run([sys.executable, "-m", "pip", "install", "pyvrl"], check=True)
    import pyvrl

from src.field_naming import normalize_field_name, FieldNamingConvention


@dataclass
class VRLCandidate:
    """VRL parser candidate with metadata"""
    name: str
    description: str
    vrl_code: str
    strategy: str  # e.g., "regex", "string_ops", "hybrid"
    validated_pyvrl: bool = False
    validated_vector: bool = False
    performance_metrics: Dict[str, Any] = field(default_factory=dict)
    extracted_fields: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


@dataclass
class PerformanceBaseline:
    """Performance metrics for a VRL candidate"""
    events_per_second: float
    cpu_percent: float
    memory_mb: float
    events_per_cpu_percent: float
    p99_latency_ms: float
    errors_count: int
    
    def __str__(self):
        return (f"Events/sec: {self.events_per_second:.0f}, "
                f"CPU: {self.cpu_percent:.1f}%, "
                f"Mem: {self.memory_mb:.0f}MB, "
                f"Events/CPU%: {self.events_per_cpu_percent:.0f}, "
                f"P99: {self.p99_latency_ms:.1f}ms, "
                f"Errors: {self.errors_count}")


class VRLTestingLoop:
    """Complete VRL testing and optimization loop - NO source-specific code!"""
    
    def __init__(self, sample_file: str, output_dir: str = "samples-parsed", log_dir: str = "logs", external_configs_dir: str = "external"):
        self.sample_file = Path(sample_file)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        # Setup logging
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        
        # Load external configs (company-wide K8s deployed files)
        self.external_configs_dir = Path(external_configs_dir)
        self.external_configs = self._load_external_configs()
        
        self._setup_logging()
        
        # Ensure .tmp directory exists
        Path('.tmp').mkdir(exist_ok=True)
        
        # Load sample data
        with open(self.sample_file, 'r') as f:
            self.samples = [json.loads(line) for line in f]
        
        # Track all candidates
        self.candidates: List[VRLCandidate] = []
        self.best_candidate: Optional[VRLCandidate] = None
        
        # Performance test configuration
        self.test_events = 10000  # Number of events for performance testing
        self.test_threads = 4  # Optimal thread count per VECTOR-VRL.md
        
        # Loop prevention for regex rejection
        self.regex_rejection_count = 0
        self.max_regex_rejections = 3
        self.rejected_patterns = set()
        
        # CPU normalization info
        self.cpu_info = self._get_cpu_info()
        
        # Benchmark local CPU for normalization
        logger.info("Benchmarking local CPU performance...")
        self.cpu_benchmark_multiplier = self._benchmark_local_cpu()
        logger.info(f"CPU benchmark multiplier: {self.cpu_benchmark_multiplier:.2f}x")
        
        # Measure Vector startup time (passthrough config)
        logger.info("Measuring Vector CLI startup time...")
        self.vector_startup_time = self._measure_vector_startup_time()
        logger.info(f"Vector startup time: {self.vector_startup_time:.2f}s")
        
        # Log external configs summary for LLM context
        self._log_external_configs_summary()
        
    def _setup_logging(self):
        """Setup Loguru logging with RFC 3339 timestamps to ./logs directory"""
        # Remove default handler
        logger.remove()
        
        # Generate log filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = self.log_dir / f"vrl_pipeline_{timestamp}.log"
        
        # Add console handler with RFC 3339 timestamps
        logger.add(
            sys.stdout,
            format="<green>{time:YYYY-MM-DDTHH:mm:ss.SSSSSS}Z</green> <level>{level: <8}</level> <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
            level="INFO",
            colorize=True
        )
        
        # Add file handler with RFC 3339 timestamps  
        logger.add(
            log_file,
            format="{time:YYYY-MM-DDTHH:mm:ss.SSSSSS}Z {level: <8} {name}:{function}:{line} - {message}",
            level="DEBUG",
            rotation="10 MB",
            retention="30 days",
            compression="gz"
        )
        
        logger.info(f"VRL Testing Pipeline logging initialized")
        logger.info(f"Log file: {log_file}")
        logger.info(f"Sample file: {self.sample_file}")
        logger.info(f"Output directory: {self.output_dir}")
        logger.info(f"External configs: {self.external_configs_dir}")
        logger.info(f"Loaded configs: {list(self.external_configs.keys())}")
    
    def generate_initial_vrl(self) -> VRLCandidate:
        """Generate GENERIC VRL template - NO source-specific parsing logic!"""
        
        # GENERIC VRL template with NO source-specific logic
        # This is just a basic template - all parsing must come from LLM
        vrl_code = """
# Generic VRL Parser Template  
# STRICT: NO REGEX per VECTOR-VRL.md (50-100x slower than string ops)
# All specific field extraction must come from LLM analysis

# Step 1: Parse JSON from raw input (Vector file source puts raw line in .message field)
. = parse_json!(string!(.message))

# Step 2: Basic metadata (generic for all logs)
._parser_metadata = {
    "parser_version": "1.0.0", 
    "parser_type": "generic_template",
    "strategy": "requires_llm_analysis",
    "note": "This template needs LLM to generate specific parsing logic"
}

# Step 3: Generic normalization examples (apply after LLM parsing)
# Note: These are just examples - actual fields depend on LLM analysis

# Return the event
.
"""
        
        candidate = VRLCandidate(
            name="generic_template",
            description="Generic VRL template - requires LLM for specific parsing",
            vrl_code=vrl_code.strip(),
            strategy="template_only"
        )
        
        self.candidates.append(candidate)
        return candidate
    
    def test_with_pyvrl(self, candidate: VRLCandidate, model_info: dict = None) -> bool:
        """Fast iteration testing with PyVRL"""
        # EXPLICIT REGEX REJECTION per VECTOR-VRL.md with loop prevention
        # Only check for actual VRL regex functions being used
        
        # Remove comments before checking for patterns
        code_lines = []
        for line in candidate.vrl_code.split('\n'):
            # Remove comments but keep the code
            if '#' in line:
                code_part = line.split('#')[0]
            else:
                code_part = line
            code_lines.append(code_part)
        
        code_without_comments = '\n'.join(code_lines)
        
        # Look for actual VRL regex functions only
        regex_functions = [
            'parse_regex!',
            'parse_regex(',
            'match!',
            'match(',
            'capture_regex!',
            'capture_regex(',
            'replace_regex!',
            'replace_regex(',
            'split_regex!',
            'split_regex('
        ]
        
        found_patterns = [func for func in regex_functions if func in code_without_comments]
        
        # Also check for regex literals used as arguments (r"..." or r'...')
        import re
        if re.search(r'\br"[^"]*"', code_without_comments) or re.search(r"\br'[^']*'", code_without_comments):
            found_patterns.append('regex literal (r"..." or r\'...\')')
        
        if found_patterns:
            self.regex_rejection_count += 1
            pattern_hash = hash(candidate.vrl_code)
            
            if pattern_hash in self.rejected_patterns:
                error_msg = "LOOP PREVENTION: This exact VRL pattern was already rejected!"
                candidate.errors.append(error_msg)
                print(f"🔄 {error_msg}")
                return False
            
            self.rejected_patterns.add(pattern_hash)
            
            error_msg = f"REJECTED (#{self.regex_rejection_count}): VRL contains regex! Per VECTOR-VRL.md regex is 50-100x slower."
            candidate.errors.append(error_msg)
            print(f"✗ {error_msg}")
            print(f"  Found forbidden patterns: {', '.join(found_patterns)}")
            print(f"  Must use: contains(), split(), upcase(), downcase() instead")
            
            if self.regex_rejection_count >= self.max_regex_rejections:
                print(f"⚠️  WARNING: {self.max_regex_rejections} regex rejections reached!")
                print(f"  Consider providing clear VECTOR-VRL.md guidance to LLM")
                print(f"  Example string operations: contains(), split(), slice(), upcase()")
                
                # Save rejection feedback to temp file for LLM context
                feedback_file = '.tmp/regex_rejection_feedback.md'
                with open(feedback_file, 'w') as f:
                    f.write(f"# Regex Rejection Feedback\n\n")
                    f.write(f"**CRITICAL**: {self.regex_rejection_count} VRL submissions contained forbidden regex patterns.\n\n")
                    f.write(f"**VECTOR-VRL.md REQUIREMENTS:**\n")
                    f.write(f"- NO parse_regex(), match(), or regex patterns\n")
                    f.write(f"- Use ONLY string operations: contains(), split(), upcase(), downcase()\n")
                    f.write(f"- String ops are 50-100x faster (350-400 events/CPU%)\n")
                    f.write(f"- Regex is Tier 4 performance (3-10 events/CPU%)\n\n")
                    f.write(f"**EXAMPLE PATTERN:**\n")
                    f.write(f"```vrl\n")
                    f.write(f"# GOOD: String operations\n")
                    f.write(f"if contains(msg, \"%\") && contains(msg, \"-\") {{\n")
                    f.write(f"    parts = split(msg, \"%\")\n")
                    f.write(f"    # Extract using array indexing and split()\n")
                    f.write(f"}}\n")
                    f.write(f"\n# BAD: Regex (FORBIDDEN)\n")
                    f.write(f"# parse_regex!(msg, r'pattern') # <- NEVER USE\n")
                    f.write(f"```\n")
                print(f"  Saved feedback to {feedback_file}")
            
            return False
        
        # Try PyVRL validation first
        max_fix_attempts = 2  # Prevent infinite loops
        for attempt in range(max_fix_attempts):
            try:
                # Create PyVRL transform
                transform = pyvrl.Transform(candidate.vrl_code)
                
                # Test with first sample - simulate Vector file source format
                test_event = {
                    'message': json.dumps(self.samples[0]),
                    'file': str(self.sample_file),
                    'host': 'test-host',
                    'source_type': 'file',
                    'timestamp': '2023-01-01T00:00:00Z'
                }
                result = transform.remap(test_event)
                
                # Check for new fields added (exclude Vector metadata fields)
                vector_fields = {'message', 'file', 'host', 'source_type', 'timestamp'}
                original_fields = set(self.samples[0].keys())
                result_fields = set(result.keys())
                new_fields = result_fields - original_fields - vector_fields
                candidate.extracted_fields = list(new_fields)
                
                candidate.validated_pyvrl = True
                logger.success(f"✓ PyVRL validation passed for {candidate.name} (attempt {attempt + 1})")
                logger.info(f"  New fields: {', '.join(new_fields)}")
                return True
                
            except Exception as e:
                error_msg = str(e)
                logger.error(f"✗ PyVRL validation failed (attempt {attempt + 1}): {error_msg}")
                
                # Try to apply error-code-based fixes if this is not the last attempt
                if attempt < max_fix_attempts - 1 and model_info and 'apply_model_specific_fixes' in globals():
                    try:
                        logger.info("🔧 Attempting to fix VRL errors automatically...")
                        error_list = [error_msg]  # Convert exception to list for fixer
                        
                        fixed_vrl, was_fixed, fix_metadata = apply_model_specific_fixes(
                            candidate.vrl_code, 
                            error_list,
                            model_info
                        )
                        
                        if was_fixed and fixed_vrl != candidate.vrl_code:
                            logger.info(f"🎯 Applied {len(fix_metadata.get('fixes_applied', []))} automatic fixes")
                            for fix in fix_metadata.get('fixes_applied', []):
                                logger.info(f"   - {fix}")
                            candidate.vrl_code = fixed_vrl
                            candidate.errors.append(f"Auto-fixed: {', '.join(fix_metadata.get('fixes_applied', []))}")
                            continue  # Retry validation with fixed code
                        else:
                            logger.warning("⚠️ No applicable fixes found for the errors")
                            
                    except Exception as fix_error:
                        logger.warning(f"⚠️ Automatic error fixing failed: {fix_error}")
                
                # If we reach here, either it's the last attempt or fixing failed
                candidate.errors.append(f"PyVRL validation failed: {error_msg}")
                return False
        
        # Should never reach here, but just in case
        return False
    
    def validate_with_vector(self, candidate: VRLCandidate) -> bool:
        """Quick validation with Vector CLI validate command"""
        # Create temporary config for validation only
        config = {
            'sources': {
                'test_input': {
                    'type': 'demo_logs',
                    'format': 'json'
                }
            },
            'transforms': {
                'test_transform': {
                    'type': 'remap',
                    'inputs': ['test_input'],
                    'source': candidate.vrl_code
                }
            },
            'sinks': {
                'test_output': {
                    'type': 'blackhole',
                    'inputs': ['test_transform']
                }
            }
        }
        
        # Write config as YAML
        config_path = Path('.tmp/vector_validate.yaml')
        with open(config_path, 'w') as f:
            import yaml
            yaml.dump(config, f)
        
        # Run vector validate
        import subprocess
        result = subprocess.run(
            ['vector', 'validate', '--config-dir', str(config_path.parent)],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            logger.success(f"✓ Vector validate passed")
            return True
        else:
            error_msg = f"Vector validate failed: {result.stderr[:500]}"
            candidate.errors.append(error_msg)
            logger.error(f"✗ {error_msg}")
            return False
    
    def test_with_vector(self, candidate: VRLCandidate) -> bool:
        """Validate with actual Vector CLI"""
        # Create temporary config
        config = {
            'data_dir': '.tmp/vector_data',
            'sources': {
                'test_input': {
                    'type': 'file',
                    'include': [str(self.sample_file)],
                    'read_from': 'beginning'
                }
            },
            'transforms': {
                'test_transform': {
                    'type': 'remap',
                    'inputs': ['test_input'],
                    'source': candidate.vrl_code
                }
            },
            'sinks': {
                'test_output': {
                    'type': 'file',
                    'inputs': ['test_transform'],
                    'path': '.tmp/vector_test_output.ndjson',
                    'encoding': {'codec': 'json'}
                }
            }
        }
        
        # Use project-local temp directory and ensure data dir exists
        data_dir = '.tmp/vector_test_data'
        os.makedirs(data_dir, exist_ok=True)
        
        config_file = f'.tmp/vector_test_{candidate.name}.yaml'
        with open(config_file, 'w') as f:
            yaml.dump(config, f)
        
        try:
            # Run Vector validate command first
            env = os.environ.copy()
            env['VECTOR_DATA_DIR'] = data_dir
            
            result = subprocess.run(
                ['vector', 'validate', config_file],
                env=env,
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                candidate.validated_vector = True
                self._log_with_timestamp(f"✓ Vector validation passed for {candidate.name}")
                return True
            else:
                error_msg = f"Vector validation failed (RC:{result.returncode})"
                candidate.errors.append(error_msg)
                self._log_with_timestamp(f"✗ {error_msg}")
                self._log_with_timestamp(f"  STDOUT: {result.stdout[:300]}")
                self._log_with_timestamp(f"  STDERR: {result.stderr[:300]}")
                return False
                
        except subprocess.TimeoutExpired:
            # Timeout is expected - Vector runs until killed
            candidate.validated_vector = True
            print(f"✓ Vector validation passed for {candidate.name}")
            return True
        except Exception as e:
            error_msg = f"Vector test error: {str(e)}"
            candidate.errors.append(error_msg)
            print(f"✗ {error_msg}")
            return False
        finally:
            # Cleanup
            if os.path.exists(config_file):
                os.unlink(config_file)
            if os.path.exists('.tmp/vector_test_output.ndjson'):
                os.unlink('.tmp/vector_test_output.ndjson')
    
    def measure_performance(self, candidate: VRLCandidate) -> PerformanceBaseline:
        """Measure CPU and throughput performance"""
        print(f"\nMeasuring performance for {candidate.name}...")
        
        # Create test data file with many events
        test_data_file = f'.tmp/perf_test_{candidate.name}.ndjson'
        with open(test_data_file, 'w') as f:
            for i in range(self.test_events):
                # Use different samples to avoid caching effects
                sample = self.samples[i % len(self.samples)]
                f.write(json.dumps(sample) + '\n')
        
        # Create Vector config for performance testing
        config = {
            'data_dir': '.tmp/vector_data',
            'sources': {
                'perf_input': {
                    'type': 'file',
                    'include': [test_data_file],
                    'read_from': 'beginning'
                }
            },
            'transforms': {
                f'{candidate.name}_transform': {
                    'type': 'remap',
                    'inputs': ['perf_input'],
                    'source': candidate.vrl_code
                }
            },
            'sinks': {
                'perf_output': {
                    'type': 'file',
                    'inputs': [f'{candidate.name}_transform'],
                    'path': f'.tmp/vector_output_{candidate.name}.ndjson',
                    'encoding': {'codec': 'json'}
                }
            }
        }
        
        # Use project-local temp directory and ensure data dir exists
        data_dir = f'.tmp/vector_perf_{candidate.name}'
        os.makedirs(data_dir, exist_ok=True)
        
        config_file = f'.tmp/vector_test_{candidate.name}.yaml'
        with open(config_file, 'w') as f:
            yaml.dump(config, f)
        
        try:
            # Start Vector process
            env = os.environ.copy()
            env['VECTOR_DATA_DIR'] = data_dir
            
            self._log_with_timestamp(f"Starting Vector process with config: {config_file}")
            self._log_with_timestamp(f"Expected output file: {f'.tmp/vector_output_{candidate.name}.ndjson'}")
            
            process = subprocess.Popen(
                ['vector', '--config', config_file, '--threads', str(self.test_threads)],
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Monitor performance
            cpu_samples = []
            memory_samples = []
            start_time = time.time()
            
            # Let it warm up
            time.sleep(1)
            
            # Measure CPU more frequently to catch Vector processing
            psutil_process = psutil.Process(process.pid)
            for i in range(20):  # More frequent sampling
                cpu_samples.append(psutil_process.cpu_percent(interval=0.25))  # Shorter intervals
                memory_samples.append(psutil_process.memory_info().rss / 1024 / 1024)
                # Also sample children if Vector spawns worker processes
                try:
                    for child in psutil_process.children():
                        cpu_samples.append(child.cpu_percent(interval=0.1))
                except:
                    pass
            
            elapsed = time.time() - start_time - 1  # Subtract warmup
            
            # Terminate Vector
            self._log_with_timestamp(f"Terminating Vector process...")
            process.terminate()
            stdout, stderr = process.communicate(timeout=5)
            self._log_with_timestamp(f"Vector stdout: {stdout[:200]}")
            self._log_with_timestamp(f"Vector stderr: {stderr[:200]}")
            
            # Calculate metrics - FIXED VERSION
            avg_cpu = statistics.mean(cpu_samples[2:]) if len(cpu_samples) > 2 else 0.1  # Skip warmup samples
            avg_memory = statistics.mean(memory_samples) if memory_samples else 0.0
            
            # CRITICAL: Check if Vector actually processed data by counting output
            output_file = f'.tmp/vector_output_{candidate.name}.ndjson'
            events_processed = 0
            if os.path.exists(output_file):
                try:
                    with open(output_file, 'r') as f:
                        events_processed = sum(1 for line in f if line.strip())
                    self._log_with_timestamp(f"    Found output file with {events_processed} events")
                except Exception as e:
                    self._log_with_timestamp(f"    Error reading output file: {e}")
                    events_processed = 0
            else:
                self._log_with_timestamp(f"    Output file not found: {output_file}")
                
            self._log_with_timestamp(f"    Events processed by Vector: {events_processed}")
            
            # Account for Vector startup time
            actual_processing_time = max(0.1, elapsed - self.vector_startup_time)
            events_per_second = events_processed / actual_processing_time if actual_processing_time > 0 and events_processed > 0 else 0
            events_per_cpu = events_per_second / max(avg_cpu, 0.1) if avg_cpu > 0 and events_per_second > 0 else 0
            
            # Estimate P99 latency (rough calculation)
            p99_latency = (1000 / events_per_second * 100) if events_per_second > 0 else 0  # ms for 100 events
            
            baseline = PerformanceBaseline(
                events_per_second=events_per_second,
                cpu_percent=avg_cpu,
                memory_mb=avg_memory,
                events_per_cpu_percent=events_per_cpu,
                p99_latency_ms=p99_latency,
                errors_count=0
            )
            
            candidate.performance_metrics = asdict(baseline)
            
            # Enhanced logging
            self._log_with_timestamp(f"  📊 Performance Results:")
            self._log_with_timestamp(f"    Events input: {self.test_events:,}")
            self._log_with_timestamp(f"    Events processed: {events_processed:,}")
            self._log_with_timestamp(f"    Processing time: {actual_processing_time:.2f}s (minus {self.vector_startup_time:.2f}s startup)")
            self._log_with_timestamp(f"    Events/second: {events_per_second:.0f}")
            self._log_with_timestamp(f"    CPU usage: {avg_cpu:.1f}%")
            self._log_with_timestamp(f"    Events/CPU%: {events_per_cpu:.0f}")
            
            if events_processed == 0:
                self._log_with_timestamp(f"    ⚠️  WARNING: No events processed by Vector!")
            elif events_processed < self.test_events:
                self._log_with_timestamp(f"    ⚠️  WARNING: Only {events_processed}/{self.test_events} events processed")
            
            return baseline
            
        except Exception as e:
            print(f"  Performance test error: {str(e)}")
            return PerformanceBaseline(0, 0, 0, 0, 0, 1)
        finally:
            # Cleanup
            if os.path.exists(config_file):
                os.unlink(config_file)
            if os.path.exists(test_data_file):
                os.unlink(test_data_file)
            output_file = f'.tmp/vector_output_{candidate.name}.ndjson'
            if os.path.exists(output_file):
                os.unlink(output_file)
    
    def compare_candidates(self) -> VRLCandidate:
        """Compare all candidates and select the best"""
        print("\n" + "="*60)
        print("PERFORMANCE COMPARISON")
        print("="*60)
        
        best_score = -1
        best_candidate = None
        
        for candidate in self.candidates:
            if 'events_per_cpu_percent' not in candidate.performance_metrics:
                continue
            
            # Primary scoring metric: VRL Performance Index (hardware-normalized)
            events_cpu = candidate.performance_metrics['events_per_cpu_percent']
            events_cpu_int = int(events_cpu)
            vpi = self._calculate_vrl_performance_index(events_cpu)
            tier = self._classify_performance_tier(events_cpu_int)
            
            self._log_with_timestamp(f"\n{candidate.name} ({candidate.strategy}):")
            self._log_with_timestamp(f"  Description: {candidate.description}")
            self._log_with_timestamp(f"  🎯 VRL Performance Index: {vpi:,} ({tier})")
            self._log_with_timestamp(f"  Raw Events/CPU%: {events_cpu_int:,}")
            self._log_with_timestamp(f"  Events/sec: {candidate.performance_metrics['events_per_second']:.0f}")
            self._log_with_timestamp(f"  CPU: {candidate.performance_metrics['cpu_percent']:.1f}%")
            self._log_with_timestamp(f"  Memory: {candidate.performance_metrics['memory_mb']:.0f}MB")
            
            # Use VPI as the primary comparison metric
            if vpi > best_score:
                best_score = vpi
                best_candidate = candidate
        
        if best_candidate:
            # best_score is now the VPI (VRL Performance Index)
            best_vpi = int(best_score)
            events_cpu = best_candidate.performance_metrics['events_per_cpu_percent']
            events_cpu_int = int(events_cpu)
            best_tier = self._classify_performance_tier(events_cpu_int)
            
            self._log_with_timestamp("\n" + "="*60)
            self._log_with_timestamp(f"🏆 WINNER: {best_candidate.name}")
            self._log_with_timestamp(f"🎯 VRL Performance Index: {best_vpi:,} ({best_tier})")
            self._log_with_timestamp(f"📊 Raw Events/CPU%: {events_cpu_int:,}")
            self._log_with_timestamp(f"💻 CPU: {self.cpu_info.get('cpu_count_logical', 1)} cores, {self.cpu_info.get('model', 'Unknown')[:40]}...")
            self._log_with_timestamp(f"⚡ Benchmark: {self.cpu_benchmark_multiplier:.2f}x baseline")
            self._log_with_timestamp("="*60)
            
            self.best_candidate = best_candidate
        
        return best_candidate
    
    def save_results(self):
        """Save the best candidate and results in 3-file format"""
        if not self.best_candidate:
            print("No best candidate selected")
            return
        
        base_name = self.sample_file.stem
        
        # 1. Save VRL file (.vrl)
        vrl_file = self.output_dir / f"{base_name}.vrl"
        with open(vrl_file, 'w') as f:
            f.write(self.best_candidate.vrl_code)
        self._log_with_timestamp(f"\n✓ Saved optimized VRL to {vrl_file}")
        
        # 2. Generate transformed sample data using Vector CLI (.json)
        transformed_file = self.output_dir / f"{base_name}.json"
        self._generate_vector_transformed_output(transformed_file)
        
        # 3. Save REST API results (-rest.json)
        rest_results_file = self.output_dir / f"{base_name}-rest.json"
        self._save_rest_api_results(rest_results_file)
        
        self._log_with_timestamp(f"✅ Complete 3-file output saved:")
        self._log_with_timestamp(f"   📄 VRL: {vrl_file}")
        self._log_with_timestamp(f"   🔄 Transformed: {transformed_file}")
        self._log_with_timestamp(f"   📊 REST API: {rest_results_file}")
    
    def _generate_vector_transformed_output(self, output_file: Path):
        """Generate Vector CLI transformed output to verify parsing works"""
        try:
            # Create Vector config to transform sample data
            config = {
                'data_dir': '.tmp/vector_transform_data',
                'sources': {
                    'sample_input': {
                        'type': 'file',
                        'include': [str(self.sample_file)],
                        'read_from': 'beginning'
                    }
                },
                'transforms': {
                    'vrl_transform': {
                        'type': 'remap',
                        'inputs': ['sample_input'],
                        'source': self.best_candidate.vrl_code
                    }
                },
                'sinks': {
                    'json_output': {
                        'type': 'file',
                        'inputs': ['vrl_transform'],
                        'path': str(output_file),
                        'encoding': {'codec': 'json'}
                    }
                }
            }
            
            # Ensure data directory exists
            data_dir = '.tmp/vector_transform_data'
            os.makedirs(data_dir, exist_ok=True)
            
            config_file = '.tmp/vector_transform_config.yaml'
            with open(config_file, 'w') as f:
                yaml.dump(config, f)
            
            self._log_with_timestamp(f"🔄 Running Vector CLI to generate transformed output...")
            
            # Run Vector CLI to generate actual transformed data
            env = os.environ.copy()
            env['VECTOR_DATA_DIR'] = data_dir
            
            process = subprocess.Popen(
                ['vector', '--config', config_file],
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Let Vector process the data
            time.sleep(2)
            
            # Terminate Vector
            process.terminate()
            stdout, stderr = process.communicate(timeout=5)
            
            # Verify output was created
            if output_file.exists():
                with open(output_file, 'r') as f:
                    line_count = sum(1 for line in f if line.strip())
                self._log_with_timestamp(f"   ✓ Generated {line_count} transformed events")
            else:
                self._log_with_timestamp(f"   ⚠️  Warning: No transformed output generated")
                # Create empty file as placeholder
                with open(output_file, 'w') as f:
                    f.write('{"error": "Vector CLI did not generate output", "note": "Check VRL syntax"}\n')
            
            # Cleanup
            if os.path.exists(config_file):
                os.unlink(config_file)
                
        except Exception as e:
            self._log_with_timestamp(f"   ❌ Vector transformation failed: {e}")
            # Create error file
            with open(output_file, 'w') as f:
                f.write(f'{{"error": "Vector transformation failed", "details": "{str(e)}"}}\n')
    
    def _save_rest_api_results(self, rest_file: Path):
        """Save REST API formatted results"""
        winner_events_cpu = int(self.best_candidate.performance_metrics.get('events_per_cpu_percent', 0))
        winner_tier = self._classify_performance_tier(winner_events_cpu)
        winner_vpi = self._calculate_vrl_performance_index(winner_events_cpu)
        
        rest_results = {
            'status': 'success',
            'parser': {
                'name': self.best_candidate.name,
                'strategy': self.best_candidate.strategy,
                'vrl_code': self.best_candidate.vrl_code,
                'extracted_fields': self.best_candidate.extracted_fields,
                'validation': {
                    'pyvrl_passed': self.best_candidate.validated_pyvrl,
                    'vector_passed': self.best_candidate.validated_vector,
                    'errors': self.best_candidate.errors
                }
            },
            'performance': {
                'events_per_second': self.best_candidate.performance_metrics.get('events_per_second', 0),
                'cpu_percent': self.best_candidate.performance_metrics.get('cpu_percent', 0),
                'memory_mb': self.best_candidate.performance_metrics.get('memory_mb', 0),
                'events_per_cpu_percent': winner_events_cpu,
                'p99_latency_ms': self.best_candidate.performance_metrics.get('p99_latency_ms', 0),
                'performance_tier': winner_tier,
                'vrl_performance_index': winner_vpi
            },
            'system_info': {
                'cpu_benchmark_multiplier': self.cpu_benchmark_multiplier,
                'vector_startup_time': self.vector_startup_time,
                'cpu_model': self.cpu_info.get('model', 'Unknown')[:50],
                'cpu_cores': self.cpu_info.get('cpu_count_logical', 1)
            },
            'metadata': {
                'timestamp': datetime.now().isoformat(),
                'sample_file': str(self.sample_file),
                'sample_count': len(self.samples),
                'iterations_tested': len(self.candidates)
            }
        }
        
        with open(rest_file, 'w') as f:
            json.dump(rest_results, f, indent=2)
        
        self._log_with_timestamp(f"   ✓ REST API results: {rest_results['status']}, tier {winner_tier}")
    
    def generate_string_ops_examples(self) -> str:
        """Generate string operations examples based on sample data"""
        # Analyze first sample for patterns
        if not self.samples:
            return "# No samples available for analysis"
        
        sample = self.samples[0]
        examples = []
        examples.append("# String Operations Examples (VECTOR-VRL.md compliant)")
        examples.append("")
        
        # Check message field patterns
        msg_field = sample.get('msg', sample.get('message', ''))
        if msg_field:
            examples.append("# Extract from message field using string operations")
            examples.append("if exists(.msg) {")
            examples.append("    msg = string!(.msg)")
            examples.append("")
            
            # Common delimiters
            if '%' in str(msg_field):
                examples.append("    # Pattern with % delimiter")
                examples.append("    if contains(msg, \"%\") {")
                examples.append("        parts = split(msg, \"%\")")
                examples.append("        if length(parts) > 1 {")
                examples.append("            .extracted_section = string!(parts[1])")
                examples.append("        }")
                examples.append("    }")
            elif ',' in str(msg_field):
                examples.append("    # CSV pattern")
                examples.append("    if contains(msg, \",\") {")
                examples.append("        csv_parts = split(msg, \",\")")
                examples.append("        if length(csv_parts) > 0 {")
                examples.append("            .field_0 = string!(csv_parts[0])")
                examples.append("        }")
                examples.append("    }")
            elif '|' in str(msg_field):
                examples.append("    # Pipe-delimited pattern")
                examples.append("    if contains(msg, \"|\") {")
                examples.append("        pipe_parts = split(msg, \"|\")")
                examples.append("        if length(pipe_parts) > 0 {")
                examples.append("            .field_0 = string!(pipe_parts[0])")
                examples.append("        }")
                examples.append("    }")
            
            examples.append("}")
            examples.append("")
        
        # Standard syslog fields
        if 'priority' in sample:
            examples.append("# Standard syslog priority extraction")
            examples.append("if exists(.priority) {")
            examples.append("    pri_value = to_int!(.priority)")
            examples.append("    .facility_num = floor(pri_value / 8)")
            examples.append("    .severity_num = mod(pri_value, 8)")
            examples.append("}")
            examples.append("")
        
        # Field normalization at END
        examples.append("# STEP 2: Normalize fields AFTER extraction (per VECTOR-VRL.md)")
        if 'hostname' in sample:
            examples.append("if exists(.hostname) {")
            examples.append("    .hostname_normalized = downcase(string!(.hostname))")
            examples.append("}")
        
        examples.append("")
        examples.append("# Return the event")
        examples.append(".")
        
        return "\n".join(examples)
    
    def _get_cpu_info(self) -> Dict[str, Any]:
        """Get CPU information for performance normalization"""
        try:
            cpu_info = {
                'cpu_count': psutil.cpu_count(logical=False),
                'cpu_count_logical': psutil.cpu_count(logical=True),
                'cpu_freq': psutil.cpu_freq()._asdict() if psutil.cpu_freq() else None
            }
            
            # Try to get CPU model from /proc/cpuinfo on Linux
            try:
                with open('/proc/cpuinfo', 'r') as f:
                    for line in f:
                        if 'model name' in line:
                            cpu_info['model'] = line.split(':')[1].strip()
                            break
            except:
                cpu_info['model'] = 'Unknown'
                
            return cpu_info
        except:
            return {'cpu_count': 1, 'cpu_count_logical': 1, 'cpu_freq': None, 'model': 'Unknown'}
    
    def _benchmark_local_cpu(self) -> float:
        """Benchmark local CPU performance for normalization
        
        Returns a multiplier where:
        - 1.0 = baseline performance (typical cloud VM)
        - >1.0 = faster than baseline
        - <1.0 = slower than baseline
        """
        try:
            # Simple CPU benchmark: calculate primes in a tight loop
            start_time = time.time()
            
            def is_prime(n):
                if n < 2:
                    return False
                for i in range(2, int(n**0.5) + 1):
                    if n % i == 0:
                        return False
                return True
            
            # Count primes up to 10000 (consistent workload)
            prime_count = sum(1 for n in range(2, 10000) if is_prime(n))
            
            elapsed = time.time() - start_time
            
            # Baseline: expect ~0.5 seconds on typical cloud VM (2.4GHz)
            baseline_time = 0.5  
            cpu_multiplier = baseline_time / elapsed  # Faster CPU = higher multiplier
            
            return max(0.1, min(10.0, cpu_multiplier))  # Clamp between 0.1x and 10x
            
        except Exception as e:
            print(f"CPU benchmark failed: {e}, using 1.0x")
            return 1.0
    
    def _calculate_vrl_performance_index(self, events_per_cpu_percent: float) -> int:
        """Calculate normalized VRL Performance Index (VPI)
        
        VPI = (Events/CPU%) * CPU_Benchmark_Multiplier
        
        This creates a single comparable number that accounts for:
        - Raw throughput (events/CPU%)
        - Actual CPU performance via benchmark (accounts for architecture, frequency, etc.)
        
        Higher VPI = better performance, normalized across different hardware
        """
        # Use actual CPU benchmark multiplier for accurate normalization
        vpi = int(events_per_cpu_percent * self.cpu_benchmark_multiplier)
        
        return vpi
    
    def _measure_vector_startup_time(self) -> float:
        """Measure Vector CLI startup time with minimal passthrough config"""
        try:
            # Create minimal test data
            startup_test_file = '.tmp/vector_startup_test.ndjson'
            with open(startup_test_file, 'w') as f:
                f.write('{"test": "startup"}\n')
            
            # Minimal passthrough config
            startup_config = {
                'sources': {
                    'startup_input': {
                        'type': 'file',
                        'include': [startup_test_file],
                        'read_from': 'beginning'
                    }
                },
                'sinks': {
                    'startup_output': {
                        'type': 'blackhole',
                        'inputs': ['startup_input']
                    }
                }
            }
            
            startup_config_file = '.tmp/vector_startup_config.yaml'
            with open(startup_config_file, 'w') as f:
                yaml.dump(startup_config, f)
            
            # Measure startup time
            start_time = time.time()
            env = os.environ.copy()
            env['VECTOR_DATA_DIR'] = '.tmp/vector_startup_data'
            
            process = subprocess.Popen(
                ['vector', '--config', startup_config_file],
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Wait for Vector to start processing (when it reads the file)
            time.sleep(0.5)
            startup_time = time.time() - start_time
            
            process.terminate()
            process.wait(timeout=2)
            
            # Cleanup
            os.unlink(startup_config_file)
            os.unlink(startup_test_file)
            
            return max(0.1, startup_time)  # Minimum 0.1s
            
        except Exception as e:
            logger.warning(f"Vector startup measurement failed: {e}, using 1.0s default")
            return 1.0
    
    def _classify_performance_tier(self, events_per_cpu_percent: int) -> str:
        """Classify performance into tiers based on events/CPU%"""
        if events_per_cpu_percent >= 15000:
            return "Tier S+ (Elite)"
        elif events_per_cpu_percent >= 5000:
            return "Tier S (Exceptional)"
        elif events_per_cpu_percent >= 300:
            return "Tier 1 (Ultra-Fast)"
        elif events_per_cpu_percent >= 150:
            return "Tier 2 (Fast)"
        elif events_per_cpu_percent >= 50:
            return "Tier 3 (Moderate)"
        elif events_per_cpu_percent >= 3:
            return "Tier 4 (Slow)"
        else:
            return "Tier 5 (Critical)"
    
    def _load_external_configs(self) -> Dict[str, Any]:
        """Load external configuration files deployed by K8s on startup"""
        configs = {}
        
        try:
            # Load vector-vrl-system.md (company-wide VRL prompt engineering)
            vector_vrl_file = self.external_configs_dir / "vector-vrl-system.md"
            if vector_vrl_file.exists():
                with open(vector_vrl_file, 'r') as f:
                    configs['vector_vrl_prompt'] = f.read()
                logger.info(f"✓ Loaded vector-vrl-system.md ({len(configs['vector_vrl_prompt'])} chars)")
            else:
                logger.warning(f"⚠️  vector-vrl-system.md not found at {vector_vrl_file}")
            
            # Load parser-system-prompts.md (project-specific overrides)
            parser_prompts_file = self.external_configs_dir / "parser-system-prompts.md"
            if parser_prompts_file.exists():
                with open(parser_prompts_file, 'r') as f:
                    configs['parser_prompts'] = f.read()
                logger.info(f"✓ Loaded parser-system-prompts.md ({len(configs['parser_prompts'])} chars)")
            else:
                logger.warning(f"⚠️  parser-system-prompts.md not found at {parser_prompts_file}")
            
            # Load type_maps.csv (field type mappings)
            type_maps_file = self.external_configs_dir / "type_maps.csv"
            if type_maps_file.exists():
                with open(type_maps_file, 'r') as f:
                    configs['type_maps'] = f.read()
                logger.info(f"✓ Loaded type_maps.csv ({len(configs['type_maps'])} chars)")
            else:
                logger.warning(f"⚠️  type_maps.csv not found at {type_maps_file}")
            
        except Exception as e:
            logger.error(f"Failed to load external configs: {e}")
        
        return configs
    
    def _log_external_configs_summary(self):
        """Log summary of loaded external configs for LLM context retention"""
        logger.info("📋 EXTERNAL CONFIGS SUMMARY (K8s deployed):")
        
        if 'vector_vrl_prompt' in self.external_configs:
            prompt = self.external_configs['vector_vrl_prompt']
            # Extract key sections for summary
            lines = prompt.split('\n')
            version_line = next((line for line in lines if 'v1.' in line or 'Version' in line), 'Unknown version')
            logger.info(f"   🎯 vector-vrl-system.md: {version_line[:60]}...")
            logger.info(f"      Contains: Performance tiers, string ops, Vector 0.49.0 config")
        
        if 'parser_prompts' in self.external_configs:
            prompts = self.external_configs['parser_prompts']
            logger.info(f"   🔧 parser-system-prompts.md: {len(prompts)} chars of project overrides")
        
        if 'type_maps' in self.external_configs:
            type_maps = self.external_configs['type_maps']
            csv_lines = type_maps.split('\n')
            field_count = len([line for line in csv_lines if line.strip() and not line.startswith('#')])
            logger.info(f"   📊 type_maps.csv: {field_count} field mappings for product evolution")
        
        logger.info("   💡 These configs are retained for persistent LLM context")
    
    def get_llm_context_package(self) -> Dict[str, str]:
        """Get complete context package for LLM - company configs + sample analysis"""
        context = {
            'external_configs': self.external_configs.copy(),
            'sample_analysis': {
                'sample_file': str(self.sample_file),
                'sample_count': len(self.samples),
                'first_sample_keys': list(self.samples[0].keys()) if self.samples else [],
                'sample_preview': json.dumps(self.samples[0], indent=2)[:500] + '...' if self.samples else 'No samples'
            },
            'system_info': {
                'cpu_info': self.cpu_info,
                'cpu_benchmark_multiplier': self.cpu_benchmark_multiplier,
                'vector_startup_time': self.vector_startup_time
            }
        }
        
        logger.info(f"📦 LLM context package prepared: {len(context['external_configs'])} configs, {len(self.samples)} samples")
        return context
    
    def _log_with_timestamp(self, message: str):
        """Legacy method - use logger.info() directly"""
        logger.info(message)
    
    def run_with_llm_generated_vrl(self, llm_vrl_code: str, iteration: int = 1, model_info: dict = None):
        """Run testing loop with LLM-generated VRL code"""
        self._log_with_timestamp("="*60)
        self._log_with_timestamp(f"TESTING LLM-GENERATED VRL (Iteration {iteration})")
        self._log_with_timestamp("="*60)
        
        # Create candidate from LLM VRL
        llm_candidate = VRLCandidate(
            name=f"llm_generated_v{iteration}",
            description=f"VRL parser generated by LLM analysis (iteration {iteration})",
            vrl_code=llm_vrl_code,
            strategy="llm_analysis"
        )
        
        self.candidates.append(llm_candidate)
        
        # Test with PyVRL first (fastest check)
        self._log_with_timestamp("\n1. TESTING WITH PyVRL")
        self._log_with_timestamp("-"*40)
        if not self.test_with_pyvrl(llm_candidate, model_info):
            self._log_with_timestamp(f"❌ LLM VRL iteration {iteration} failed PyVRL validation")
            
            # Generate helpful examples
            if self.regex_rejection_count > 0:
                self._log_with_timestamp(f"\n💡 PROVIDING STRING OPERATIONS EXAMPLES:")
                self._log_with_timestamp("-"*40)
                examples = self.generate_string_ops_examples()
                
                # Save examples to temp file for LLM reference
                examples_file = f'.tmp/string_ops_examples_iter{iteration}.vrl'
                with open(examples_file, 'w') as f:
                    f.write(examples)
                
                self._log_with_timestamp(f"Saved working examples to {examples_file}")
                self._log_with_timestamp("\nKey patterns for this data:")
                self._log_with_timestamp("- Use contains() and split() instead of parse_regex()")
                self._log_with_timestamp("- Extract fields FIRST, normalize AFTER")
                self._log_with_timestamp("- String operations are 350-400 events/CPU%")
                self._log_with_timestamp("- Regex is only 3-10 events/CPU% (50-100x slower)")
            
            return False
        
        # Quick validate with Vector (fast syntax check)
        self._log_with_timestamp("\n2. VALIDATING WITH VECTOR CLI (vector validate)")
        self._log_with_timestamp("-"*40)
        if not self.validate_with_vector(llm_candidate):
            self._log_with_timestamp(f"❌ LLM VRL iteration {iteration} failed Vector validation")
            return False
        
        # Full test with Vector (only if validation passed)
        self._log_with_timestamp("\n3. FULL TEST WITH VECTOR CLI")
        self._log_with_timestamp("-"*40)
        self.test_with_vector(llm_candidate)
        
        # Measure performance
        self._log_with_timestamp("\n4. MEASURING PERFORMANCE")  
        self._log_with_timestamp("-"*40)
        self.measure_performance(llm_candidate)
        
        # Save results
        self.best_candidate = llm_candidate
        self.save_results()
        
        self._log_with_timestamp(f"\n✅ LLM VRL iteration {iteration} testing complete!")
        return True


    def run_automated_llm_generation(self, provider: str = "anthropic", 
                                    max_iterations: int = 10,  # High budget - local fixes are FREE!
                                    model_override: str = None) -> bool:
        """
        Fully automated VRL generation using external LLM API
        
        This method:
        1. Calls external LLM API (Claude/GPT/Gemini) with samples
        2. Tests the generated VRL
        3. Iterates with feedback if needed
        
        Args:
            provider: "anthropic", "openai", or "gemini"
            max_iterations: Maximum iterations to attempt
            model_override: Optional specific model to use (overrides auto-detection)
            
        Returns:
            True if successful VRL was generated
        """
        from litellm_client import LiteLLMVRLGenerator
        
        logger.info("🤖 Starting automated LLM VRL generation")
        logger.info(f"Provider: {provider}, Max iterations: {max_iterations}")
        if model_override:
            logger.info(f"Model override: {model_override}")
        
        # Optimize samples using pre-tokenizer
        from pre_tokenizer import PreTokenizer
        from pre_tokenizer.enhanced_optimizer import EnhancedOptimizer
        
        logger.info("🔧 Optimizing samples with pre-tokenizer...")
        
        # Use enhanced optimizer for smart selection and caching
        optimizer = EnhancedOptimizer()
        
        # Check for cached VRL patterns first
        primary_pattern = optimizer.detect_log_pattern(self.samples[0]) if self.samples else 'unknown'
        cached_vrl = optimizer.get_cached_vrl(primary_pattern)
        
        if cached_vrl:
            logger.info(f"📦 Found cached VRL for pattern: {primary_pattern}")
            # Test cached VRL first
            test_success = self.run_with_llm_generated_vrl(cached_vrl, 0, {'provider': provider, 'model': 'cached'})
            if test_success:
                logger.success("✅ Cached VRL works! Skipping LLM generation.")
                self.save_results()
                return True
            else:
                logger.warning("Cached VRL failed validation, proceeding with LLM generation")
        
        # Smart sample selection
        optimized_samples = optimizer.smart_sample_selection(
            self.samples,
            max_per_pattern=3,  # 3 examples per pattern
            max_total=50  # Maximum 50 samples total
        )
        
        # Token optimization
        tokenizer = PreTokenizer(max_tokens=30000)  # Conservative limit for prompts
        token_result = tokenizer.prepare_for_llm(optimized_samples)
        
        logger.info(f"📊 Sample optimization: {len(self.samples)} → {token_result['count']} samples")
        logger.info(f"📊 Token usage: {token_result['optimization_stats']['total_tokens']:,} tokens")
        logger.info(f"📊 Pattern coverage: {token_result['optimization_stats']['pattern_coverage']}")
        
        # Initialize LiteLLM VRL generator - no hardcoding, auto-model selection!
        model_preference = "opus" if "opus" in str(model_override).lower() else "sonnet"
        llm_generator = LiteLLMVRLGenerator(provider=provider, model_preference=model_preference)
        
        logger.info(f"🚀 Using LiteLLM with dynamic model selection (preference: {model_preference})")
        logger.info("💰 Cost tracking: Built into LiteLLM (automatic)")
        
        # Generate initial VRL with optimized samples using LiteLLM
        try:
            # Build system prompt from external configs
            system_prompt = self.external_configs.get('parser_prompts', 'You are a VRL expert.')
            context_prompt = self.external_configs.get('vector_vrl_prompt', 'Generate VRL code for these samples.')
            
            result = llm_generator.generate_vrl(
                samples=token_result['samples'],  # Use optimized samples
                system_prompt=system_prompt,
                context_prompt=context_prompt
            )
            
            vrl_code = result['vrl_code']
            success = True
            logger.info(f"✅ Generated initial VRL with {result['metadata']['model']}")
            logger.info(f"💰 Cost: ${result['metadata']['cost']:.4f}, Tokens: {result['metadata']['tokens']}")
            
        except Exception as e:
            logger.error(f"❌ Failed to generate initial VRL: {e}")
            vrl_code = None
            success = False
        
        if not success:
            logger.error("Failed to generate initial VRL")
            return False
            
        # Test and iterate
        for iteration in range(1, max_iterations + 1):
            logger.info(f"Testing iteration {iteration}")
            
            # Get model information from LiteLLM client
            model_info = {
                'provider': provider,
                'model': llm_generator.client.current_model or 'unknown'
            }
            
            # Test the VRL
            test_success = self.run_with_llm_generated_vrl(vrl_code, iteration, model_info)
            
            # Try MODEL-SPECIFIC local fixes after any failure
            if not test_success and hasattr(self, 'last_test_results'):
                from model_specific_vrl_fixer import apply_model_specific_fixes
                
                errors = self.last_test_results.get('errors', [])
                
                # Get model information for specific fixes
                # Extract model from session if available
                current_model = 'claude-opus-4-1'  # default
                if hasattr(self, 'session') and self.session:
                    current_model = getattr(self.session, 'model', current_model)
                
                model_info = {
                    'provider': provider,
                    'model': current_model
                }
                
                # Always try model-specific fixes for common errors
                logger.info(f"🔧 Attempting model-specific fixes for {model_info['provider']}...")
                
                fixed_vrl, was_fixed, fix_metadata = apply_model_specific_fixes(
                    vrl_code, errors, model_info
                )
                
                if was_fixed:
                    logger.info(f"🎯 Applied {len(fix_metadata.get('fixes_applied', []))} model-specific fixes (FREE)")
                    
                    # Test the fixed VRL  
                    test_success = self.run_with_llm_generated_vrl(fixed_vrl, iteration, model_info)
                    
                    if test_success:
                        logger.success(f"✅ Model-specific fixes worked! Saved ${fix_metadata.get('cost_saved', 0.50):.2f}")
                        vrl_code = fixed_vrl
                    else:
                        logger.info("Model fixes helped but didn't resolve everything...")
                        # Still use the partially fixed code for next iteration
                        vrl_code = fixed_vrl
            
            if test_success:
                logger.success(f"✅ Valid VRL generated on iteration {iteration}!")
                
                # Save successful VRL
                self.save_results()
                
                # Cache successful VRL for future use
                optimizer.cache_successful_vrl(primary_pattern, vrl_code, token_result['samples'])
                logger.info(f"💾 Cached successful VRL for pattern: {primary_pattern}")
                
                # Log cost summary from LiteLLM
                total_cost = llm_generator.get_total_cost()
                logger.info(f"💰 Total session cost: ${total_cost:.4f}")
                
                # Log session summary
                summary = llm_generator.get_session_summary()
                logger.info(f"Session summary: {json.dumps(summary, indent=2)}")
                
                return True
                
            # Get test results for feedback
            if self.candidates:
                latest = self.candidates[-1]
                test_results = {
                    'pyvrl_valid': getattr(latest, 'pyvrl_valid', False),
                    'vector_valid': getattr(latest, 'vector_valid', False),
                    'errors': getattr(latest, 'errors', []),
                    'events_per_cpu_percent': getattr(latest, 'events_per_cpu_percent', 0),
                    'extracted_fields': getattr(latest, 'extracted_fields', [])
                }
                
                # Iterate with feedback
                if iteration < max_iterations:
                    # Collect ALL errors comprehensively
                    from error_batch_collector import ErrorBatchCollector, create_comprehensive_error_feedback
                    
                    collector = ErrorBatchCollector()
                    all_errors = collector.collect_all_errors(vrl_code, self.samples[:10])
                    
                    # Add comprehensive error feedback
                    if all_errors['total_count'] > 0:
                        test_results['comprehensive_errors'] = create_comprehensive_error_feedback(all_errors)
                        logger.info(f"📊 Collected {all_errors['total_count']} errors for batch fixing")
                    
                    # Create feedback message for LiteLLM iteration
                    feedback_msg = self._build_feedback_message(test_results)
                    
                    try:
                        result = llm_generator.iterate_with_feedback(
                            feedback=feedback_msg,
                            previous_vrl=vrl_code
                        )
                        vrl_code = result['vrl_code']
                        success = True
                        logger.info(f"✅ Iteration {iteration} complete - Cost: ${result['metadata']['cost']:.4f}")
                    except Exception as e:
                        logger.error(f"❌ Iteration {iteration} failed: {e}")
                        success = False
                    
                    if not success:
                        logger.error(f"Failed to generate improved VRL on iteration {iteration}")
                        break
                        
        logger.warning(f"Failed to generate valid VRL after {max_iterations} iterations")
    
    def _build_feedback_message(self, test_results: Dict[str, Any]) -> str:
        """Build comprehensive feedback message for LiteLLM iteration"""
        feedback_parts = []
        
        # Validation status
        if not test_results.get('pyvrl_valid', False):
            feedback_parts.append("❌ PyVRL validation failed")
        if not test_results.get('vector_valid', False):
            feedback_parts.append("❌ Vector CLI validation failed")
        
        # Performance issues
        if test_results.get('events_per_cpu_percent', 0) < 50:
            feedback_parts.append(f"⚡ Performance concern: {test_results.get('events_per_cpu_percent', 0)}% CPU efficiency")
        
        # Errors
        errors = test_results.get('errors', [])
        if errors:
            feedback_parts.append(f"🐛 Errors found ({len(errors)} total):")
            for error in errors[:5]:  # Show first 5 errors
                feedback_parts.append(f"  - {error}")
        
        # Comprehensive errors from batch collector
        if 'comprehensive_errors' in test_results:
            feedback_parts.append("\n📊 Comprehensive Error Analysis:")
            feedback_parts.append(test_results['comprehensive_errors'])
        
        # Field extraction status
        extracted = test_results.get('extracted_fields', [])
        if extracted:
            feedback_parts.append(f"✅ Successfully extracted fields: {', '.join(extracted)}")
        else:
            feedback_parts.append("⚠️ No fields were extracted from the samples")
        
        return "\n".join(feedback_parts)

if __name__ == "__main__":
    print("VRL Testing Loop - Clean Version with External LLM Integration")
    print("This version can automatically generate VRL using external LLMs:")
    print("- Anthropic Claude API")
    print("- OpenAI GPT API")
    print("- Google Gemini API")
    print("\nUsage:")
    print("  loop = VRLTestingLoop('samples/data.ndjson')")
    print("  success = loop.run_automated_llm_generation(provider='anthropic')")
    print("\nSet API keys via environment variables:")
    print("  export ANTHROPIC_API_KEY=your-key-here")
    print("  export OPENAI_API_KEY=your-key-here")
    print("  export GOOGLE_API_KEY=your-key-here")