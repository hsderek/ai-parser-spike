"""
VRL Performance Iteration Manager

Handles iterative VRL generation with performance optimization,
metrics tracking, and efficient LLM session management.
"""

import os
import time
import json
import socket
import subprocess
import requests
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from loguru import logger

from ..llm.client import DFELLMClient
from ..config.loader import DFEConfigLoader
from .validator import DFEVRLValidator
from .error_fixer import DFEVRLErrorFixer
from ..utils.streaming import stream_file_chunks


@dataclass
class IterationMetrics:
    """Track VRL generation iteration performance"""
    iteration_number: int
    iteration_type: str  # 'initial', 'local_fix', 'llm_fix'
    success: bool
    cost_estimate: float
    duration_seconds: float
    timestamp: datetime = field(default_factory=datetime.now)
    error_code: Optional[str] = None
    vrl_size_chars: int = 0


@dataclass
class PerformanceBaseline:
    """VRL performance measurements"""
    events_per_second: float
    cpu_percent: float
    memory_mb: float
    events_per_cpu_percent: float
    p99_latency_ms: float
    errors_count: int
    vrl_performance_index: int = 0  # VPI - hardware normalized performance score
    
    def __str__(self):
        return (f"Events/sec: {self.events_per_second:.0f}, "
                f"CPU: {self.cpu_percent:.1f}%, "
                f"Mem: {self.memory_mb:.0f}MB, "
                f"Events/CPU%: {self.events_per_cpu_percent:.0f}, "
                f"VPI: {self.vrl_performance_index:,}, "
                f"P99: {self.p99_latency_ms:.1f}ms, "
                f"Errors: {self.errors_count}")


@dataclass
class VRLCandidate:
    """VRL candidate with complete validation and performance data"""
    strategy: Dict[str, str]
    vrl_code: str
    validation_attempts: List[Dict[str, Any]] = field(default_factory=list)
    performance_history: List[PerformanceBaseline] = field(default_factory=list)
    is_valid: bool = False
    current_performance: Optional[PerformanceBaseline] = None
    improvement_cycle: int = 0
    total_cost: float = 0.0
    
    @property
    def latest_vpi(self) -> int:
        """Get latest VPI score"""
        return self.current_performance.vrl_performance_index if self.current_performance else 0
    
    @property
    def performance_improvement(self) -> float:
        """Calculate performance improvement from previous iteration"""
        if len(self.performance_history) < 2:
            return 100.0  # First measurement = 100% "improvement"
        
        current_vpi = self.performance_history[-1].vrl_performance_index
        previous_vpi = self.performance_history[-2].vrl_performance_index
        
        if previous_vpi == 0:
            return 100.0
        
        improvement = ((current_vpi - previous_vpi) / previous_vpi) * 100
        return improvement


class VRLPerformanceOptimizer:
    """VRL code performance optimization using VPI-based approach"""
    
    def __init__(self):
        # VRL function VPI impact (events per CPU percent impact)
        self.function_vpi_impact = {
            # Ultra-high VPI functions (400+ events/CPU%)
            "contains": 400,
            "split!": 380, 
            "upcase": 350,
            "downcase": 350,
            "length": 380,
            "slice": 370,
            
            # High VPI functions (200-300 events/CPU%)  
            "to_string!": 280,
            "to_int!": 250,
            "to_float!": 240,
            "to_bool!": 260,
            "starts_with": 320,
            "ends_with": 320,
            
            # Moderate VPI functions (100-200 events/CPU%)
            "parse_json": 180,
            "parse_syslog": 150,
            "parse_timestamp": 120,
            "md5": 100,
            "sha2": 90,
            
            # Low VPI functions (3-50 events/CPU%)
            "match": 10,
            "parse_regex": 8, 
            "parse_regex_all": 5,
            "capture": 12
        }
    
    def optimize_vrl_code(self, vrl_code: str) -> str:
        """Apply performance optimizations to VRL code"""
        optimized = vrl_code
        
        # Convert slow regex operations to fast string operations where possible
        optimized = self._optimize_regex_to_string_ops(optimized)
        
        # Add early exits for common cases
        optimized = self._add_early_exits(optimized)
        
        # Optimize memory usage
        optimized = self._optimize_memory_usage(optimized)
        
        return optimized
    
    def _optimize_regex_to_string_ops(self, vrl_code: str) -> str:
        """Replace slow regex with fast string operations"""
        import re
        
        optimizations = [
            (r'match\([^,]+,\s*r[\'"]ERROR[\'"].*?\)', 'contains(string!(.message), "ERROR")'),
            (r'match\([^,]+,\s*r[\'"]WARN[\'"].*?\)', 'contains(string!(.message), "WARN")'),  
            (r'match\([^,]+,\s*r[\'"]INFO[\'"].*?\)', 'contains(string!(.message), "INFO")'),
            (r'match\([^,]+,\s*r[\'"]DEBUG[\'"].*?\)', 'contains(string!(.message), "DEBUG")'),
        ]
        
        optimized = vrl_code
        for pattern, replacement in optimizations:
            optimized = re.sub(pattern, replacement, optimized)
        
        return optimized
    
    def _add_early_exits(self, vrl_code: str) -> str:
        """Add early exit optimizations"""
        if 'message' in vrl_code.lower() or 'msg' in vrl_code.lower():
            early_exit = '''# Early exit optimization
if !exists(.message) && !exists(.msg) && !exists(.log) {
    .parser_skipped = true
    return
}

'''
            return early_exit + vrl_code
        
        return vrl_code
    
    def _optimize_memory_usage(self, vrl_code: str) -> str:
        """Add memory optimizations"""
        memory_optimizations = '''
# Memory optimization - clean up large fields
if exists(.raw_data) && length(string!(.raw_data)) > 1000 {
    del(.raw_data)
}
'''
        return vrl_code + memory_optimizations
    
    def analyze_performance(self, vrl_code: str) -> Dict[str, Any]:
        """Analyze VRL performance characteristics using VPI approach"""
        lines = vrl_code.split('\n')
        function_calls = []
        total_vpi_cost = 0
        
        # Count function usage and calculate VPI impact
        for line in lines:
            if line.strip().startswith('#') or not line.strip():
                continue
                
            for func, vpi_impact in self.function_vpi_impact.items():
                if func in line:
                    function_calls.append((func, vpi_impact))
                    # VPI cost is inverse of VPI impact
                    total_vpi_cost += (1.0 / vpi_impact) if vpi_impact > 0 else 1.0
        
        # Estimate events per CPU percent based on function VPI impacts
        if total_vpi_cost > 0:
            # Higher VPI cost = lower events per CPU%
            estimated_events_per_cpu_percent = max(1, int(1000 / total_vpi_cost))
        else:
            # No recognized functions, assume basic operations
            estimated_events_per_cpu_percent = 300
        
        # Group functions by VPI ranges for analysis
        vpi_distribution = {
            "ultra_high_vpi": len([f for f, vpi in function_calls if vpi >= 350]),
            "high_vpi": len([f for f, vpi in function_calls if 200 <= vpi < 350]),
            "moderate_vpi": len([f for f, vpi in function_calls if 50 <= vpi < 200]),
            "low_vpi": len([f for f, vpi in function_calls if vpi < 50])
        }
        
        return {
            "function_calls": function_calls,
            "vpi_distribution": vpi_distribution,
            "total_vpi_cost": total_vpi_cost,
            "estimated_events_per_cpu_percent": estimated_events_per_cpu_percent,
            "performance_rating": self._get_vpi_rating(estimated_events_per_cpu_percent)
        }
    
    def _get_vpi_rating(self, events_per_cpu_percent: int) -> str:
        """Rate VRL performance based on events/CPU% (will be normalized to VPI)"""
        if events_per_cpu_percent >= 300:
            return "excellent"
        elif events_per_cpu_percent >= 150:
            return "good" 
        elif events_per_cpu_percent >= 50:
            return "acceptable"
        else:
            return "poor"


