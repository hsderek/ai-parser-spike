#!/usr/bin/env python3
"""
Iterative VRL parser testing with performance validation
Tests multiple approaches, A/B performance comparison, and direct vector integration
"""
import pytest
import json
import tempfile
import subprocess
import shlex
import time
from pathlib import Path
from typing import List, Dict, Any, Tuple
import statistics

from src.pipeline import VRLPipeline
from src.config import Config
from src.models import VRLParseResult


class IterativeParserTester:
    """
    Handles iterative testing of VRL parsers with performance validation
    """
    
    def __init__(self, max_iterations: int = 3):
        self.max_iterations = max_iterations
        self.config = Config()
        
    def test_with_refinement(
        self, 
        sample_file: Path, 
        target_performance_tier: int = 2
    ) -> Dict[str, Any]:
        """
        Test parser with iterative refinement until performance target is met
        
        Args:
            sample_file: Path to NDJSON sample file
            target_performance_tier: Target performance tier (1=best, 4=acceptable)
            
        Returns:
            Dict with best parser, performance metrics, and iteration history
        """
        iteration_results = []
        best_result = None
        best_performance = 0
        
        print(f"\n🔄 Starting iterative testing for {sample_file.name}")
        print(f"🎯 Target performance tier: {target_performance_tier}")
        
        for iteration in range(self.max_iterations):
            print(f"\n📍 Iteration {iteration + 1}/{self.max_iterations}")
            
            # Generate parser with different approaches
            parser_variants = self._generate_parser_variants(sample_file, iteration)
            
            # Test each variant
            variant_results = []
            for variant_name, parser_result in parser_variants.items():
                print(f"   Testing {variant_name}...")
                performance_metrics = self._test_performance_with_vector(
                    parser_result, sample_file
                )
                
                variant_results.append({
                    'name': variant_name,
                    'parser': parser_result,
                    'performance': performance_metrics
                })
                
                # Track best overall result
                current_score = self._calculate_performance_score(performance_metrics)
                if current_score > best_performance:
                    best_performance = current_score
                    best_result = {
                        'iteration': iteration + 1,
                        'variant': variant_name,
                        'parser': parser_result,
                        'performance': performance_metrics,
                        'score': current_score
                    }
            
            iteration_results.append({
                'iteration': iteration + 1,
                'variants': variant_results,
                'best_variant': max(variant_results, key=lambda x: self._calculate_performance_score(x['performance']))
            })
            
            # Check if we've met the performance target
            best_tier = self._get_performance_tier(best_performance)
            if best_tier <= target_performance_tier:
                print(f"✅ Target performance tier {target_performance_tier} achieved!")
                print(f"📊 Achieved tier {best_tier} with score {best_performance:.2f}")
                break
        
        return {
            'best_result': best_result,
            'iteration_history': iteration_results,
            'final_tier': self._get_performance_tier(best_performance),
            'total_iterations': len(iteration_results)
        }
    
    def _generate_parser_variants(self, sample_file: Path, iteration: int) -> Dict[str, VRLParseResult]:
        """
        Generate different parser variants for A/B testing
        """
        variants = {}
        
        # Base configuration approaches
        configs = [
            {"level": "medium", "domains": ["cyber"], "approach": "balanced"},
            {"level": "high", "domains": ["cyber"], "approach": "comprehensive"},
            {"level": "low", "domains": ["cyber"], "approach": "minimal"},
        ]
        
        # Add iteration-specific refinements
        if iteration > 0:
            configs.append({
                "level": "high", 
                "domains": ["cyber", "defence"], 
                "approach": "multi_domain"
            })
            
        if iteration > 1:
            configs.append({
                "level": "medium", 
                "domains": ["cyber"], 
                "approach": "optimized"
            })
        
        for config in configs:
            approach = config.pop("approach")
            try:
                pipeline = VRLPipeline(self.config)
                result = pipeline.process(sample_file, **config)
                variants[f"{approach}_iter{iteration + 1}"] = result
            except Exception as e:
                print(f"   ⚠️  Failed to generate {approach} variant: {e}")
                continue
                
        return variants
    
    def _test_performance_with_vector(
        self, 
        parser_result: VRLParseResult, 
        sample_file: Path
    ) -> Dict[str, Any]:
        """
        Test VRL parser performance using actual vector installation
        """
        try:
            # Create temporary vector configuration
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                
                # Write VRL code to file
                vrl_file = temp_path / "parser.vrl"
                vrl_file.write_text(parser_result.vrl_code)
                
                # Create vector config
                vector_config = self._create_vector_config(vrl_file, sample_file, temp_path)
                config_file = temp_path / "vector.toml"
                config_file.write_text(vector_config)
                
                # Run vector performance test
                return self._run_vector_benchmark(config_file, sample_file, temp_path)
                
        except Exception as e:
            print(f"   ❌ Vector performance test failed: {e}")
            return {
                'events_per_second': 0,
                'cpu_usage_percent': 100,
                'memory_mb': 1000,
                'error_rate': 1.0,
                'latency_ms': 1000,
                'success': False,
                'error': str(e)
            }
    
    def _create_vector_config(self, vrl_file: Path, sample_file: Path, temp_dir: Path) -> str:
        """Create vector configuration for testing"""
        return f"""
[api]
enabled = true

[sources.test_input]
type = "file"
include = ["{sample_file.absolute()}"]
read_from = "beginning"

[transforms.parse]
type = "remap"
inputs = ["test_input"]
file = "{vrl_file.absolute()}"
drop_on_error = false

[sinks.test_output]
type = "file"
inputs = ["parse"]
path = "{temp_dir / 'output.ndjson'}"
encoding.codec = "ndjson"
"""
    
    def _run_vector_benchmark(
        self, 
        config_file: Path, 
        sample_file: Path, 
        temp_dir: Path
    ) -> Dict[str, Any]:
        """
        Run vector with the configuration and measure performance
        """
        start_time = time.time()
        
        try:
            # Check if vector is available
            vector_cmd = "vector"  # Assumes vector is in PATH
            
            # Run vector with timeout
            cmd = [vector_cmd, "--config", str(config_file)]
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Wait for processing with timeout
            stdout, stderr = process.communicate(timeout=30)
            end_time = time.time()
            
            # Calculate metrics
            duration = end_time - start_time
            
            # Count input and output lines
            input_lines = self._count_lines(sample_file)
            output_file = temp_dir / "output.ndjson"
            output_lines = self._count_lines(output_file) if output_file.exists() else 0
            
            events_per_second = output_lines / duration if duration > 0 else 0
            error_rate = (input_lines - output_lines) / input_lines if input_lines > 0 else 1.0
            
            return {
                'events_per_second': events_per_second,
                'cpu_usage_percent': 10,  # Estimated - would need proper monitoring
                'memory_mb': 50,  # Estimated - would need proper monitoring  
                'error_rate': error_rate,
                'latency_ms': duration * 1000,
                'duration_seconds': duration,
                'input_events': input_lines,
                'output_events': output_lines,
                'success': process.returncode == 0,
                'stdout': stdout[:1000],  # Truncated
                'stderr': stderr[:1000]   # Truncated
            }
            
        except subprocess.TimeoutExpired:
            process.kill()
            return {
                'events_per_second': 0,
                'cpu_usage_percent': 100,
                'memory_mb': 500,
                'error_rate': 1.0,
                'latency_ms': 30000,
                'success': False,
                'error': 'Vector process timeout (30s)'
            }
        except FileNotFoundError:
            return {
                'events_per_second': 0,
                'cpu_usage_percent': 0,
                'memory_mb': 0,
                'error_rate': 0,
                'latency_ms': 0,
                'success': False,
                'error': 'Vector not found in PATH - install vector first'
            }
        except Exception as e:
            return {
                'events_per_second': 0,
                'cpu_usage_percent': 100,
                'memory_mb': 500,
                'error_rate': 1.0,
                'latency_ms': 5000,
                'success': False,
                'error': f'Vector execution failed: {str(e)}'
            }
    
    def _count_lines(self, file_path: Path) -> int:
        """Count lines in a file"""
        try:
            with open(file_path, 'r') as f:
                return sum(1 for _ in f)
        except:
            return 0
    
    def _calculate_performance_score(self, metrics: Dict[str, Any]) -> float:
        """
        Calculate overall performance score (higher is better)
        """
        if not metrics.get('success', False):
            return 0.0
        
        # Normalize metrics to 0-100 scale and weight them
        eps_score = min(metrics.get('events_per_second', 0) / 10, 100)  # 10 EPS = 100 points
        error_score = max(0, (1 - metrics.get('error_rate', 1.0)) * 100)  # Lower error rate = higher score
        latency_score = max(0, 100 - (metrics.get('latency_ms', 1000) / 10))  # Lower latency = higher score
        
        # Weighted average
        total_score = (eps_score * 0.4) + (error_score * 0.4) + (latency_score * 0.2)
        return total_score
    
    def _get_performance_tier(self, score: float) -> int:
        """
        Convert performance score to tier
        Tier 1: 80+ (Excellent)
        Tier 2: 60+ (Good) 
        Tier 3: 40+ (Acceptable)
        Tier 4: 20+ (Poor)
        Tier 5: <20 (Unusable)
        """
        if score >= 80:
            return 1
        elif score >= 60:
            return 2
        elif score >= 40:
            return 3
        elif score >= 20:
            return 4
        else:
            return 5


