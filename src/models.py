from pydantic import BaseModel
from typing import List, Dict, Optional, Any
from enum import Enum


class ParseLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class CPUCost(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Domain(str, Enum):
    CYBER = "cyber"
    TRAVEL = "travel"
    IOT = "iot"
    DEFENCE = "defence"
    FINANCIAL = "financial"


class ExtractedField(BaseModel):
    name: str
    type: str
    description: str
    cpu_cost: CPUCost
    confidence: float
    sample_values: List[str] = []
    parser_type: str = "string"
    is_high_value: bool = False


class DataSource(BaseModel):
    name: str
    confidence: float
    description: str
    common_fields: List[str] = []
    known_parsers: List[str] = []


class LLMUsage(BaseModel):
    total_tokens: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost_usd: float = 0.0
    api_calls: int = 0


class ParserSource(BaseModel):
    """Information about the base parser source used"""
    type: str  # "internet", "custom", "hybrid"
    sources: List[str] = []  # List of parser names/URLs used as reference
    confidence: float = 0.0  # Confidence in the source attribution
    description: str = ""  # Description of how the source was used

class VRLParseResult(BaseModel):
    vrl_code: str
    fields: List[ExtractedField]
    data_source: Optional[DataSource] = None
    performance_metrics: Dict[str, float] = {}
    test_results: Dict[str, Any] = {}
    llm_usage: Optional[LLMUsage] = None
    parser_source: Optional[ParserSource] = None  # New field for parser attribution


class SampleData(BaseModel):
    original_sample: str  # Raw NDJSON text for LLM analysis
    field_analysis: Dict[str, Any]
    data_source_hints: List[str] = []
    common_patterns: List[str] = []