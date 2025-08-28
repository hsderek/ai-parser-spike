#!/usr/bin/env python3
"""
Error Batch Collector - Collects ALL VRL errors in one pass

Instead of iterating error-by-error, collect all syntax and validation 
errors at once, then send comprehensive feedback to LLM.
"""

import subprocess
import tempfile
import json
from typing import List, Dict, Any, Tuple
from pathlib import Path
from loguru import logger
import pyvrl

class ErrorBatchCollector:
    """Collect all VRL errors comprehensively"""
    
    def __init__(self):
        self.error_categories = {
            'syntax': [],
            'type': [],
            'fallible': [],
            'array_access': [],
            'undefined': [],
            'other': []
        }
        
    def collect_all_errors(self, vrl_code: str, samples: List[Dict]) -> Dict[str, Any]:
        """
        Collect ALL errors from multiple validation methods
        
        Returns comprehensive error report
        """
        all_errors = {
            'pyvrl_errors': [],
            'vector_errors': [],
            'runtime_errors': [],
            'categorized': self.error_categories.copy(),
            'total_count': 0,
            'summary': ''
        }
        
        # 1. PyVRL syntax validation
        logger.info("📋 Phase 1: PyVRL syntax validation")
        pyvrl_errors = self._collect_pyvrl_errors(vrl_code)
        all_errors['pyvrl_errors'] = pyvrl_errors
        
        # 2. Vector CLI validation (if PyVRL passes basic syntax)
        if len(pyvrl_errors) < 10:  # Don't bother if too many syntax errors
            logger.info("📋 Phase 2: Vector CLI validation")
            vector_errors = self._collect_vector_errors(vrl_code)
            all_errors['vector_errors'] = vector_errors
        
        # 3. Runtime testing with samples (if compilation passes)
        if len(pyvrl_errors) == 0 and len(all_errors['vector_errors']) == 0:
            logger.info("📋 Phase 3: Runtime testing with samples")
            runtime_errors = self._collect_runtime_errors(vrl_code, samples[:5])
            all_errors['runtime_errors'] = runtime_errors
        
        # Categorize all errors
        all_error_messages = (
            all_errors['pyvrl_errors'] + 
            all_errors['vector_errors'] + 
            all_errors['runtime_errors']
        )
        
        all_errors['categorized'] = self._categorize_errors(all_error_messages)
        all_errors['total_count'] = len(all_error_messages)
        
        # Generate summary
        all_errors['summary'] = self._generate_error_summary(all_errors)
        
        logger.info(f"📊 Collected {all_errors['total_count']} total errors")
        if all_errors['categorized']:
            for category, errors in all_errors['categorized'].items():
                if errors:
                    logger.info(f"   {category}: {len(errors)} errors")
        
        return all_errors
    
    def _collect_pyvrl_errors(self, vrl_code: str) -> List[str]:
        """Collect all PyVRL validation errors"""
        errors = []
        
        try:
            # First pass - basic validation
            result = pyvrl.validate_vrl(vrl_code)
            if not result.is_valid():
                for error in result.errors:
                    errors.append(f"PyVRL: {error}")
                    
        except Exception as e:
            # Parse exception for all error details
            error_str = str(e)
            # Split by "error[" to get individual errors
            error_parts = error_str.split('error[')
            for part in error_parts[1:]:  # Skip first empty part
                errors.append(f"PyVRL: error[{part.split('=')[0]}")
                
        return errors
    
    def _collect_vector_errors(self, vrl_code: str) -> List[str]:
        """Collect Vector CLI compilation errors"""
        errors = []
        
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.vrl', delete=False) as f:
                f.write(vrl_code)
                vrl_file = f.name
            
            # Run vector validate
            result = subprocess.run(
                ['vector', 'vrl', '--file', vrl_file],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode != 0:
                # Parse all errors from stderr
                stderr_lines = result.stderr.strip().split('\n')
                for line in stderr_lines:
                    if 'error' in line.lower():
                        errors.append(f"Vector: {line}")
                        
            Path(vrl_file).unlink(missing_ok=True)
            
        except Exception as e:
            errors.append(f"Vector: Validation failed - {e}")
            
        return errors
    
    def _collect_runtime_errors(self, vrl_code: str, samples: List[Dict]) -> List[str]:
        """Test with actual samples to find runtime errors"""
        errors = []
        
        try:
            # Create test config
            test_config = self._create_test_config(vrl_code)
            
            with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as f:
                f.write(test_config)
                config_file = f.name
            
            # Test with each sample
            for i, sample in enumerate(samples):
                test_result = self._test_single_sample(config_file, sample)
                if not test_result['success']:
                    errors.append(f"Runtime (sample {i+1}): {test_result['error']}")
            
            Path(config_file).unlink(missing_ok=True)
            
        except Exception as e:
            errors.append(f"Runtime: Testing failed - {e}")
            
        return errors
    
    def _categorize_errors(self, errors: List[str]) -> Dict[str, List[str]]:
        """Categorize errors by type"""
        categories = {
            'syntax': [],
            'type': [],
            'fallible': [],
            'array_access': [],
            'undefined': [],
            'logic': [],
            'other': []
        }
        
        for error in errors:
            categorized = False
            
            # Syntax errors
            if 'syntax error' in error or 'E203' in error:
                categories['syntax'].append(error)
                categorized = True
            
            # Type errors
            elif 'type' in error.lower() or 'E300' in error:
                categories['type'].append(error)
                categorized = True
            
            # Fallible operations
            elif 'E103' in error or 'fallible' in error:
                categories['fallible'].append(error)
                categorized = True
            
            # Array access
            elif 'array' in error or 'index' in error or 'length' in error:
                categories['array_access'].append(error)
                categorized = True
            
            # Undefined variables/fields
            elif 'undefined' in error or 'not found' in error:
                categories['undefined'].append(error)
                categorized = True
            
            # Logic errors
            elif 'Runtime' in error:
                categories['logic'].append(error)
                categorized = True
            
            # Other
            if not categorized:
                categories['other'].append(error)
        
        return categories
    
    def _generate_error_summary(self, all_errors: Dict) -> str:
        """Generate concise error summary for LLM"""
        summary_parts = []
        
        if all_errors['total_count'] == 0:
            return "No errors detected"
        
        summary_parts.append(f"Found {all_errors['total_count']} total errors:")
        
        # Priority order for fixing
        priority_categories = ['syntax', 'array_access', 'fallible', 'type', 'undefined', 'logic']
        
        for category in priority_categories:
            if all_errors['categorized'][category]:
                count = len(all_errors['categorized'][category])
                summary_parts.append(f"- {category.title()}: {count} errors")
                
                # Add first example of each category
                first_error = all_errors['categorized'][category][0]
                # Clean up error message
                clean_error = first_error.split('\n')[0][:200]
                summary_parts.append(f"  Example: {clean_error}")
        
        return '\n'.join(summary_parts)
    
    def _create_test_config(self, vrl_code: str) -> str:
        """Create Vector config for testing"""
        return f"""
[sources.test_input]
type = "stdin"
decoding.codec = "json"

[transforms.test_vrl]
type = "remap"
inputs = ["test_input"]
source = '''
{vrl_code}
'''

[sinks.test_output]
type = "console"
inputs = ["test_vrl"]
encoding.codec = "json"
"""
    
    def _test_single_sample(self, config_file: str, sample: Dict) -> Dict:
        """Test a single sample through Vector"""
        try:
            # Run vector with sample
            process = subprocess.Popen(
                ['vector', '-c', config_file],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            stdout, stderr = process.communicate(
                input=json.dumps(sample),
                timeout=2
            )
            
            if process.returncode != 0:
                return {'success': False, 'error': stderr}
            
            return {'success': True}
            
        except Exception as e:
            return {'success': False, 'error': str(e)}


def create_comprehensive_error_feedback(all_errors: Dict) -> str:
    """
    Create comprehensive feedback for LLM with ALL errors at once
    """
    feedback_parts = []
    
    feedback_parts.append("# COMPREHENSIVE ERROR REPORT")
    feedback_parts.append(all_errors['summary'])
    feedback_parts.append("")
    
    # Group errors by fix strategy
    feedback_parts.append("# ERRORS TO FIX (grouped by type):")
    feedback_parts.append("")
    
    # 1. Syntax errors (must fix first)
    if all_errors['categorized']['syntax']:
        feedback_parts.append("## 1. SYNTAX ERRORS (fix these first):")
        for error in all_errors['categorized']['syntax'][:5]:  # Top 5
            feedback_parts.append(f"- {error}")
        feedback_parts.append("FIX: Check bracket matching, statement termination")
        feedback_parts.append("")
    
    # 2. Array access errors
    if all_errors['categorized']['array_access']:
        feedback_parts.append("## 2. ARRAY ACCESS ERRORS:")
        for error in all_errors['categorized']['array_access'][:3]:
            feedback_parts.append(f"- {error}")
        feedback_parts.append("FIX: Use literal integers only, no variables in array[index]")
        feedback_parts.append("FIX: Always check length before access")
        feedback_parts.append("")
    
    # 3. Fallible operations
    if all_errors['categorized']['fallible']:
        feedback_parts.append("## 3. FALLIBLE OPERATIONS:")
        for error in all_errors['categorized']['fallible'][:3]:
            feedback_parts.append(f"- {error}")
        feedback_parts.append("FIX: Add ! to make infallible or use ?? for defaults")
        feedback_parts.append("")
    
    # 4. Type errors
    if all_errors['categorized']['type']:
        feedback_parts.append("## 4. TYPE ERRORS:")
        for error in all_errors['categorized']['type'][:3]:
            feedback_parts.append(f"- {error}")
        feedback_parts.append("FIX: Use to_string(), to_int() for conversions")
        feedback_parts.append("")
    
    feedback_parts.append("# IMPORTANT:")
    feedback_parts.append("- Fix ALL the above errors in a single pass")
    feedback_parts.append("- Do not use variables for array indexing")
    feedback_parts.append("- Check array length before any access")
    feedback_parts.append("- Make fallible operations infallible with !")
    
    return '\n'.join(feedback_parts)