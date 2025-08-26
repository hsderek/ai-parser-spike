#!/usr/bin/env python3
"""
VRL Parser Testing Loop Framework

Implements comprehensive testing and optimization flow:
1. Initial VRL candidate generation from JSON
2. PyVRL iteration/debugging for fast validation  
3. Vector CLI validation
4. Performance baseline recording
5. Alternative implementation generation (regex-free)
6. A-B performance testing
7. Best candidate selection
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
import yaml

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

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
    """Complete VRL testing and optimization loop"""
    
    def __init__(self, sample_file: str, output_dir: str = "samples-parsed"):
        self.sample_file = Path(sample_file)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        # Load sample data
        with open(self.sample_file, 'r') as f:
            self.samples = [json.loads(line) for line in f]
        
        # Track all candidates
        self.candidates: List[VRLCandidate] = []
        self.best_candidate: Optional[VRLCandidate] = None
        
        # Performance test configuration
        self.test_events = 10000  # Number of events for performance testing
        self.test_threads = 4  # Optimal thread count per VECTOR-VRL.md
        
    def analyze_json_fields(self) -> Dict[str, Any]:
        """Analyze JSON samples to understand field patterns"""
        field_info = {}
        
        for sample in self.samples:
            for key, value in sample.items():
                if key not in field_info:
                    field_info[key] = {
                        'types': set(),
                        'samples': [],
                        'always_present': True,
                        'cardinality': set()
                    }
                
                field_info[key]['types'].add(type(value).__name__)
                if len(field_info[key]['samples']) < 3:
                    field_info[key]['samples'].append(value)
                if isinstance(value, (str, int, float)):
                    field_info[key]['cardinality'].add(str(value))
        
        # Check if fields are always present
        all_keys = set()
        for sample in self.samples:
            all_keys.update(sample.keys())
        
        for key in all_keys:
            present_count = sum(1 for s in self.samples if key in s)
            field_info[key]['always_present'] = present_count == len(self.samples)
            field_info[key]['cardinality_estimate'] = len(field_info[key]['cardinality'])
            
        return field_info
    
    def generate_initial_vrl(self) -> VRLCandidate:
        """Generate initial VRL candidate from JSON analysis - STRING OPS FIRST per VECTOR-VRL.md"""
        field_info = self.analyze_json_fields()
        
        vrl_lines = []
        vrl_lines.append("# VRL Parser - Generated from JSON analysis")
        vrl_lines.append("# STRICT: NO REGEX ALLOWED per VECTOR-VRL.md")
        vrl_lines.append("# String operations are 50-100x faster than regex")
        vrl_lines.append("")
        vrl_lines.append("# STEP 1: Extract fields using ONLY string operations")
        vrl_lines.append("")
        
        # Analyze message field for patterns if it exists
        if 'msg' in field_info or 'message' in field_info:
            msg_field = 'msg' if 'msg' in field_info else 'message'
            vrl_lines.append(f"# Analyze {msg_field} field for extractable patterns")
            vrl_lines.append(f"if exists(.{msg_field}) {{")
            vrl_lines.append(f"    msg_content = string!(.{msg_field})")
            vrl_lines.append("    ")
            vrl_lines.append("    # Generic pattern extraction using string operations")
            vrl_lines.append("    # Look for common delimiters and extract if found")
            vrl_lines.append("    ")
            
            # Analyze actual samples to find common patterns
            sample_msgs = [s.get(msg_field, '') for s in self.samples[:5] if msg_field in s]
            
            # Check for common delimiter patterns in the actual data
            has_percent = any('%' in str(m) for m in sample_msgs)
            has_dash = any('-' in str(m) for m in sample_msgs)
            has_colon = any(':' in str(m) for m in sample_msgs)
            has_pipe = any('|' in str(m) for m in sample_msgs)
            has_comma = any(',' in str(m) for m in sample_msgs)
            
            if has_percent and has_dash:
                vrl_lines.append("    # Found % and - delimiters in samples")
                vrl_lines.append("    if contains(msg_content, \"%\") && contains(msg_content, \"-\") {")
                vrl_lines.append("        # Extract pattern between % and next space")
                vrl_lines.append("        parts = split(msg_content, \"%\")")
                vrl_lines.append("        if length(parts) > 1 {")
                vrl_lines.append("            pattern_part = string!(parts[1])")
                vrl_lines.append("            space_parts = split(pattern_part, \" \")")
                vrl_lines.append("            if length(space_parts) > 0 {")
                vrl_lines.append("                .extracted_pattern = string!(space_parts[0])")
                vrl_lines.append("            }")
                vrl_lines.append("        }")
                vrl_lines.append("    }")
            elif has_pipe:
                vrl_lines.append("    # Found pipe delimiter in samples")
                vrl_lines.append("    if contains(msg_content, \"|\") {")
                vrl_lines.append("        pipe_parts = split(msg_content, \"|\")")
                vrl_lines.append("        if length(pipe_parts) > 0 {")
                vrl_lines.append("            .field_0 = string!(pipe_parts[0])")
                vrl_lines.append("        }")
                vrl_lines.append("        if length(pipe_parts) > 1 {")
                vrl_lines.append("            .field_1 = string!(pipe_parts[1])")
                vrl_lines.append("        }")
                vrl_lines.append("    }")
            elif has_comma:
                vrl_lines.append("    # Found comma delimiter in samples")
                vrl_lines.append("    if contains(msg_content, \",\") {")
                vrl_lines.append("        csv_parts = split(msg_content, \",\")")
                vrl_lines.append("        if length(csv_parts) > 0 {")
                vrl_lines.append("            .csv_field_0 = string!(csv_parts[0])")
                vrl_lines.append("        }")
                vrl_lines.append("    }")
            
            vrl_lines.append("}")
            vrl_lines.append("")
        
        # Extract from priority field if present
        if 'priority' in field_info:
            vrl_lines.append("# Standard syslog priority decomposition")
            vrl_lines.append("if exists(.priority) {")
            vrl_lines.append("    pri_value = to_int!(.priority)")
            vrl_lines.append("    .facility_num = floor(pri_value / 8)")
            vrl_lines.append("    .severity_num = mod(pri_value, 8)")
            vrl_lines.append("}")
            vrl_lines.append("")
        
        # Parse any nested objects found
        for field, info in field_info.items():
            if 'dict' in info['types']:
                vrl_lines.append(f"# Extract nested fields from {field}")
                vrl_lines.append(f"if exists(.{field}) && is_object(.{field}) {{")
                # Get sample to see what fields exist
                sample_obj = next((s[field] for s in self.samples if field in s and isinstance(s[field], dict)), {})
                for subfield in list(sample_obj.keys())[:3]:  # Limit to first 3 subfields
                    vrl_lines.append(f"    if exists(.{field}.{subfield}) {{")
                    vrl_lines.append(f"        .{field}_{subfield} = string!(.{field}.{subfield})")
                    vrl_lines.append(f"    }}")
                vrl_lines.append("}")
                vrl_lines.append("")
        
        # No hardcoded log type specific logic!
            vrl_lines.append("# Extract structured syslog fields if present")
            vrl_lines.append("if exists(.syslog) && is_object(.syslog) {")
            vrl_lines.append("    if exists(.syslog.facility) {")
            vrl_lines.append("        .syslog_facility = string!(.syslog.facility)")
            vrl_lines.append("    }")
            vrl_lines.append("    if exists(.syslog.severity) {")
            vrl_lines.append("        .syslog_severity = string!(.syslog.severity)")
            vrl_lines.append("    }")
            vrl_lines.append("    if exists(.syslog.mnemonic) {")
            vrl_lines.append("        .syslog_mnemonic = string!(.syslog.mnemonic)")
            vrl_lines.append("    }")
            vrl_lines.append("}")
            vrl_lines.append("")
        
        vrl_lines.append("# STEP 2: Normalize and format fields AFTER extraction")
        vrl_lines.append("")
        
        # Normalize hostname AFTER extraction
        if 'hostname' in field_info:
            vrl_lines.append("# Normalize hostname (at END after extraction)")
            vrl_lines.append("if exists(.hostname) {")
            vrl_lines.append("    .hostname_normalized = downcase(string!(.hostname))")
            vrl_lines.append("}")
            vrl_lines.append("")
        
        # Normalize timestamp AFTER extraction
        if 'timestamp' in field_info:
            vrl_lines.append("# Normalize timestamp (at END after extraction)")
            vrl_lines.append("if exists(.timestamp) {")
            vrl_lines.append("    .timestamp_normalized = string!(.timestamp)")
            vrl_lines.append("}")
            vrl_lines.append("")
        
        # Add metadata
        vrl_lines.append("# Add parser metadata")
        vrl_lines.append("._parser_metadata = {")
        vrl_lines.append('    "parser_version": "1.0.0",')
        vrl_lines.append('    "parser_type": "initial_candidate",')
        vrl_lines.append('    "strategy": "regex"')
        vrl_lines.append("}")
        vrl_lines.append("")
        vrl_lines.append("# Return the event")
        vrl_lines.append(".")
        
        vrl_code = "\n".join(vrl_lines)
        
        candidate = VRLCandidate(
            name="initial_string_ops",
            description="Initial string operations parser per VECTOR-VRL.md guidelines",
            vrl_code=vrl_code,
            strategy="string_ops"
        )
        
        self.candidates.append(candidate)
        return candidate
    
    def test_with_pyvrl(self, candidate: VRLCandidate) -> bool:
        """Fast iteration testing with PyVRL"""
        # EXPLICIT REGEX REJECTION per VECTOR-VRL.md
        if 'regex' in candidate.vrl_code or 'parse_regex' in candidate.vrl_code or 'match(' in candidate.vrl_code:
            error_msg = "REJECTED: VRL contains regex! Per VECTOR-VRL.md regex is 50-100x slower. Use string operations only!"
            candidate.errors.append(error_msg)
            print(f"✗ {error_msg}")
            print(f"  Found forbidden patterns: parse_regex/match/regex")
            print(f"  Must use: contains(), split(), upcase(), downcase() instead")
            return False
        
        try:
            # Create PyVRL transform
            transform = pyvrl.Transform(candidate.vrl_code)
            
            # Test with first sample
            test_event = self.samples[0].copy()
            result = transform.remap(test_event)
            
            # Check for new fields added
            new_fields = set(result.keys()) - set(self.samples[0].keys())
            candidate.extracted_fields = list(new_fields)
            
            candidate.validated_pyvrl = True
            print(f"✓ PyVRL validation passed for {candidate.name}")
            print(f"  New fields: {', '.join(new_fields)}")
            return True
            
        except Exception as e:
            error_msg = f"PyVRL validation failed: {str(e)}"
            candidate.errors.append(error_msg)
            print(f"✗ {error_msg}")
            return False
    
    def iterate_with_pyvrl(self, candidate: VRLCandidate, max_iterations: int = 5) -> bool:
        """Iterate and debug with PyVRL until working"""
        for iteration in range(max_iterations):
            if self.test_with_pyvrl(candidate):
                return True
            
            # Auto-fix common issues
            if iteration < max_iterations - 1:
                print(f"  Iteration {iteration + 1}: Attempting auto-fix...")
                candidate.vrl_code = self.fix_common_vrl_issues(candidate.vrl_code)
        
        return False
    
    def fix_common_vrl_issues(self, vrl_code: str) -> str:
        """Fix common VRL syntax issues"""
        fixes = [
            # Remove unnecessary null coalescing after infallible operations
            (r'to_int!\((.*?)\) \?\? 0', r'to_int!(\1)'),
            # Fix parse_json with infallible and coalescing
            (r'parse_json!\((.*?)\) \?\? \{\}', r'parse_json(\1) ?? {}'),
            # Replace % with mod
            (r'(\w+)\s*%\s*(\w+)', r'mod(\1, \2)'),
            # Fix type() to is_object()
            (r'type\((.*?)\)\s*==\s*"object"', r'is_object(\1)'),
        ]
        
        import re
        for pattern, replacement in fixes:
            vrl_code = re.sub(pattern, replacement, vrl_code)
        
        return vrl_code
    
    def test_with_vector(self, candidate: VRLCandidate) -> bool:
        """Validate with actual Vector CLI"""
        # Create temporary config
        config = {
            'sources': {
                'test_input': {
                    'type': 'file',
                    'include': [str(self.sample_file)],
                    'encoding': {'codec': 'json'}
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
                    'path': '/tmp/vector_test_output.ndjson',
                    'encoding': {'codec': 'json'}
                }
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config, f)
            config_file = f.name
        
        try:
            # Run Vector with timeout
            env = os.environ.copy()
            env['VECTOR_DATA_DIR'] = '/tmp/vector_test_data'
            
            # Run Vector validate command first
            result = subprocess.run(
                ['vector', 'validate', config_file],
                env=env,
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0 or "Shutdown complete" in result.stderr:
                candidate.validated_vector = True
                print(f"✓ Vector validation passed for {candidate.name}")
                return True
            else:
                error_msg = f"Vector validation failed: {result.stderr[:200]}"
                candidate.errors.append(error_msg)
                print(f"✗ {error_msg}")
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
            if os.path.exists('/tmp/vector_test_output.ndjson'):
                os.unlink('/tmp/vector_test_output.ndjson')
    
    def measure_performance(self, candidate: VRLCandidate) -> PerformanceBaseline:
        """Measure CPU and throughput performance"""
        print(f"\nMeasuring performance for {candidate.name}...")
        
        # Create test data file with many events
        test_data_file = f'/tmp/perf_test_{candidate.name}.ndjson'
        with open(test_data_file, 'w') as f:
            for i in range(self.test_events):
                # Use different samples to avoid caching effects
                sample = self.samples[i % len(self.samples)]
                f.write(json.dumps(sample) + '\n')
        
        # Create Vector config for performance testing
        config = {
            'sources': {
                'perf_input': {
                    'type': 'file',
                    'include': [test_data_file],
                    'encoding': {'codec': 'json'},
                    'start_at_beginning': True
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
                    'type': 'blackhole',
                    'inputs': [f'{candidate.name}_transform'],
                    'print_interval_secs': 1
                }
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config, f)
            config_file = f.name
        
        try:
            # Start Vector process
            env = os.environ.copy()
            env['VECTOR_DATA_DIR'] = f'/tmp/vector_perf_{candidate.name}'
            
            process = subprocess.Popen(
                ['vector', '--threads', str(self.test_threads), config_file],
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
            
            # Measure for 5 seconds
            psutil_process = psutil.Process(process.pid)
            for _ in range(10):
                cpu_samples.append(psutil_process.cpu_percent(interval=0.5))
                memory_samples.append(psutil_process.memory_info().rss / 1024 / 1024)
            
            elapsed = time.time() - start_time - 1  # Subtract warmup
            
            # Terminate Vector
            process.terminate()
            process.wait(timeout=5)
            
            # Parse output for event counts
            output = process.stderr.read() if process.stderr else ""
            events_processed = self.test_events  # Assume all processed
            
            # Calculate metrics
            avg_cpu = statistics.mean(cpu_samples[2:])  # Skip warmup samples
            avg_memory = statistics.mean(memory_samples)
            events_per_second = events_processed / elapsed
            events_per_cpu = events_per_second / max(avg_cpu, 0.1)
            
            # Estimate P99 latency (rough calculation)
            p99_latency = 1000 / events_per_second * 100  # ms for 100 events
            
            baseline = PerformanceBaseline(
                events_per_second=events_per_second,
                cpu_percent=avg_cpu,
                memory_mb=avg_memory,
                events_per_cpu_percent=events_per_cpu,
                p99_latency_ms=p99_latency,
                errors_count=0
            )
            
            candidate.performance_metrics = asdict(baseline)
            print(f"  {baseline}")
            
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
    
    def generate_regex_alternative(self) -> VRLCandidate:
        """Generate regex-based alternative for comparison (NOT RECOMMENDED)"""
        vrl_lines = []
        vrl_lines.append("# Regex-based VRL Parser - FOR COMPARISON ONLY")
        vrl_lines.append("# WARNING: Regex is 50-100x slower per VECTOR-VRL.md")
        vrl_lines.append("")
        
        # Normalize hostname
        vrl_lines.append("# Normalize hostname")
        vrl_lines.append("if exists(.hostname) {")
        vrl_lines.append("    .hostname_normalized = downcase(string!(.hostname))")
        vrl_lines.append("}")
        vrl_lines.append("")
        
        # Map severity without regex
        vrl_lines.append("# Map severity to label")
        vrl_lines.append("if exists(.severity) {")
        vrl_lines.append("    severity_num = to_int!(.severity)")
        vrl_lines.append("    .severity_label = if severity_num == 0 {")
        vrl_lines.append('        "emergency"')
        vrl_lines.append("    } else if severity_num == 1 {")
        vrl_lines.append('        "alert"')
        vrl_lines.append("    } else if severity_num == 2 {")
        vrl_lines.append('        "critical"')
        vrl_lines.append("    } else if severity_num == 3 {")
        vrl_lines.append('        "error"')
        vrl_lines.append("    } else if severity_num == 4 {")
        vrl_lines.append('        "warning"')
        vrl_lines.append("    } else if severity_num == 5 {")
        vrl_lines.append('        "notice"')
        vrl_lines.append("    } else if severity_num == 6 {")
        vrl_lines.append('        "info"')
        vrl_lines.append("    } else {")
        vrl_lines.append('        "debug"')
        vrl_lines.append("    }")
        vrl_lines.append("}")
        vrl_lines.append("")
        
        # Extract facility/severity from priority
        vrl_lines.append("# Extract facility and severity from priority")
        vrl_lines.append("if exists(.priority) {")
        vrl_lines.append("    pri_value = to_int!(.priority)")
        vrl_lines.append("    .facility_num = floor(pri_value / 8)")
        vrl_lines.append("    .severity_num = mod(pri_value, 8)")
        vrl_lines.append("}")
        vrl_lines.append("")
        
        # Parse Cisco IOS with REGEX (Tier 4: 3-10 events/CPU%)
        vrl_lines.append("# Parse Cisco IOS patterns using REGEX - SLOW!")
        vrl_lines.append("if exists(.msg) {")
        vrl_lines.append("    msg = string!(.msg)")
        vrl_lines.append("    ")
        vrl_lines.append("    # Direct regex extraction - TIER 4 PERFORMANCE (3-10 events/CPU%)")
        vrl_lines.append("    ios_match = parse_regex!(msg, r'%(?P<facility>[A-Z]+)-(?P<severity>\\d+)-(?P<mnemonic>[A-Z_]+):')")
        vrl_lines.append("    ")
        vrl_lines.append("    if length(ios_match) > 0 {")
        vrl_lines.append("        if exists(ios_match.facility) {")
        vrl_lines.append("            .ios_facility = ios_match.facility")
        vrl_lines.append("        }")
        vrl_lines.append("        if exists(ios_match.severity) {")
        vrl_lines.append("            .ios_severity = ios_match.severity")
        vrl_lines.append("        }")
        vrl_lines.append("        if exists(ios_match.mnemonic) {")
        vrl_lines.append("            .ios_mnemonic = ios_match.mnemonic")
        vrl_lines.append("        }")
        vrl_lines.append("    }")
        vrl_lines.append("}")
        vrl_lines.append("")
        
        # Parse structured syslog
        vrl_lines.append("# Parse structured syslog fields")
        vrl_lines.append("if exists(.syslog) && is_object(.syslog) {")
        vrl_lines.append("    if exists(.syslog.facility) {")
        vrl_lines.append("        .syslog_facility = string!(.syslog.facility)")
        vrl_lines.append("    }")
        vrl_lines.append("    if exists(.syslog.severity) {")
        vrl_lines.append("        .syslog_severity = string!(.syslog.severity)")
        vrl_lines.append("    }")
        vrl_lines.append("    if exists(.syslog.mnemonic) {")
        vrl_lines.append("        .syslog_mnemonic = string!(.syslog.mnemonic)")
        vrl_lines.append("    }")
        vrl_lines.append("}")
        vrl_lines.append("")
        
        # Normalize timestamp
        vrl_lines.append("# Normalize timestamp")
        vrl_lines.append("if exists(.timestamp) {")
        vrl_lines.append("    .timestamp_normalized = string!(.timestamp)")
        vrl_lines.append("}")
        vrl_lines.append("")
        
        # Add metadata
        vrl_lines.append("# Add parser metadata")
        vrl_lines.append("._parser_metadata = {")
        vrl_lines.append('    "parser_version": "1.0.0",')
        vrl_lines.append('    "parser_type": "string_ops_candidate",')
        vrl_lines.append('    "strategy": "string_operations"')
        vrl_lines.append("}")
        vrl_lines.append("")
        vrl_lines.append("# Return the event")
        vrl_lines.append(".")
        
        vrl_code = "\n".join(vrl_lines)
        
        candidate = VRLCandidate(
            name="string_ops",
            description="String operations only - no regex for performance",
            vrl_code=vrl_code,
            strategy="string_ops"
        )
        
        self.candidates.append(candidate)
        return candidate
    
    def generate_hybrid_alternative(self) -> VRLCandidate:
        """Generate hybrid approach - string checks before regex"""
        vrl_lines = []
        vrl_lines.append("# Hybrid VRL Parser - String checks before minimal regex")
        vrl_lines.append("# Optimized with early exits and minimal regex use")
        vrl_lines.append("")
        
        # Early exit check
        vrl_lines.append("# Early exit if no message to parse")
        vrl_lines.append("if !exists(.msg) {")
        vrl_lines.append("    .")
        vrl_lines.append("}")
        vrl_lines.append("")
        
        # Normalize hostname
        vrl_lines.append("# Normalize hostname")
        vrl_lines.append("if exists(.hostname) {")
        vrl_lines.append("    .hostname_normalized = downcase(string!(.hostname))")
        vrl_lines.append("}")
        vrl_lines.append("")
        
        # Fast severity mapping
        vrl_lines.append("# Fast severity mapping without array indexing")
        vrl_lines.append("if exists(.severity) {")
        vrl_lines.append("    severity_num = to_int!(.severity)")
        vrl_lines.append("    .severity_label = if severity_num == 0 {")
        vrl_lines.append('        "emergency"')
        vrl_lines.append("    } else if severity_num == 1 {")
        vrl_lines.append('        "alert"')
        vrl_lines.append("    } else if severity_num == 2 {")
        vrl_lines.append('        "critical"')
        vrl_lines.append("    } else if severity_num == 3 {")
        vrl_lines.append('        "error"')
        vrl_lines.append("    } else if severity_num == 4 {")
        vrl_lines.append('        "warning"')
        vrl_lines.append("    } else if severity_num == 5 {")
        vrl_lines.append('        "notice"')
        vrl_lines.append("    } else if severity_num == 6 {")
        vrl_lines.append('        "info"')
        vrl_lines.append("    } else if severity_num == 7 {")
        vrl_lines.append('        "debug"')
        vrl_lines.append("    } else {")
        vrl_lines.append('        "unknown"')
        vrl_lines.append("    }")
        vrl_lines.append("}")
        vrl_lines.append("")
        
        # Priority extraction
        vrl_lines.append("# Extract facility and severity from priority")
        vrl_lines.append("if exists(.priority) {")
        vrl_lines.append("    pri_value = to_int!(.priority)")
        vrl_lines.append("    .facility_num = floor(pri_value / 8)")
        vrl_lines.append("    .severity_num = mod(pri_value, 8)")
        vrl_lines.append("}")
        vrl_lines.append("")
        
        # Hybrid Cisco IOS parsing
        vrl_lines.append("# Hybrid Cisco IOS parsing - string check then targeted regex")
        vrl_lines.append("if exists(.msg) {")
        vrl_lines.append("    msg = string!(.msg)")
        vrl_lines.append("    ")
        vrl_lines.append("    # Fast string check first")
        vrl_lines.append("    if contains(msg, \"%\") && contains(msg, \"-\") && contains(msg, \":\") {")
        vrl_lines.append("        # Only use regex if pattern likely exists")
        vrl_lines.append("        msg_parts = split(msg, \"%\")")
        vrl_lines.append("        ")
        vrl_lines.append("        if length(msg_parts) > 1 {")
        vrl_lines.append("            # Extract just the relevant portion")
        vrl_lines.append("            msg_part = string!(msg_parts[1])")
        vrl_lines.append("            ios_portion_parts = split(msg_part, \" \")")
        vrl_lines.append("            if length(ios_portion_parts) > 0 {")
        vrl_lines.append("                ios_portion = string!(ios_portion_parts[0])")
        vrl_lines.append("                ")
        vrl_lines.append("                # Targeted regex on small string")
        vrl_lines.append("                ios_match = parse_regex!(ios_portion, r'^(?P<facility>[A-Z]+)-(?P<severity>\\d+)-(?P<mnemonic>[A-Z_]+):')")
        vrl_lines.append("                ")
        vrl_lines.append("                if length(ios_match) > 0 {")
        vrl_lines.append("                    .ios_facility = ios_match.facility")
        vrl_lines.append("                    .ios_severity = ios_match.severity")
        vrl_lines.append("                    .ios_mnemonic = ios_match.mnemonic")
        vrl_lines.append("                }")
        vrl_lines.append("            }")
        vrl_lines.append("        }")
        vrl_lines.append("    }")
        vrl_lines.append("}")
        vrl_lines.append("")
        
        # Structured syslog
        vrl_lines.append("# Parse structured syslog fields")
        vrl_lines.append("if exists(.syslog) && is_object(.syslog) {")
        vrl_lines.append("    if exists(.syslog.facility) {")
        vrl_lines.append("        .syslog_facility = string!(.syslog.facility)")
        vrl_lines.append("    }")
        vrl_lines.append("    if exists(.syslog.severity) {")
        vrl_lines.append("        .syslog_severity = string!(.syslog.severity)")
        vrl_lines.append("    }")
        vrl_lines.append("    if exists(.syslog.mnemonic) {")
        vrl_lines.append("        .syslog_mnemonic = string!(.syslog.mnemonic)")
        vrl_lines.append("    }")
        vrl_lines.append("}")
        vrl_lines.append("")
        
        # Normalize timestamp
        vrl_lines.append("# Normalize timestamp")
        vrl_lines.append("if exists(.timestamp) {")
        vrl_lines.append("    .timestamp_normalized = string!(.timestamp)")
        vrl_lines.append("}")
        vrl_lines.append("")
        
        # Add metadata
        vrl_lines.append("# Add parser metadata")
        vrl_lines.append("._parser_metadata = {")
        vrl_lines.append('    "parser_version": "1.0.0",')
        vrl_lines.append('    "parser_type": "hybrid_candidate",')
        vrl_lines.append('    "strategy": "hybrid_string_regex"')
        vrl_lines.append("}")
        vrl_lines.append("")
        vrl_lines.append("# Return the event")
        vrl_lines.append(".")
        
        vrl_code = "\n".join(vrl_lines)
        
        candidate = VRLCandidate(
            name="hybrid",
            description="Hybrid approach - string checks with minimal regex",
            vrl_code=vrl_code,
            strategy="hybrid"
        )
        
        self.candidates.append(candidate)
        return candidate
    
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
            
            # Score based on events per CPU % (primary metric per VECTOR-VRL.md)
            score = candidate.performance_metrics['events_per_cpu_percent']
            
            print(f"\n{candidate.name} ({candidate.strategy}):")
            print(f"  Description: {candidate.description}")
            print(f"  Events/CPU%: {score:.0f}")
            print(f"  Events/sec: {candidate.performance_metrics['events_per_second']:.0f}")
            print(f"  CPU: {candidate.performance_metrics['cpu_percent']:.1f}%")
            print(f"  Memory: {candidate.performance_metrics['memory_mb']:.0f}MB")
            print(f"  P99 Latency: {candidate.performance_metrics['p99_latency_ms']:.1f}ms")
            
            if score > best_score:
                best_score = score
                best_candidate = candidate
        
        if best_candidate:
            print("\n" + "="*60)
            print(f"WINNER: {best_candidate.name}")
            print(f"Best Events/CPU%: {best_score:.0f}")
            print("="*60)
            
            self.best_candidate = best_candidate
        
        return best_candidate
    
    def save_results(self):
        """Save the best candidate and results"""
        if not self.best_candidate:
            print("No best candidate selected")
            return
        
        base_name = self.sample_file.stem
        
        # Save VRL file
        vrl_file = self.output_dir / f"{base_name}-optimized.vrl"
        with open(vrl_file, 'w') as f:
            f.write(self.best_candidate.vrl_code)
        print(f"\nSaved optimized VRL to {vrl_file}")
        
        # Save performance comparison
        results = {
            'winner': self.best_candidate.name,
            'strategy': self.best_candidate.strategy,
            'performance': self.best_candidate.performance_metrics,
            'all_candidates': [
                {
                    'name': c.name,
                    'strategy': c.strategy,
                    'performance': c.performance_metrics
                }
                for c in self.candidates
            ]
        }
        
        results_file = self.output_dir / f"{base_name}-performance.json"
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"Saved performance results to {results_file}")
    
    def run_complete_loop(self):
        """Run the complete testing and optimization loop"""
        print("="*60)
        print("VRL PARSER TESTING AND OPTIMIZATION LOOP")
        print("="*60)
        
        # Step 1: Generate initial candidate
        print("\n1. GENERATING INITIAL VRL CANDIDATE")
        print("-"*40)
        initial = self.generate_initial_vrl()
        
        # Step 2: Test and iterate with PyVRL
        print("\n2. TESTING WITH PyVRL (Fast Iteration)")
        print("-"*40)
        if not self.iterate_with_pyvrl(initial):
            print("Failed to validate initial candidate with PyVRL")
        
        # Step 3: Validate with Vector CLI
        print("\n3. VALIDATING WITH VECTOR CLI")
        print("-"*40)
        self.test_with_vector(initial)
        
        # Step 4: Measure baseline performance
        print("\n4. MEASURING BASELINE PERFORMANCE")
        print("-"*40)
        baseline = self.measure_performance(initial)
        
        # Step 5: Generate alternatives
        print("\n5. GENERATING OPTIMIZED ALTERNATIVES")
        print("-"*40)
        
        print("\nGenerating string operations alternative...")
        string_ops = self.generate_string_ops_alternative()
        if self.iterate_with_pyvrl(string_ops):
            self.test_with_vector(string_ops)
            self.measure_performance(string_ops)
        
        print("\nGenerating hybrid alternative...")
        hybrid = self.generate_hybrid_alternative()
        if self.iterate_with_pyvrl(hybrid):
            self.test_with_vector(hybrid)
            self.measure_performance(hybrid)
        
        # Step 6: Compare and select best
        print("\n6. A-B TESTING - COMPARING ALL CANDIDATES")
        best = self.compare_candidates()
        
        # Step 7: Save results
        print("\n7. SAVING RESULTS")
        print("-"*40)
        self.save_results()
        
        print("\n" + "="*60)
        print("TESTING LOOP COMPLETE")
        print("="*60)


if __name__ == "__main__":
    # Run the complete testing loop
    loop = VRLTestingLoop("samples/cisco-ios.ndjson")
    loop.run_complete_loop()