class TestIterativeSyslogParsing:
    """
    Test suite for iterative syslog parsing with performance validation
    """
    
    @pytest.fixture
    def tester(self):
        """Create iterative parser tester"""
        return IterativeParserTester(max_iterations=3)
    
    @pytest.fixture
    def sample_files(self):
        """Get sample files for testing"""
        samples_dir = Path("samples")
        return {
            'cisco_asa': samples_dir / "cisco-asa.ndjson",
            'palo_alto': samples_dir / "palo-alto.ndjson",
            'fortinet': samples_dir / "fortinet-fortigate.ndjson",
            'comprehensive': samples_dir / "comprehensive-syslog.ndjson"
        }
    
    def test_cisco_asa_iterative_refinement(self, tester, sample_files):
        """Test Cisco ASA parsing with iterative refinement"""
        sample_file = sample_files['cisco_asa']
        
        if not sample_file.exists():
            pytest.skip(f"Sample file {sample_file} not found")
        
        result = tester.test_with_refinement(sample_file, target_performance_tier=2)
        
        # Validate iterative testing results
        assert result['best_result'] is not None, "No successful parser generated"
        assert result['total_iterations'] > 0, "No iterations completed"
        assert result['final_tier'] <= 4, f"Performance tier {result['final_tier']} too poor"
        
        # Validate best parser
        best_parser = result['best_result']['parser']
        assert best_parser.vrl_code is not None, "No VRL code generated"
        assert len(best_parser.fields) > 0, "No fields extracted"
        
        # Check for ASA-specific fields
        field_names = [field.name for field in best_parser.fields]
        asa_fields = ["hostname", "priority", "severity"]
        found_fields = sum(1 for field in asa_fields if field in field_names)
        assert found_fields >= 2, f"Expected ASA fields not found. Got: {field_names}"
        
        print(f"\n✅ Cisco ASA Test Results:")
        print(f"   🏆 Best performance tier: {result['final_tier']}")
        print(f"   🔄 Iterations: {result['total_iterations']}")
        print(f"   📊 Score: {result['best_result']['score']:.2f}")
        
    def test_comprehensive_syslog_iterative_refinement(self, tester, sample_files):
        """Test comprehensive syslog parsing with iterative refinement"""
        sample_file = sample_files['comprehensive']
        
        if not sample_file.exists():
            pytest.skip(f"Sample file {sample_file} not found")
        
        result = tester.test_with_refinement(sample_file, target_performance_tier=3)
        
        # Validate iterative testing results
        assert result['best_result'] is not None, "No successful parser generated"
        assert result['total_iterations'] > 0, "No iterations completed"
        
        # Should handle comprehensive data well
        best_parser = result['best_result']['parser']
        assert len(best_parser.fields) >= 10, f"Expected at least 10 fields for comprehensive data, got {len(best_parser.fields)}"
        
        # Check for common syslog fields
        field_names = [field.name for field in best_parser.fields]
        common_fields = ["timestamp", "hostname", "severity", "priority"]
        found_fields = sum(1 for field in common_fields if field in field_names)
        assert found_fields >= 3, f"Expected common syslog fields not found. Got: {field_names}"
        
        print(f"\n✅ Comprehensive Syslog Test Results:")
        print(f"   🏆 Best performance tier: {result['final_tier']}")
        print(f"   🔄 Iterations: {result['total_iterations']}")
        print(f"   📊 Score: {result['best_result']['score']:.2f}")
        print(f"   📝 Fields: {len(best_parser.fields)}")
    
    def test_ab_performance_comparison(self, tester, sample_files):
        """Test A/B performance comparison across different sample types"""
        results = {}
        
        # Test multiple sample files
        test_files = ['cisco_asa', 'palo_alto', 'fortinet']
        
        for file_key in test_files:
            sample_file = sample_files[file_key]
            if not sample_file.exists():
                continue
                
            print(f"\n🧪 A/B Testing {file_key}")
            result = tester.test_with_refinement(sample_file, target_performance_tier=3)
            results[file_key] = result
        
        assert len(results) > 0, "No sample files available for A/B testing"
        
        # Compare results across different device types
        best_overall = max(results.values(), key=lambda x: x['best_result']['score'] if x['best_result'] else 0)
        
        print(f"\n📊 A/B Testing Summary:")
        for file_key, result in results.items():
            score = result['best_result']['score'] if result['best_result'] else 0
            tier = result['final_tier']
            print(f"   {file_key}: Tier {tier}, Score {score:.2f}")
        
        # Validate that at least one parser achieved reasonable performance
        assert best_overall['final_tier'] <= 4, "All parsers performed poorly"
        
    def test_performance_regression_detection(self, tester, sample_files):
        """Test detection of performance regression across iterations"""
        sample_file = sample_files.get('cisco_asa')
        
        if not sample_file or not sample_file.exists():
            pytest.skip("Cisco ASA sample not available")
        
        # Run with higher iteration count to detect regression
        tester_extended = IterativeParserTester(max_iterations=4)
        result = tester_extended.test_with_refinement(sample_file)
        
        # Analyze iteration performance trends
        scores_by_iteration = []
        for iteration_result in result['iteration_history']:
            best_variant = iteration_result['best_variant']
            score = tester._calculate_performance_score(best_variant['performance'])
            scores_by_iteration.append(score)
        
        # Check that performance generally improves or stabilizes
        if len(scores_by_iteration) >= 3:
            # Allow for some variance but expect improvement trend
            final_score = scores_by_iteration[-1]
            initial_score = scores_by_iteration[0]
            
            print(f"\n📈 Performance Trend Analysis:")
            for i, score in enumerate(scores_by_iteration):
                print(f"   Iteration {i + 1}: {score:.2f}")
            
            # Performance should not severely degrade
            assert final_score >= initial_score * 0.7, f"Severe performance regression detected: {initial_score:.2f} -> {final_score:.2f}"