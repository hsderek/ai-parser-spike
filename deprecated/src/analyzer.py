import re
import json
from typing import List, Dict, Any, Set, Optional
from collections import Counter, defaultdict
from .config import Config
from .models import SampleData, ExtractedField, CPUCost
from .field_naming import normalize_field_name, FieldNamingConvention, standardize_field_name


class DataAnalyzer:
    def __init__(self, config: Config):
        self.config = config
        self.high_value_fields = {
            "msg", "message", "description", "log", "event",
            "timestamp", "time", "@timestamp", "datetime",
            "level", "severity", "priority", "status",
            "user", "username", "userid", "user_id",
            "ip", "src_ip", "dst_ip", "client_ip", "remote_addr",
            "host", "hostname", "server", "source",
            "error", "exception", "stack_trace"
        }
    
    def analyze_samples(self, samples: List[Dict]) -> SampleData:
        if not samples:
            raise ValueError("No samples provided")
        
        field_analysis = self._analyze_fields(samples)
        data_source_hints = self._extract_data_source_hints(samples)
        common_patterns = self._find_common_patterns(samples)
        
        # Convert samples to NDJSON text for LLM analysis (limit to first few samples)
        sample_limit = min(5, len(samples))  # Use first 5 samples for analysis
        sample_lines = [json.dumps(sample, separators=(',', ':')) for sample in samples[:sample_limit]]
        original_sample_text = '\n'.join(sample_lines)
        
        return SampleData(
            original_sample=original_sample_text,
            field_analysis=field_analysis,
            data_source_hints=data_source_hints,
            common_patterns=common_patterns
        )
    
    def _analyze_fields(self, samples: List[Dict]) -> Dict[str, Any]:
        all_fields: Set[str] = set()
        field_types: Dict[str, Counter] = defaultdict(Counter)
        field_samples: Dict[str, List[str]] = defaultdict(list)
        
        for sample in samples:
            flat_fields = self._flatten_dict(sample)
            all_fields.update(flat_fields.keys())
            
            for field, value in flat_fields.items():
                python_type = type(value).__name__
                field_types[field][python_type] += 1
                
                if len(field_samples[field]) < 5:
                    field_samples[field].append(str(value)[:100])
        
        analysis = {}
        for field in all_fields:
            most_common_type = field_types[field].most_common(1)[0][0]
            mapped_type = self._map_python_to_abstract_type(most_common_type, field_samples[field])
            
            analysis[field] = {
                "python_type": most_common_type,
                "abstract_type": mapped_type,
                "frequency": sum(field_types[field].values()),
                "samples": field_samples[field],
                "is_high_value": self._is_high_value_field(field)
            }
        
        return analysis
    
    def _flatten_dict(self, d: Dict, parent_key: str = "", sep: str = ".") -> Dict[str, Any]:
        items: List[tuple] = []
        for k, v in d.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            if isinstance(v, dict):
                items.extend(self._flatten_dict(v, new_key, sep).items())
            elif isinstance(v, list) and v and isinstance(v[0], dict):
                for i, item in enumerate(v[:3]):
                    items.extend(self._flatten_dict(item, f"{new_key}[{i}]", sep).items())
            else:
                items.append((new_key, v))
        return dict(items)
    
    def _map_python_to_abstract_type(self, python_type: str, samples: List[str]) -> str:
        if python_type == "int":
            return "int64"
        elif python_type == "float":
            return "float64"
        elif python_type == "bool":
            return "boolean"
        elif python_type == "str":
            return self._infer_string_type(samples)
        else:
            return "string"
    
    def _infer_string_type(self, samples: List[str]) -> str:
        if not samples:
            return "string"
        
        ip_pattern = re.compile(r'^(?:\d{1,3}\.){3}\d{1,3}$')
        timestamp_pattern = re.compile(r'\d{4}-\d{2}-\d{2}')
        uuid_pattern = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.I)
        
        for sample in samples[:3]:
            if ip_pattern.match(sample):
                return "ipv4"
            elif uuid_pattern.match(sample):
                return "uuid"
            elif timestamp_pattern.search(sample):
                return "datetime"
        
        avg_length = sum(len(s) for s in samples) / len(samples)
        if avg_length > 100:
            return "text"
        
        unique_count = len(set(samples))
        if len(samples) > 1 and unique_count / len(samples) < 0.3:
            return "string_lowcardinality"
        
        return "string"
    
    def _is_high_value_field(self, field_name: str) -> bool:
        field_lower = field_name.lower()
        return any(hvf in field_lower for hvf in self.high_value_fields)
    
    def _extract_data_source_hints(self, samples: List[Dict]) -> List[str]:
        hints = []
        
        all_fields: Set[str] = set()
        for sample in samples:
            all_fields.update(self._flatten_dict(sample).keys())
        
        if any("syslog" in str(field).lower() for field in all_fields):
            hints.append("syslog")
        if any("apache" in str(field).lower() or "nginx" in str(field).lower() for field in all_fields):
            hints.append("web_server_logs")
        if any("kubernetes" in str(field).lower() or "k8s" in str(field).lower() for field in all_fields):
            hints.append("kubernetes")
        if any("aws" in str(field).lower() or "cloudtrail" in str(field).lower() for field in all_fields):
            hints.append("aws_cloudtrail")
        
        return hints
    
    def _find_common_patterns(self, samples: List[Dict]) -> List[str]:
        patterns = []
        
        for sample in samples[:3]:
            flat = self._flatten_dict(sample)
            for field, value in flat.items():
                if isinstance(value, str) and len(value) > 10:
                    if re.search(r'\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}:\d{2}', value):
                        patterns.append("iso_timestamp")
                    elif re.search(r'ERROR|WARN|INFO|DEBUG', value, re.I):
                        patterns.append("log_levels")
                    elif re.search(r'(?:\d{1,3}\.){3}\d{1,3}', value):
                        patterns.append("ip_addresses")
        
        return list(set(patterns))
    
    def extract_field_candidates(self, sample_data: SampleData, level: str, domains: Optional[List[str]] = None) -> List[ExtractedField]:
        candidates = []
        
        # Get naming convention from config
        convention_str = self.config.field_naming_convention
        convention = FieldNamingConvention.SNAKE_CASE  # Default
        try:
            if convention_str == "camelCase":
                convention = FieldNamingConvention.CAMEL_CASE
            elif convention_str == "PascalCase":
                convention = FieldNamingConvention.PASCAL_CASE
            elif convention_str == "kebab-case":
                convention = FieldNamingConvention.KEBAB_CASE
            elif convention_str == "original":
                convention = FieldNamingConvention.ORIGINAL
        except:
            pass  # Use default snake_case
        
        for field_name, analysis in sample_data.field_analysis.items():
            if self._should_include_field(field_name, analysis, level):
                # Apply naming convention
                normalized_name = normalize_field_name(field_name, convention)
                
                field = ExtractedField(
                    name=normalized_name,
                    type=analysis["abstract_type"],
                    description=self._generate_field_description(field_name, analysis),
                    cpu_cost=self._estimate_cpu_cost(analysis["abstract_type"], field_name),
                    confidence=self._calculate_confidence(analysis),
                    sample_values=analysis["samples"],
                    is_high_value=analysis["is_high_value"]
                )
                
                # Store original name if it was changed
                if normalized_name != field_name:
                    field.metadata = {"original_name": field_name}
                
                candidates.append(field)
        
        return candidates
    
    def _should_include_field(self, field_name: str, analysis: Dict, level: str) -> bool:
        if level == "high":
            return analysis["is_high_value"] and analysis["frequency"] >= 0.8
        elif level == "medium":
            return analysis["is_high_value"] or analysis["frequency"] >= 0.5
        else:
            return analysis["frequency"] >= 0.3
    
    def _generate_field_description(self, field_name: str, analysis: Dict) -> str:
        type_info = analysis["abstract_type"]
        freq = analysis["frequency"]
        
        if analysis["is_high_value"]:
            return f"High-value {type_info} field appearing in {freq} samples"
        else:
            return f"{type_info} field with {freq} occurrences"
    
    def _estimate_cpu_cost(self, abstract_type: str, field_name: str) -> CPUCost:
        if abstract_type in ["string", "string_fast", "boolean"]:
            return CPUCost.LOW
        elif abstract_type in ["int64", "float64", "datetime"]:
            return CPUCost.MEDIUM
        elif "json" in abstract_type.lower() or "text" in abstract_type.lower():
            return CPUCost.HIGH
        else:
            return CPUCost.MEDIUM
    
    def _calculate_confidence(self, analysis: Dict) -> float:
        base_confidence = min(analysis["frequency"], 1.0)
        if analysis["is_high_value"]:
            base_confidence *= 1.2
        return min(base_confidence, 1.0)