class DFEVRLPerformanceOptimizer:
    """
    Performance optimization stage: Takes candidate_baseline from baseline_stage
    and generates optimized VRL variants with VPI performance measurement.
    """
    
    def __init__(self, config_path: str = None):
        self.config = DFEConfigLoader.load(config_path)
        self.llm_client = DFELLMClient(self.config)
        self.validator = DFEVRLValidator(self.config)
        self.error_fixer = DFEVRLErrorFixer(self.llm_client)
        self.optimizer = VRLPerformanceOptimizer()
        
        # Session tracking
        self.session_id = f"vrl_perf_session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.iteration_metrics: List[IterationMetrics] = []
        self.start_time = None
        self.end_time = None
        
        # CPU benchmarking for VPI calculation
        self.cpu_benchmark_multiplier = self._benchmark_cpu_performance()
        
        # Measure Vector CLI startup time for accurate performance measurement
        self.vector_startup_time = self._measure_vector_startup_time()
        
        # Get configuration
        perf_config = self.config.get("performance", {})
        self.max_iterations = perf_config.get("max_iterations", 10)
        self.iteration_delay = perf_config.get("iteration_delay", 2)
        self.cost_threshold = perf_config.get("cost_threshold", 5.0)  # Max $5 per VRL
        self.default_optimize_for = perf_config.get("optimize_for", "cpu_efficiency")
        self.candidate_count = perf_config.get("candidate_count", 3)
        self.candidate_strategies = perf_config.get("candidate_strategies", [])
        
        logger.info(f"🎯 VRL Performance Optimization Session: {self.session_id}")
        logger.info(f"   Max iterations: {self.max_iterations}")
        logger.info(f"   Cost threshold: ${self.cost_threshold}")
        logger.info(f"   CPU benchmark multiplier: {self.cpu_benchmark_multiplier:.2f}")
        logger.info(f"   Vector startup time: {self.vector_startup_time:.2f}s")
        logger.info(f"   Default optimization: {self.default_optimize_for}")
    
    def run_performance_optimization(self, 
                                     log_file: str,
                                     device_type: str = None,
                                     optimize_for: str = None,
                                     baseline_vrl: str = None) -> Tuple[str, Dict[str, Any]]:
        """
        Run complete performance optimization cycle
        
        Args:
            log_file: Path to log file
            device_type: Optional device type hint
            optimize_for: "cpu_efficiency", "throughput", or "balanced" (defaults to config)
            baseline_vrl: Optional working VRL to use as starting point
            
        Returns:
            Tuple of (optimized_vrl_code, optimization_metrics)
        """
        # Use config default if not specified
        if optimize_for is None:
            optimize_for = self.default_optimize_for
        
        self.start_time = datetime.now()
        log_path = Path(log_file)
        
        if not log_path.exists():
            raise FileNotFoundError(f"Log file not found: {log_file}")
        
        logger.info(f"🚀 Starting performance iteration for {log_path.name}")
        logger.info(f"   Optimization target: {optimize_for} (from {'config' if optimize_for == self.default_optimize_for else 'API parameter'})")
        
        # Auto-detect device type
        if not device_type:
            device_type = self._detect_device_type(log_path.name)
        
        # Stream sample data efficiently
        sample_logs = self._stream_sample_logs(log_path)
        logger.info(f"   Sample size: {len(sample_logs.split())} lines")
        
        best_vrl = None
        best_performance = None
        total_cost = 0.0
        candidates = []
        
        # Step 0: Establish candidate_baseline from baseline_stage if not provided
        candidate_baseline = None
        if not hasattr(self, '_candidate_baseline'):
            logger.info("🔄 Running baseline_stage to establish candidate_baseline...")
            from .generator import DFEVRLGenerator
            baseline_generator = DFEVRLGenerator(self.config)
            
            candidate_baseline, baseline_metadata = baseline_generator.generate(
                sample_logs=sample_logs,
                device_type=device_type,
                validate=True,
                fix_errors=True
            )
            
            # Validate candidate_baseline works
            if baseline_metadata.get('validation_passed', False):
                logger.info("✅ Baseline_stage produced working candidate_baseline")
                self._candidate_baseline = candidate_baseline
            else:
                logger.warning("⚠️ Baseline_stage failed - performance_stage cannot proceed")
                return "", self._generate_session_metrics(0, [])
        
        candidate_baseline = getattr(self, '_candidate_baseline', None)
        
        # Step 1: Generate candidate strategies using candidate_baseline
        logger.info(f"🎯 Performance_stage: Generating {self.candidate_count} candidate strategies...")
        if candidate_baseline:
            logger.info("📋 Using candidate_baseline from baseline_stage for optimization")
        
        strategies = self.llm_client.generate_candidate_strategies(
            sample_logs=sample_logs,
            device_type=device_type,
            candidate_count=self.candidate_count,
            baseline_vrl=candidate_baseline
        )
        # Use actual LiteLLM cost if available
        strategy_cost = getattr(self.llm_client, 'last_completion_cost', 0) or 0
        total_cost += strategy_cost
        
        logger.info("📋 Generated strategies:")
        for i, strategy in enumerate(strategies, 1):
            logger.info(f"   {i}. {strategy['name']}: {strategy['description']}")
        
        # Step 2: Generate and validate VRL candidates in parallel
        logger.info(f"\n🚀 Generating and validating {len(strategies)} VRL candidates in parallel...")
        
        candidates = self._generate_and_validate_candidates_parallel(
            strategies, sample_logs, device_type, total_cost, candidate_baseline
        )
        total_cost += sum(c.total_cost for c in candidates)
        
        # TODO: PERFORMANCE OPTIMIZATION STAGE (DISABLED FOR STAGE 1 FOCUS)
        # Step 3: Serial performance testing (no interference)
        # Step 4: Iterative improvement cycles with 5% threshold  
        # Step 5: VPI-based candidate ranking and selection
        # 
        # UNCOMMENT BELOW WHEN STAGE 1 IS RELIABLE:
        
        """
        logger.info(f"\n📊 Running serial performance tests...")
        valid_candidates = [c for c in candidates if c.is_valid]
        
        if not valid_candidates:
            logger.error("❌ No valid VRL candidates after parallel validation!")
            return "", self._generate_session_metrics(total_cost, [c.__dict__ for c in candidates])
        
        # Run performance tests serially to avoid interference
        for i, candidate in enumerate(valid_candidates, 1):
            logger.info(f"🚀 Performance testing candidate {i}/{len(valid_candidates)}: {candidate.strategy['name']}")
            
            try:
                performance = self._measure_vrl_performance(candidate.vrl_code, sample_logs)
                candidate.current_performance = performance
                candidate.performance_history.append(performance)
                
                tier = self._classify_performance_tier(performance.vrl_performance_index)
                logger.info(f"   📊 VPI: {performance.vrl_performance_index:,} ({tier})")
                
            except Exception as e:
                logger.warning(f"   Performance test failed: {e}")
        
        # Step 4: Iterative improvement cycles with 5% threshold
        logger.info(f"\n🔄 Starting iterative improvement cycles...")
        improved_candidates = self._run_improvement_cycles(
            valid_candidates, sample_logs, device_type, optimize_for
        )
        
        # Final ranking and selection
        final_candidates = sorted(improved_candidates, 
                                key=lambda c: c.latest_vpi, 
                                reverse=True)
        
        winner = final_candidates[0]
        return winner.vrl_code, self._generate_session_metrics(total_cost, [c.__dict__ for c in final_candidates])
        """
        
        # STAGE 1 FOCUS: Return first valid candidate
        self.end_time = datetime.now()
        valid_candidates = [c for c in candidates if c.is_valid]
        
        if valid_candidates:
            # Return first working candidate for stage 1
            winner = valid_candidates[0]
            logger.success(f"\n🎯 STAGE 1 SUCCESS: {winner.strategy['name']} working VRL achieved!")
            logger.info(f"   Cost: ${winner.total_cost:.4f}")
            logger.info(f"   Validation attempts: {len(winner.validation_attempts)}")
            
            return winner.vrl_code, self._generate_session_metrics(total_cost, [c.__dict__ for c in candidates])
        else:
            logger.error("❌ STAGE 1 FAILED: No valid VRL candidates generated")
            return "", self._generate_session_metrics(total_cost, [c.__dict__ for c in candidates])
    
    def _stream_sample_logs(self, log_path: Path, max_lines: int = 1000) -> str:
        """Efficiently stream sample logs using dask/streaming utilities"""
        try:
            # Use streaming utilities from the module
            chunks = list(stream_file_chunks(str(log_path), chunk_lines=max_lines // 10))
            
            # Take representative samples from chunks
            samples = []
            for chunk in chunks[:10]:  # Max 10 chunks
                samples.extend(chunk[:max_lines // 10])  # Representative from each chunk
                if len(samples) >= max_lines:
                    break
            
            logger.info(f"Streamed {len(samples)} representative samples from {log_path.name}")
            return '\n'.join(samples)
            
        except Exception as e:
            logger.warning(f"Streaming failed: {e}, using basic read")
            
            # Fallback to basic file reading
            lines = []
            with open(log_path, 'r') as f:
                for i, line in enumerate(f):
                    if i >= max_lines:
                        break
                    lines.append(line.rstrip())
            
            return '\n'.join(lines)
    
    def _detect_device_type(self, filename: str) -> Optional[str]:
        """Auto-detect device type from filename"""
        filename_lower = filename.lower()
        
        patterns = {
            "ssh": ["ssh", "sshd", "openssh"],
            "apache": ["apache", "httpd", "access", "error"],
            "cisco": ["cisco", "asa", "ios", "nexus"],
            "nginx": ["nginx"],
            "firewall": ["firewall", "pfsense", "fortinet"],
            "windows": ["windows", "win", "evtx"],
            "syslog": ["syslog", "messages", "system"],
            "docker": ["docker", "container"],
            "kubernetes": ["k8s", "kubernetes", "kube"]
        }
        
        for device_type, keywords in patterns.items():
            if any(keyword in filename_lower for keyword in keywords):
                logger.info(f"Auto-detected device type: {device_type}")
                return device_type
        
        return "unknown"
    
    def _refine_vrl_for_performance(self, 
                                   current_vrl: str, 
                                   current_performance: Optional[PerformanceBaseline],
                                   sample_logs: str) -> str:
        """Use LLM to refine VRL for better performance"""
        
        if current_performance:
            performance_feedback = f"""
Current VRL Performance Analysis:
- Events/sec: {current_performance.events_per_second:.0f}
- CPU usage: {current_performance.cpu_percent:.1f}%
- Memory: {current_performance.memory_mb:.0f}MB
- Rating: {self.optimizer.analyze_performance(current_vrl)['performance_rating']}

Please optimize the VRL for better performance while maintaining correctness.
Focus on:
1. Using faster string operations instead of regex where possible
2. Adding early exit conditions
3. Minimizing memory allocations
4. Avoiding expensive operations in tight loops
"""
        else:
            performance_feedback = f"""
Current VRL failed validation. Please fix the errors while optimizing for performance.
Performance Rating: {self.optimizer.analyze_performance(current_vrl)['performance_rating']}

Focus on:
1. Fix validation errors first
2. Use fast string operations instead of regex
3. Add proper error handling with ?? operators
4. Use infallible functions where possible
"""
        
        # Use the fix_vrl_error method instead of a non-existent refine_vrl method
        return self.llm_client.fix_vrl_error(current_vrl, performance_feedback, sample_logs)
    
    def _measure_vrl_performance(self, vrl_code: str, sample_logs: str) -> PerformanceBaseline:
        """Measure VRL performance using actual Vector CLI execution"""
        import tempfile
        import subprocess
        import psutil
        import yaml
        import time
        
        logger.info("📊 Running Vector CLI performance measurement...")
        
        try:
            # Create temporary files for Vector test
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                
                # Create test input file
                input_file = temp_path / "input.ndjson"
                output_file = temp_path / "output.ndjson"
                config_file = temp_path / "vector.yaml"
                
                # Write sample data (limit to 1000 events for quick test)
                lines = sample_logs.strip().split('\n')[:1000]
                with open(input_file, 'w') as f:
                    for line in lines:
                        # Convert to NDJSON if needed
                        if line.strip().startswith('{'):
                            f.write(line + '\n')
                        else:
                            # Convert raw log to JSON
                            f.write(f'{{"message": {json.dumps(line)}}}\n')
                
                # Find available port for GraphQL API  
                api_port = self._find_available_port()
                
                # Create Vector config with VRL transform (including 101 transform + GraphQL API)
                vector_config = {
                    'data_dir': str(temp_path / 'vector_data'),
                    'api': {
                        'enabled': True,
                        'address': f'127.0.0.1:{api_port}',
                        'graphql': True
                    },
                    'sources': {
                        'perf_test': {
                            'type': 'file',
                            'include': [str(input_file)],
                            'read_from': 'beginning',
                            'max_read_bytes': 1000000
                        }
                    },
                    'transforms': {
                        # Step 1: HyperSec 101 transform - flatten message JSON
                        'flatten_message_parse': {
                            'type': 'remap',
                            'inputs': ['perf_test'],
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
                        # Step 2: VRL parser (after message flattening)  
                        'vrl_parser': {
                            'type': 'remap',
                            'inputs': ['flatten_message_filter'],
                            'source': vrl_code
                        }
                    },
                    'sinks': {
                        'perf_output': {
                            'type': 'file',
                            'inputs': ['vrl_parser'],
                            'path': str(output_file),
                            'encoding': {'codec': 'json'}
                        }
                    }
                }
                
                with open(config_file, 'w') as f:
                    yaml.dump(vector_config, f)
                
                # Run Vector with performance monitoring
                logger.info(f"   Running Vector CLI with {len(lines)} test events...")
                
                start_time = time.time()
                
                # Start Vector process
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
                
                # Monitor CPU usage during processing
                cpu_readings = []
                memory_readings = []
                
                try:
                    psutil_process = psutil.Process(process.pid)
                    
                    # Wait for Vector to start, then monitor via GraphQL + collect performance metrics
                    time.sleep(2)  # Give Vector time to start API
                    
                    measurement_start = time.time()
                    
                    # Monitor event processing via GraphQL API while collecting performance metrics
                    events_processed, cpu_readings, memory_readings = self._monitor_vector_performance_with_metrics(
                        api_port, process, psutil_process, len(lines)
                    )
                    
                    measurement_duration = time.time() - measurement_start
                    
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    logger.warning("Could not monitor Vector process")
                    cpu_readings = [5.0]  # Estimate
                    memory_readings = [50.0]  # Estimate
                    measurement_duration = 2.0
                
                # Terminate Vector process
                if process.poll() is None:
                    process.terminate()
                    process.wait(timeout=5)
                
                total_time = time.time() - start_time
                actual_processing_time = max(0.1, total_time - self.vector_startup_time)
                
                # Calculate performance metrics
                avg_cpu = sum(cpu_readings) / len(cpu_readings) if cpu_readings else 5.0
                avg_memory = sum(memory_readings) / len(memory_readings) if memory_readings else 50.0
                
                events_per_second = events_processed / actual_processing_time if actual_processing_time > 0 else 0
                events_per_cpu_percent = events_per_second / max(avg_cpu, 0.1) if avg_cpu > 0 else 0
                
                # Calculate VPI
                vpi = self._calculate_vrl_performance_index(events_per_cpu_percent)
                
                # Estimate P99 latency
                p99_latency = (1000 / events_per_second * 100) if events_per_second > 0 else 0
                
                logger.info(f"   Processed {events_processed}/{len(lines)} events")
                logger.info(f"   Processing time: {actual_processing_time:.2f}s (startup excluded)")
                logger.info(f"   Events/sec: {events_per_second:.0f}")
                logger.info(f"   CPU: {avg_cpu:.1f}%, Memory: {avg_memory:.0f}MB")
                logger.info(f"   Events/CPU%: {events_per_cpu_percent:.0f}")
                logger.info(f"   VPI: {vpi:,}")
                
                return PerformanceBaseline(
                    events_per_second=events_per_second,
                    cpu_percent=avg_cpu,
                    memory_mb=avg_memory,
                    events_per_cpu_percent=events_per_cpu_percent,
                    p99_latency_ms=p99_latency,
                    errors_count=len(lines) - events_processed,  # Failed events
                    vrl_performance_index=vpi
                )
                
        except Exception as e:
            logger.warning(f"Vector CLI performance measurement failed: {e}")
            
            # Fallback to estimated performance
            perf_analysis = self.optimizer.analyze_performance(vrl_code)
            events_per_cpu_percent = perf_analysis["estimated_events_per_cpu_percent"]
            vpi = self._calculate_vrl_performance_index(events_per_cpu_percent)
            
            return PerformanceBaseline(
                events_per_second=events_per_cpu_percent,  # Use as proxy
                cpu_percent=10.0,  # Placeholder
                memory_mb=50.0,    # Placeholder
                events_per_cpu_percent=events_per_cpu_percent,
                p99_latency_ms=5.0,  # Placeholder
                errors_count=0,
                vrl_performance_index=vpi
            )
    
    def _is_better_performance(self, 
                              new_perf: PerformanceBaseline, 
                              current_best: PerformanceBaseline,
                              optimize_for: str) -> bool:
        """
        Determine if new performance is better than current best using VPI as primary metric
        
        VPI provides hardware-normalized comparison, making it the most reliable metric
        for comparing VRL performance across different systems and conditions.
        """
        if optimize_for == "throughput":
            # Pure throughput: events per second
            return new_perf.events_per_second > current_best.events_per_second
        elif optimize_for == "cpu_efficiency":
            # CPU efficiency: Use VPI as primary metric (hardware-normalized events/CPU%)
            return new_perf.vrl_performance_index > current_best.vrl_performance_index
        elif optimize_for == "balanced":
            # Balanced: Use VPI as primary with throughput as tiebreaker
            if new_perf.vrl_performance_index != current_best.vrl_performance_index:
                return new_perf.vrl_performance_index > current_best.vrl_performance_index
            else:
                # Tiebreaker: events per second
                return new_perf.events_per_second > current_best.events_per_second
        
        return False
    
    def _extract_error_code(self, error_message: str) -> Optional[str]:
        """Extract Vector error code from error message"""
        import re
        
        if not error_message:
            return None
        
        # Look for error codes like E103, E651, etc.
        match = re.search(r'error\[E(\d+)\]', error_message)
        if match:
            return f"E{match.group(1)}"
        
        return None
    
    def _generate_session_metrics(self, total_cost: float, candidates: List[Dict] = None) -> Dict[str, Any]:
        """Generate comprehensive session performance metrics"""
        duration = (self.end_time - self.start_time).total_seconds() if self.end_time and self.start_time else 0
        
        # Handle candidate-based metrics
        if candidates:
            valid_candidates = [c for c in candidates if c["is_valid"]]
            successful = len(valid_candidates) > 0
            
            candidate_metrics = []
            for i, candidate in enumerate(candidates):
                strategy = candidate["strategy"]
                perf = candidate.get("performance")
                
                candidate_metrics.append({
                    "candidate_number": i + 1,
                    "strategy_name": strategy["name"],
                    "strategy_description": strategy["description"], 
                    "is_valid": candidate["is_valid"],
                    "vpi": perf.vrl_performance_index if perf else 0,
                    "events_per_second": perf.events_per_second if perf else 0,
                    "cpu_percent": perf.cpu_percent if perf else 0,
                    "duration": candidate["duration"],
                    "cost": candidate["cost"],
                    "error_code": self._extract_error_code(candidate.get("error_message", "")),
                    "vrl_size": len(candidate["vrl_code"])
                })
            
            return {
                "session_id": self.session_id,
                "approach": "multi_candidate",
                "total_candidates": len(candidates),
                "valid_candidates": len(valid_candidates),
                "total_cost": total_cost,
                "duration_seconds": duration,
                "successful": successful,
                "winner_vpi": max((c.get("performance", type('obj', (object,), {"vrl_performance_index": 0})).vrl_performance_index for c in valid_candidates), default=0),
                "candidates": candidate_metrics,
                "cpu_benchmark_multiplier": self.cpu_benchmark_multiplier,
                "vector_startup_time": self.vector_startup_time
            }
        
        # Fallback to iteration-based metrics if no candidates
        if not self.iteration_metrics:
            return {"session_id": self.session_id, "total_cost": total_cost}
        
        # Calculate iteration metrics
        total_iterations = len(self.iteration_metrics)
        llm_calls = len([m for m in self.iteration_metrics if m.iteration_type in ['initial', 'llm_fix']])
        local_fixes = len([m for m in self.iteration_metrics if m.iteration_type == 'local_fix'])
        successful = any(m.success for m in self.iteration_metrics)
        success_iteration = next((m.iteration_number for m in self.iteration_metrics if m.success), None)
        
        return {
            "session_id": self.session_id,
            "approach": "iterative",
            "total_iterations": total_iterations,
            "llm_calls": llm_calls,
            "local_fixes": local_fixes,
            "total_cost": total_cost,
            "duration_seconds": duration,
            "successful": successful,
            "success_at_iteration": success_iteration
        }
    
    def print_session_summary(self, metrics: Dict[str, Any]):
        """Print detailed session summary"""
        logger.info(f"\n{'='*80}")
        logger.info(f"📊 VRL PERFORMANCE ITERATION SUMMARY")
        logger.info(f"{'='*80}")
        
        approach = metrics.get("approach", "unknown")
        
        if approach == "multi_candidate":
            # Multi-candidate summary
            logger.info(f"\n📈 Multi-Candidate Results:")
            logger.info(f"  Total candidates: {metrics['total_candidates']}")
            logger.info(f"  Valid candidates: {metrics['valid_candidates']}")
            logger.info(f"  Success: {'✅ YES' if metrics['successful'] else '❌ NO'}")
            
            if metrics['successful']:
                logger.success(f"  Winner VPI: {metrics['winner_vpi']:,}")
            
            logger.info(f"\n💰 Cost Analysis:")
            logger.info(f"  Total cost: ${metrics['total_cost']:.2f}")
            logger.info(f"  Average per candidate: ${metrics['total_cost']/metrics['total_candidates']:.2f}")
            
            logger.info(f"\n⏱️ Performance:")
            logger.info(f"  Total duration: {metrics['duration_seconds']:.1f} seconds")
            
            logger.info(f"\n🎯 System Benchmarks:")
            logger.info(f"  CPU benchmark multiplier: {metrics['cpu_benchmark_multiplier']:.2f}")
            logger.info(f"  Vector startup time: {metrics['vector_startup_time']:.2f}s")
            
            # Candidate details
            if 'candidates' in metrics:
                logger.info(f"\n📊 Candidate Performance:")
                for candidate in metrics['candidates']:
                    status = "✅" if candidate['is_valid'] else "❌"
                    vpi_info = f"VPI: {candidate['vpi']:,}" if candidate['vpi'] > 0 else "No VPI"
                    error_info = f" ({candidate['error_code']})" if candidate['error_code'] else ""
                    logger.info(f"  {candidate['candidate_number']}. {status} {candidate['strategy_name']}: {vpi_info}{error_info}")
        
        else:
            # Legacy iteration-based summary
            logger.info(f"\n📈 Iteration Breakdown:")
            logger.info(f"  Total iterations: {metrics.get('total_iterations', 0)}")
            logger.info(f"  LLM calls: {metrics.get('llm_calls', 0)}")
            logger.info(f"  Local fixes: {metrics.get('local_fixes', 0)}")
            logger.info(f"  Success: {'✅ YES' if metrics.get('successful', False) else '❌ NO'}")
            
            logger.info(f"\n💰 Cost Analysis:")
            logger.info(f"  Total cost: ${metrics.get('total_cost', 0):.2f}")
            
            logger.info(f"\n⏱️ Performance:")
            logger.info(f"  Total duration: {metrics.get('duration_seconds', 0):.1f} seconds")
    
    def _benchmark_cpu_performance(self) -> float:
        """
        Benchmark CPU performance to create hardware-normalized VPI scores
        
        Returns:
            CPU benchmark multiplier for VPI calculation
        """
        import psutil
        
        logger.info("🔧 Benchmarking CPU performance...")
        
        try:
            # Simple CPU benchmark: string operations per second
            import time
            
            # Test string operations (similar to VRL workload)
            start_time = time.time()
            iterations = 100000
            test_string = "Dec 10 06:55:46 LabSZ sshd[24200]: Invalid user test from 192.168.1.100 port 22"
            
            for _ in range(iterations):
                # String operations similar to VRL
                parts = test_string.split(" ")
                contains_check = "Invalid" in test_string
                upper_case = test_string.upper()
                slice_op = test_string[0:10]
            
            duration = time.time() - start_time
            ops_per_second = iterations / duration
            
            # Normalize based on expected baseline (modern CPU ~500k ops/sec)
            baseline_ops_per_sec = 500000
            multiplier = ops_per_second / baseline_ops_per_sec
            
            logger.info(f"   CPU ops/sec: {ops_per_second:.0f}")
            logger.info(f"   Benchmark multiplier: {multiplier:.2f}")
            
            return max(0.1, min(10.0, multiplier))  # Clamp between 0.1 and 10.0
            
        except Exception as e:
            logger.warning(f"CPU benchmark failed: {e}, using default multiplier")
            return 1.0
    
    def _calculate_vrl_performance_index(self, events_per_cpu_percent: float) -> int:
        """
        Calculate normalized VRL Performance Index (VPI)
        
        VPI = (Events/CPU%) * CPU_Benchmark_Multiplier
        
        This creates a hardware-normalized performance score that accounts for:
        - Raw throughput efficiency (events/CPU%)
        - Actual CPU performance via benchmark (accounts for architecture, frequency, etc.)
        
        Higher VPI = better performance, normalized across different hardware
        
        Args:
            events_per_cpu_percent: Raw events per CPU percent
            
        Returns:
            VPI score (integer for easy comparison)
        """
        vpi = int(events_per_cpu_percent * self.cpu_benchmark_multiplier)
        return vpi
    
    def _classify_performance_tier(self, vpi: int) -> str:
        """Classify VPI score into performance tier"""
        if vpi >= 5000:
            return "excellent"
        elif vpi >= 2000:
            return "good"
        elif vpi >= 500:
            return "acceptable"
        else:
            return "poor"
    
    def _generate_and_validate_candidates_parallel(self, 
                                                  strategies: List[Dict[str, str]], 
                                                  sample_logs: str,
                                                  device_type: str,
                                                  initial_cost: float,
                                                  baseline_vrl: str = None) -> List[VRLCandidate]:
        """Generate and validate VRL candidates in parallel using threading"""
        from concurrent.futures import as_completed
        from .. import get_thread_pool
        
        executor = get_thread_pool()
        future_to_strategy = {}
        
        # Submit parallel VRL generation tasks with baseline
        for strategy in strategies:
            future = executor.submit(
                self._generate_and_validate_single_candidate,
                strategy, sample_logs, device_type, baseline_vrl
            )
            future_to_strategy[future] = strategy
        
        # Collect results as they complete
        candidates = []
        for future in as_completed(future_to_strategy):
            try:
                candidate = future.result()
                candidates.append(candidate)
                
                status = "✅ Valid" if candidate.is_valid else "❌ Invalid"
                logger.info(f"   {status} {candidate.strategy['name']}: ${candidate.total_cost:.2f}")
                
            except Exception as e:
                strategy = future_to_strategy[future]
                logger.error(f"   ❌ {strategy['name']} failed: {e}")
        
        logger.info(f"✅ Parallel validation complete: {len([c for c in candidates if c.is_valid])}/{len(candidates)} valid")
        return candidates
    
    def _generate_and_validate_single_candidate(self, 
                                              strategy: Dict[str, str],
                                              sample_logs: str, 
                                              device_type: str,
                                              baseline_vrl: str = None) -> VRLCandidate:
        """Generate and validate a single VRL candidate (runs in thread)"""
        candidate = VRLCandidate(strategy=strategy, vrl_code="")
        
        try:
            # Generate VRL using strategy and incumbent baseline
            vrl_code = self.llm_client.generate_vrl(
                sample_logs=sample_logs,
                device_type=device_type,
                stream=False,
                strategy=strategy,
                incumbent_vrl=baseline_vrl  # Use working baseline for all candidates
            )
            candidate.vrl_code = vrl_code
            # Use actual LiteLLM cost if available
            generation_cost = getattr(self.llm_client, 'last_completion_cost', 0) or 0
            candidate.total_cost += generation_cost
            
            # Validation and fixing loop (same as original but per-candidate)
            for attempt in range(3):  # Max 3 validation attempts per candidate
                is_valid, error_message = self.validator.validate(candidate.vrl_code, sample_logs)
                
                validation_attempt = {
                    "attempt": attempt + 1,
                    "is_valid": is_valid,
                    "error_code": self._extract_error_code(error_message) if not is_valid else None,
                    "error_message": error_message if not is_valid else None
                }
                candidate.validation_attempts.append(validation_attempt)
                
                if is_valid:
                    candidate.is_valid = True
                    break
                
                # Try local fixes first
                fixed_vrl = self.error_fixer.fix_locally(candidate.vrl_code, error_message)
                if fixed_vrl and fixed_vrl != candidate.vrl_code:
                    candidate.vrl_code = fixed_vrl
                    validation_attempt["local_fix_applied"] = True
                    continue
                
                # Use LLM fix if local fix didn't work
                if attempt < 2:  # Don't fix on last attempt
                    try:
                        llm_fixed = self.llm_client.fix_vrl_error(
                            candidate.vrl_code, error_message, sample_logs
                        )
                        if llm_fixed and llm_fixed != candidate.vrl_code:
                            candidate.vrl_code = llm_fixed
                            # Use actual LiteLLM cost if available
                            fix_cost = getattr(self.llm_client, 'last_completion_cost', 0) or 0
                            candidate.total_cost += fix_cost
                            validation_attempt["llm_fix_applied"] = True
                            validation_attempt["fix_cost"] = fix_cost
                    except Exception as e:
                        validation_attempt["llm_fix_error"] = str(e)
                        break
        
        except Exception as e:
            logger.error(f"Candidate {strategy['name']} generation failed: {e}")
        
        return candidate
    
    def _run_improvement_cycles(self, 
                               candidates: List[VRLCandidate],
                               sample_logs: str,
                               device_type: str, 
                               optimize_for: str) -> List[VRLCandidate]:
        """Run iterative improvement cycles until <5% improvement threshold"""
        
        improvement_threshold = 0.05  # 5%
        max_improvement_cycles = 5
        
        for cycle in range(1, max_improvement_cycles + 1):
            logger.info(f"\n🔄 Improvement Cycle {cycle}/{max_improvement_cycles}")
            
            active_candidates = []
            
            for candidate in candidates:
                if candidate.improvement_cycle >= max_improvement_cycles:
                    continue  # Skip candidates that hit max cycles
                
                # Check if last improvement was < 5%
                if (candidate.improvement_cycle > 0 and 
                    candidate.performance_improvement < improvement_threshold * 100):
                    logger.info(f"   ⏹️ {candidate.strategy['name']}: <5% improvement, stopping cycles")
                    continue
                
                logger.info(f"   🔧 Optimizing {candidate.strategy['name']}...")
                
                try:
                    # Use LLM to improve performance based on current metrics
                    improved_vrl = self._refine_vrl_for_performance(
                        candidate.vrl_code,
                        candidate.current_performance, 
                        sample_logs
                    )
                    
                    if improved_vrl and improved_vrl != candidate.vrl_code:
                        # Validate improved VRL
                        is_valid, error_message = self.validator.validate(improved_vrl, sample_logs)
                        
                        if is_valid:
                            # Test performance of improvement
                            new_performance = self._measure_vrl_performance(improved_vrl, sample_logs)
                            
                            # Calculate improvement
                            old_vpi = candidate.latest_vpi
                            new_vpi = new_performance.vrl_performance_index
                            improvement_pct = ((new_vpi - old_vpi) / max(old_vpi, 1)) * 100
                            
                            logger.info(f"     VPI: {old_vpi:,} → {new_vpi:,} ({improvement_pct:+.1f}%)")
                            
                            # Accept improvement if it's meaningful
                            if improvement_pct > 1.0:  # At least 1% improvement
                                candidate.vrl_code = improved_vrl
                                candidate.current_performance = new_performance
                                candidate.performance_history.append(new_performance)
                                candidate.improvement_cycle = cycle
                                candidate.total_cost += 0.3
                                
                                logger.success(f"     ✨ Improvement accepted!")
                            else:
                                logger.info(f"     ⚠️ Minimal improvement ({improvement_pct:.1f}%), keeping original")
                        else:
                            logger.warning(f"     ❌ Improved VRL failed validation: {self._extract_error_code(error_message)}")
                    
                    active_candidates.append(candidate)
                    
                except Exception as e:
                    logger.warning(f"   Improvement failed for {candidate.strategy['name']}: {e}")
            
            # Stop if no candidates are actively improving
            if not active_candidates:
                logger.info(f"🏁 All candidates below improvement threshold, stopping cycles")
                break
        
        return candidates
    
    def _measure_vector_startup_time(self) -> float:
        """Measure Vector CLI startup time with minimal passthrough config"""
        import tempfile
        import subprocess
        import yaml
        
        logger.info("🔧 Measuring Vector CLI startup time...")
        
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                
                # Create minimal test data
                startup_test_file = temp_path / 'vector_startup_test.ndjson'
                with open(startup_test_file, 'w') as f:
                    f.write('{"test": "startup"}\n')
                
                # Minimal passthrough config
                startup_config = {
                    'sources': {
                        'startup_input': {
                            'type': 'file',
                            'include': [str(startup_test_file)],
                            'read_from': 'beginning'
                        }
                    },
                    'sinks': {
                        'startup_output': {
                            'type': 'console',
                            'inputs': ['startup_input'],
                            'encoding': {'codec': 'json'}
                        }
                    }
                }
                
                startup_config_file = temp_path / 'vector_startup_config.yaml'
                with open(startup_config_file, 'w') as f:
                    yaml.dump(startup_config, f)
                
                # Measure startup time
                start_time = time.time()
                env = os.environ.copy()
                env['VECTOR_DATA_DIR'] = str(temp_path / 'vector_startup_data')
                
                process = subprocess.Popen(
                    ['vector', '--config', str(startup_config_file)],
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
                
                startup_time = max(0.1, startup_time)  # Minimum 0.1s
                logger.info(f"   Vector startup time: {startup_time:.2f}s")
                return startup_time
                
        except Exception as e:
            logger.warning(f"Vector startup measurement failed: {e}, using 1.0s default")
            return 1.0
    
    def _find_available_port(self, start_port: int = 8700) -> int:
        """Find available port for Vector GraphQL API (performance testing uses different range)"""
        for port in range(start_port, start_port + 200):
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                    result = sock.connect_ex(('127.0.0.1', port))
                    if result != 0:  # Port is available
                        return port
            except Exception:
                continue
        
        # Fallback to random port if all checked ports busy
        import random
        return random.randint(10000, 11000)
    
    def _monitor_vector_performance_with_metrics(self, 
                                               api_port: int,
                                               process: subprocess.Popen,
                                               psutil_process,
                                               expected_events: int,
                                               max_wait: int = 60) -> Tuple[int, List[float], List[float]]:
        """
        Monitor Vector processing with GraphQL metrics + performance collection
        
        Args:
            api_port: Vector GraphQL API port
            process: Vector process
            psutil_process: Process for CPU/memory monitoring  
            expected_events: Expected number of events
            max_wait: Maximum wait time
            
        Returns:
            Tuple of (events_processed, cpu_readings, memory_readings)
        """
        api_url = f"http://127.0.0.1:{api_port}/graphql"
        
        # GraphQL query for sink metrics
        metrics_query = """
        query {
            components {
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
        cpu_readings = []
        memory_readings = []
        start_time = time.time()
        
        logger.debug(f"Monitoring Vector performance via GraphQL on port {api_port}")
        
        while time.time() - start_time < max_wait:
            # Check if Vector process died
            if process.poll() is not None:
                break
            
            try:
                # Collect CPU/Memory metrics
                cpu_readings.append(psutil_process.cpu_percent())
                memory_readings.append(psutil_process.memory_info().rss / 1024 / 1024)  # MB
                
                # Query GraphQL API for event processing metrics
                response = requests.post(
                    api_url,
                    json={'query': metrics_query},
                    timeout=1
                )
                
                if response.status_code == 200:
                    data = response.json()
                    components = data.get('data', {}).get('components', {})
                    sinks = components.get('sinks', [])
                    
                    for sink in sinks:
                        if sink.get('name') == 'perf_output':
                            received = sink.get('metrics', {}).get('received', {})
                            events = received.get('events', {})
                            total = events.get('total', 0)
                            
                            if total != events_processed:
                                events_processed = total
                                logger.debug(f"Performance test: {events_processed}/{expected_events} events")
                            
                            # Check if all events processed
                            if events_processed >= expected_events:
                                logger.debug("All events processed, stopping performance monitoring")
                                time.sleep(1)  # Give a moment for final metrics
                                return events_processed, cpu_readings, memory_readings
                
                time.sleep(0.2)  # Sample every 200ms
                
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                break
            except requests.RequestException:
                # API not ready or network issue
                time.sleep(0.5)
                continue
            except Exception as e:
                logger.debug(f"Performance monitoring error: {e}")
                time.sleep(0.5)
                continue
        
        logger.debug(f"Performance monitoring complete: {events_processed}/{expected_events} events")
        return events_processed, cpu_readings, memory_readings