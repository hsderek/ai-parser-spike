#!/usr/bin/env python3
"""
PyVRL Tester - Fast Python-based VRL validation and testing
Performs quick syntax checks and field validation before running full Vector CLI
"""
import re
import json
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path


@dataclass
class PyVRLTestResult:
    """Result from PyVRL testing"""
    valid: bool
    errors: List[str]
    warnings: List[str]
    extracted_fields: List[str]
    transformations: List[str]
    confidence: float  # 0.0 to 1.0


class PyVRLTester:
    """
    Python-based VRL syntax validator and tester.
    Fast iteration testing before running actual Vector.
    """
    
    def __init__(self):
        # Common VRL functions and their signatures
        self.vrl_functions = {
            # Type conversion functions
            "string": {"args": 1, "infallible": True},
            "to_int": {"args": 1, "infallible": False},
            "to_float": {"args": 1, "infallible": False},
            "int": {"args": 1, "infallible": False},
            "float": {"args": 1, "infallible": False},
            "bool": {"args": 1, "infallible": False},
            
            # String functions
            "downcase": {"args": 1, "infallible": True},
            "upcase": {"args": 1, "infallible": True},
            "trim": {"args": 1, "infallible": True},
            "replace": {"args": 3, "infallible": True},
            "contains": {"args": 2, "infallible": True},
            "starts_with": {"args": 2, "infallible": True},
            "ends_with": {"args": 2, "infallible": True},
            "slice": {"args": 3, "infallible": True},
            "split": {"args": 2, "infallible": True},
            
            # Math functions
            "floor": {"args": 1, "infallible": True},
            "ceil": {"args": 1, "infallible": True},
            "round": {"args": 1, "infallible": True},
            "abs": {"args": 1, "infallible": True},
            "mod": {"args": 2, "infallible": True},
            
            # Date/time functions
            "now": {"args": 0, "infallible": True},
            "parse_timestamp": {"args": 1, "infallible": False},
            "format_timestamp": {"args": 2, "infallible": False},
            
            # Parsing functions
            "parse_regex": {"args": 2, "infallible": False},
            "parse_json": {"args": 1, "infallible": False},
            "parse_csv": {"args": 1, "infallible": False},
            "parse_key_value": {"args": 1, "infallible": False},
            
            # Utility functions
            "exists": {"args": 1, "infallible": True},
            "length": {"args": 1, "infallible": True},
            "is_null": {"args": 1, "infallible": True},
            "is_string": {"args": 1, "infallible": True},
            "is_int": {"args": 1, "infallible": True},
            "is_float": {"args": 1, "infallible": True},
            "is_bool": {"args": 1, "infallible": True},
            "is_array": {"args": 1, "infallible": True},
            "is_object": {"args": 1, "infallible": True},
            
            # Encoding functions
            "encode_json": {"args": 1, "infallible": True},
            "decode_base64": {"args": 1, "infallible": False},
            "encode_base64": {"args": 1, "infallible": True},
            
            # IP functions
            "ip_cidr_contains": {"args": 2, "infallible": False},
            "ip_subnet": {"args": 2, "infallible": False},
        }
        
        # Common VRL patterns
        self.patterns = {
            "field_access": re.compile(r'\.([a-zA-Z_][a-zA-Z0-9_]*)'),
            "field_assignment": re.compile(r'\.([a-zA-Z_][a-zA-Z0-9_]*)\s*='),
            "function_call": re.compile(r'([a-zA-Z_][a-zA-Z0-9_]*)[!\?]?\('),
            "if_statement": re.compile(r'\bif\s+'),
            "exists_check": re.compile(r'exists\s*\(\s*\.([a-zA-Z_][a-zA-Z0-9_]*)\s*\)'),
            "fallible_call": re.compile(r'([a-zA-Z_][a-zA-Z0-9_]*)\s*\('),
            "infallible_call": re.compile(r'([a-zA-Z_][a-zA-Z0-9_]*)!\s*\('),
            "coalesce": re.compile(r'\?\?'),
            "string_literal": re.compile(r'"([^"]*)"'),
            "regex_pattern": re.compile(r"r'([^']*)'"),
        }
    
    def validate_vrl(self, vrl_code: str, sample_data: Optional[List[Dict[str, Any]]] = None) -> PyVRLTestResult:
        """
        Validate VRL code syntax and structure.
        
        Args:
            vrl_code: The VRL code to validate
            sample_data: Optional sample data to test field references against
            
        Returns:
            PyVRLTestResult with validation results
        """
        errors = []
        warnings = []
        extracted_fields = []
        transformations = []
        confidence = 1.0
        
        # Split into lines for analysis
        lines = vrl_code.split('\n')
        
        # Check for common syntax errors
        errors.extend(self._check_syntax_errors(vrl_code))
        
        # Check function usage
        func_errors, func_warnings = self._check_function_usage(vrl_code)
        errors.extend(func_errors)
        warnings.extend(func_warnings)
        
        # Extract field operations
        extracted_fields = self._extract_field_operations(vrl_code)
        
        # Extract transformations
        transformations = self._extract_transformations(vrl_code)
        
        # Check field references against sample data
        if sample_data:
            field_warnings = self._check_field_references(vrl_code, sample_data)
            warnings.extend(field_warnings)
        
        # Check for infallibility requirements
        infallible_errors = self._check_infallibility(vrl_code)
        errors.extend(infallible_errors)
        
        # Calculate confidence score
        if errors:
            confidence = 0.3
        elif warnings:
            confidence = 0.7
        else:
            confidence = 0.9
        
        return PyVRLTestResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            extracted_fields=extracted_fields,
            transformations=transformations,
            confidence=confidence
        )
    
    def _check_syntax_errors(self, vrl_code: str) -> List[str]:
        """Check for common VRL syntax errors"""
        errors = []
        
        # Check for balanced braces
        open_braces = vrl_code.count('{')
        close_braces = vrl_code.count('}')
        if open_braces != close_braces:
            errors.append(f"Unbalanced braces: {open_braces} open, {close_braces} close")
        
        # Check for balanced parentheses
        open_parens = vrl_code.count('(')
        close_parens = vrl_code.count(')')
        if open_parens != close_parens:
            errors.append(f"Unbalanced parentheses: {open_parens} open, {close_parens} close")
        
        # Check for missing semicolons (VRL doesn't require them, but check for consistency)
        # Actually VRL doesn't use semicolons, so skip this
        
        # Check for invalid field names
        invalid_fields = re.findall(r'\.(\d[a-zA-Z0-9_]*)', vrl_code)
        for field in invalid_fields:
            errors.append(f"Invalid field name starting with digit: .{field}")
        
        # Check for unclosed strings
        if vrl_code.count('"') % 2 != 0:
            errors.append("Unclosed string literal")
        
        return errors
    
    def _check_function_usage(self, vrl_code: str) -> Tuple[List[str], List[str]]:
        """Check VRL function usage"""
        errors = []
        warnings = []
        
        # Find all function calls
        func_calls = self.patterns["function_call"].findall(vrl_code)
        
        for func in func_calls:
            # Remove ! or ? suffix
            func_name = func.rstrip('!?')
            
            # Check if function exists
            if func_name not in self.vrl_functions and func_name not in ['if', 'else', 'length']:
                warnings.append(f"Unknown function: {func_name}")
            
            # Check for functions that should be infallible
            if func_name in self.vrl_functions:
                func_info = self.vrl_functions[func_name]
                if not func_info["infallible"] and '!' not in func:
                    # Check if it's used with ?? (null coalescing)
                    pattern = f"{func}[^)]*\\)\\s*\\?\\?"
                    if not re.search(pattern, vrl_code):
                        warnings.append(f"Function '{func_name}' is fallible - consider using '{func_name}!' or '??' operator")
        
        return errors, warnings
    
    def _check_infallibility(self, vrl_code: str) -> List[str]:
        """Check that all assignments are infallible"""
        errors = []
        
        # Find all field assignments
        assignments = self.patterns["field_assignment"].findall(vrl_code)
        
        for field in assignments:
            # Find the assignment line
            pattern = f'\\.{field}\\s*=\\s*([^\\n]+)'
            match = re.search(pattern, vrl_code)
            if match:
                assignment_expr = match.group(1)
                
                # Check if assignment uses fallible functions without handling
                fallible_funcs = ['to_int', 'to_float', 'parse_timestamp', 'parse_regex', 'parse_json']
                for func in fallible_funcs:
                    if func in assignment_expr and f"{func}!" not in assignment_expr and "??" not in assignment_expr:
                        errors.append(f"Field '.{field}' assignment uses fallible function '{func}' without '!' or '??'")
        
        return errors
    
    def _extract_field_operations(self, vrl_code: str) -> List[str]:
        """Extract fields being created or modified"""
        fields = []
        
        # Find all field assignments
        assignments = self.patterns["field_assignment"].findall(vrl_code)
        fields.extend(assignments)
        
        return list(set(fields))
    
    def _extract_transformations(self, vrl_code: str) -> List[str]:
        """Extract transformation operations"""
        transformations = []
        
        # Find function calls
        func_calls = self.patterns["function_call"].findall(vrl_code)
        for func in func_calls:
            func_name = func.rstrip('!?')
            if func_name in ['downcase', 'upcase', 'trim', 'parse_regex', 'parse_json', 'to_int', 'to_float']:
                transformations.append(func_name)
        
        return list(set(transformations))
    
    def _check_field_references(self, vrl_code: str, sample_data: List[Dict[str, Any]]) -> List[str]:
        """Check field references against sample data"""
        warnings = []
        
        if not sample_data:
            return warnings
        
        # Get all available fields from sample data
        available_fields = set()
        for sample in sample_data[:3]:  # Check first few samples
            available_fields.update(sample.keys())
        
        # Find all field accesses in VRL
        field_accesses = self.patterns["field_access"].findall(vrl_code)
        
        for field in field_accesses:
            if field not in available_fields and field not in ['_parser_metadata']:
                # Check if it's a new field being created
                if f".{field} =" not in vrl_code:
                    warnings.append(f"Field '.{field}' not found in sample data")
        
        return warnings
    
    def suggest_fixes(self, vrl_code: str, errors: List[str]) -> str:
        """
        Suggest fixes for common VRL errors.
        
        Args:
            vrl_code: The VRL code with errors
            errors: List of errors found
            
        Returns:
            Fixed VRL code
        """
        fixed_code = vrl_code
        
        for error in errors:
            if "fallible function" in error:
                # Add ! to fallible functions
                match = re.search(r"'([a-zA-Z_]+)'", error)
                if match:
                    func = match.group(1)
                    fixed_code = re.sub(f'{func}\\(', f'{func}!(', fixed_code)
            
            elif "Unbalanced braces" in error:
                # Try to fix unbalanced braces
                open_count = fixed_code.count('{')
                close_count = fixed_code.count('}')
                if open_count > close_count:
                    fixed_code += '\n}' * (open_count - close_count)
                elif close_count > open_count:
                    # Remove extra closing braces
                    for _ in range(close_count - open_count):
                        fixed_code = fixed_code[:fixed_code.rfind('}')]
        
        return fixed_code


