#!/usr/bin/env python3
"""
FastAPI-ready request and response models
Separated from internal models for clean API boundaries
"""
from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any, Union
from enum import Enum
from pathlib import Path

from .models import ParseLevel, Domain, CPUCost


class ParseRequest(BaseModel):
    """Request model for VRL parser generation"""
    file_path: str = Field(..., description="Path to NDJSON input file")
    level: ParseLevel = Field(default=ParseLevel.MEDIUM, description="Parsing detail level")
    domains: Optional[List[Domain]] = Field(default=None, description="Target domains for specialized parsing")
    max_fields: Optional[int] = Field(default=None, description="Maximum number of fields to extract")
    model_preference: Optional[str] = Field(default="opus", description="LLM model preference (opus/sonnet/auto)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "file_path": "/path/to/logs.ndjson",
                "level": "medium",
                "domains": ["cyber", "defence"],
                "max_fields": 15,
                "model_preference": "opus"
            }
        }


class IterativeParseRequest(ParseRequest):
    """Request model for iterative VRL parser generation with performance optimization"""
    max_iterations: int = Field(default=3, description="Maximum refinement iterations")
    target_performance_tier: int = Field(default=2, description="Target performance tier (1=best, 4=acceptable)")
    enable_vector_testing: bool = Field(default=True, description="Enable actual Vector performance testing")
    
    class Config:
        json_schema_extra = {
            "example": {
                "file_path": "/path/to/logs.ndjson",
                "level": "high",
                "domains": ["cyber"],
                "max_iterations": 3,
                "target_performance_tier": 2,
                "enable_vector_testing": True
            }
        }


class FieldInfo(BaseModel):
    """Field information in API response"""
    name: str
    type: str
    description: str
    cpu_cost: CPUCost
    confidence: float
    sample_values: List[str] = []
    parser_type: str = "string"
    is_high_value: bool = False


class DataSourceInfo(BaseModel):
    """Data source information in API response"""
    name: str
    confidence: float
    description: str
    common_fields: List[str] = []
    known_parsers: List[str] = []


class ParserSourceInfo(BaseModel):
    """Parser source attribution information"""
    type: str  # "internet", "custom", "hybrid"
    sources: List[str] = []
    confidence: float = 0.0
    description: str = ""


class LLMUsageInfo(BaseModel):
    """LLM usage and cost information"""
    total_tokens: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost_usd: float = 0.0
    api_calls: int = 0


class PerformanceMetrics(BaseModel):
    """Performance test results"""
    events_per_second: float = 0.0
    cpu_usage_percent: float = 0.0
    memory_mb: float = 0.0
    error_rate: float = 0.0
    latency_ms: float = 0.0
    duration_seconds: float = 0.0
    input_events: int = 0
    output_events: int = 0
    success: bool = False
    error: Optional[str] = None


class ParserVariant(BaseModel):
    """Information about a parser variant tested during iterations"""
    name: str
    iteration: int
    performance: PerformanceMetrics
    field_count: int
    performance_score: float
    performance_tier: int


class IterationHistory(BaseModel):
    """History of a single iteration"""
    iteration: int
    variants_tested: List[ParserVariant]
    best_variant: ParserVariant
    improvements: List[str] = []


class ParseSummary(BaseModel):
    """Summary statistics for the parsing results"""
    total_fields: int
    high_value_fields: int
    low_cpu_cost_fields: int
    medium_cpu_cost_fields: int
    high_cpu_cost_fields: int
    estimated_performance_tier: int = 0
    total_processing_time_seconds: float = 0.0


class ParseResponse(BaseModel):
    """Standard response for VRL parser generation"""
    status: str = "success"
    message: str
    data: Dict[str, Any]
    narrative: Optional[str] = Field(default=None, description="Human-readable explanation of parsing results and decisions")
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": "success",
                "message": "Successfully generated VRL parser with 12 fields",
                "data": {
                    "vrl_code": "# VRL parser code...",
                    "fields": [],
                    "data_source": None,
                    "parser_source": None,
                    "performance_metrics": {},
                    "llm_usage": {},
                    "summary": {}
                },
                "narrative": "This parser was generated for Cisco ASA firewall logs. DFE identified 12 key security fields including source/destination IPs, actions, and severity levels. The parser prioritizes performance by using string operations over regex patterns. Field types were optimized for typical cybersecurity query patterns - IP addresses use string_fast for rapid filtering, while log messages use text for full-text search capabilities."
            }
        }


class IterativeParseResponse(BaseModel):
    """Response for iterative VRL parser generation"""
    status: str = "success"
    message: str
    data: Dict[str, Any]
    iterations: Dict[str, Any]
    narrative: Optional[str] = Field(default=None, description="Human-readable explanation of iterative parsing results and optimization decisions")
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": "success",
                "message": "Generated optimized VRL parser after 2 iterations",
                "data": {
                    "vrl_code": "# Optimized VRL parser code...",
                    "fields": [],
                    "final_performance_tier": 2,
                    "performance_score": 85.5
                },
                "iterations": {
                    "total_iterations": 2,
                    "history": [],
                    "performance_improvement": "+23.4%"
                }
            }
        }


class ErrorResponse(BaseModel):
    """Standard error response"""
    status: str = "error"
    message: str
    error_code: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": "error",
                "message": "Invalid input file format",
                "error_code": "INVALID_FILE_FORMAT",
                "details": {
                    "file_path": "/path/to/invalid.json",
                    "line_number": 5,
                    "parse_error": "Invalid JSON syntax"
                }
            }
        }


class HealthResponse(BaseModel):
    """Health check response"""
    status: str = "healthy"
    timestamp: str
    version: str = "1.0.0"
    services: Dict[str, str] = {}
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": "healthy",
                "timestamp": "2025-01-01T12:00:00Z",
                "version": "1.0.0",
                "services": {
                    "llm_client": "connected",
                    "vector_integration": "available",
                    "token_protection": "active"
                }
            }
        }