def quick_vrl_test(vrl_code: str, sample_file: Optional[Path] = None) -> bool:
    """
    Quick VRL validation test.
    
    Args:
        vrl_code: VRL code to test
        sample_file: Optional sample data file
        
    Returns:
        True if VRL is likely valid
    """
    tester = PyVRLTester()
    
    # Load sample data if provided
    sample_data = None
    if sample_file and sample_file.exists():
        sample_data = []
        with open(sample_file, 'r') as f:
            for line in f:
                if line.strip():
                    try:
                        sample_data.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
    
    # Run validation
    result = tester.validate_vrl(vrl_code, sample_data)
    
    print("PyVRL Validation Results:")
    print("-" * 40)
    print(f"Valid: {result.valid}")
    print(f"Confidence: {result.confidence:.1%}")
    
    if result.errors:
        print("\n❌ Errors:")
        for error in result.errors:
            print(f"  - {error}")
    
    if result.warnings:
        print("\n⚠️  Warnings:")
        for warning in result.warnings:
            print(f"  - {warning}")
    
    if result.extracted_fields:
        print(f"\n📝 Fields to be created: {', '.join(result.extracted_fields)}")
    
    if result.transformations:
        print(f"🔄 Transformations used: {', '.join(result.transformations)}")
    
    # Suggest fixes if there are errors
    if result.errors:
        print("\n🔧 Attempting auto-fix...")
        fixed_code = tester.suggest_fixes(vrl_code, result.errors)
        if fixed_code != vrl_code:
            print("Fixed code generated - retesting...")
            fixed_result = tester.validate_vrl(fixed_code, sample_data)
            if fixed_result.valid:
                print("✅ Fixed code is valid!")
                return True
    
    return result.valid