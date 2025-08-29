#!/usr/bin/env python3
"""
FastAPI-ready route definitions
Organized for easy conversion to actual FastAPI endpoints
"""
from typing import Dict, Any
import logging

from .api_models import (
    ParseRequest, IterativeParseRequest, ParseResponse, IterativeParseResponse, 
    ErrorResponse, HealthResponse
)
from .services import ParseService, IterativeParseService, HealthService
from .config import Config

# Setup logging
logger = logging.getLogger(__name__)


class VRLParserRoutes:
    """
    Route handler class that mimics FastAPI router structure
    This can be easily converted to actual FastAPI routes
    """
    
    def __init__(self, config: Config = None):
        self.config = config or Config()
        self.parse_service = ParseService(self.config)
        self.iterative_service = IterativeParseService(self.config)
        self.health_service = HealthService(self.config)
    
    # Standard parsing endpoints
    async def parse_logs(self, request: ParseRequest) -> ParseResponse | ErrorResponse:
        """
        Generate VRL parser from log samples
        
        POST /api/v1/parse
        """
        try:
            logger.info(f"Processing parse request for file: {request.file_path}")
            result = await self.parse_service.generate_parser(request)
            logger.info(f"Successfully generated parser with {len(result.data['fields'])} fields")
            return result
            
        except ValueError as e:
            logger.error(f"Validation error: {str(e)}")
            return ErrorResponse(
                message=str(e),
                error_code="VALIDATION_ERROR",
                details={"request": request.dict()}
            )
        except FileNotFoundError as e:
            logger.error(f"File not found: {str(e)}")
            return ErrorResponse(
                message=str(e),
                error_code="FILE_NOT_FOUND",
                details={"file_path": request.file_path}
            )
        except Exception as e:
            logger.error(f"Unexpected error in parse_logs: {str(e)}")
            return ErrorResponse(
                message="Internal server error during parser generation",
                error_code="INTERNAL_ERROR",
                details={"error": str(e)}
            )
    
    async def parse_logs_iterative(self, request: IterativeParseRequest) -> IterativeParseResponse | ErrorResponse:
        """
        Generate optimized VRL parser with iterative refinement
        
        POST /api/v1/parse/iterative
        """
        try:
            logger.info(f"Processing iterative parse request for file: {request.file_path}")
            logger.info(f"Max iterations: {request.max_iterations}, Target tier: {request.target_performance_tier}")
            
            result = await self.iterative_service.generate_optimized_parser(request)
            
            logger.info(f"Iterative parsing completed in {result.iterations['total_iterations']} iterations")
            logger.info(f"Final performance tier: {result.data['final_performance_tier']}")
            
            return result
            
        except ValueError as e:
            logger.error(f"Validation error in iterative parsing: {str(e)}")
            return ErrorResponse(
                message=str(e),
                error_code="VALIDATION_ERROR",
                details={"request": request.dict()}
            )
        except Exception as e:
            logger.error(f"Unexpected error in parse_logs_iterative: {str(e)}")
            return ErrorResponse(
                message="Internal server error during iterative parser generation",
                error_code="INTERNAL_ERROR",
                details={"error": str(e)}
            )
    
    # Utility endpoints
    async def health_check(self) -> HealthResponse:
        """
        Health check endpoint
        
        GET /api/v1/health
        """
        try:
            health_data = await self.health_service.get_health_status()
            return HealthResponse(**health_data)
        except Exception as e:
            logger.error(f"Health check failed: {str(e)}")
            return HealthResponse(
                status="unhealthy",
                timestamp="",
                services={"error": str(e)}
            )
    
    async def get_supported_formats(self) -> Dict[str, Any]:
        """
        Get list of supported log formats and data sources
        
        GET /api/v1/formats
        """
        return {
            "status": "success",
            "data": {
                "supported_formats": [".json", ".ndjson", ".jsonl"],
                "supported_domains": ["cyber", "travel", "iot", "defence", "financial"],
                "parsing_levels": ["low", "medium", "high"],
                "common_data_sources": [
                    "Apache Access Logs",
                    "NGINX Logs", 
                    "Kubernetes Logs",
                    "Syslog (RFC 3164/5424)",
                    "AWS CloudTrail",
                    "Docker Container Logs",
                    "Application JSON Logs"
                ]
            }
        }
    
    async def validate_file(self, file_path: str) -> Dict[str, Any]:
        """
        Validate input file format and structure
        
        POST /api/v1/validate
        """
        try:
            from pathlib import Path
            import json
            
            path = Path(file_path)
            
            if not path.exists():
                return ErrorResponse(
                    message="File not found",
                    error_code="FILE_NOT_FOUND",
                    details={"file_path": file_path}
                ).dict()
            
            # Sample file validation
            valid_lines = 0
            total_lines = 0
            sample_fields = set()
            
            with open(path, 'r') as f:
                for line_num, line in enumerate(f):
                    total_lines += 1
                    if total_lines > 100:  # Limit validation to first 100 lines
                        break
                    
                    try:
                        data = json.loads(line.strip())
                        if isinstance(data, dict):
                            valid_lines += 1
                            sample_fields.update(data.keys())
                    except json.JSONDecodeError:
                        continue
            
            validity_ratio = valid_lines / total_lines if total_lines > 0 else 0
            
            return {
                "status": "success" if validity_ratio >= 0.8 else "warning",
                "data": {
                    "file_path": file_path,
                    "total_lines": total_lines,
                    "valid_json_lines": valid_lines,
                    "validity_ratio": validity_ratio,
                    "sample_fields": list(sample_fields)[:20],  # Limit to first 20 fields
                    "estimated_parseable": validity_ratio >= 0.5,
                    "recommendations": self._get_validation_recommendations(validity_ratio, sample_fields)
                }
            }
            
        except Exception as e:
            logger.error(f"File validation error: {str(e)}")
            return ErrorResponse(
                message="File validation failed",
                error_code="VALIDATION_ERROR",
                details={"error": str(e)}
            ).dict()
    
    def _get_validation_recommendations(self, validity_ratio: float, fields: set) -> list:
        """Generate validation recommendations"""
        recommendations = []
        
        if validity_ratio < 0.5:
            recommendations.append("File contains many invalid JSON lines. Consider cleaning the data first.")
        elif validity_ratio < 0.8:
            recommendations.append("File contains some invalid JSON lines. Parser generation may skip invalid entries.")
        
        if len(fields) > 50:
            recommendations.append("File contains many fields. Consider using 'high' parsing level for comprehensive extraction.")
        elif len(fields) < 5:
            recommendations.append("File contains few fields. Consider using 'low' parsing level for efficiency.")
        
        # Check for common high-value fields
        high_value_fields = {"timestamp", "message", "level", "error", "user", "ip", "host"}
        if high_value_fields.intersection(fields):
            recommendations.append("Detected high-value fields for log analysis. Good candidate for parsing.")
        
        return recommendations


# Example of how this would be converted to actual FastAPI:
"""
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

app = FastAPI(title="VRL Parser Generator API", version="1.0.0")

# Initialize routes
routes = VRLParserRoutes()

@app.post("/api/v1/parse", response_model=ParseResponse)
async def parse_logs_endpoint(request: ParseRequest):
    result = await routes.parse_logs(request)
    if isinstance(result, ErrorResponse):
        raise HTTPException(status_code=400, detail=result.dict())
    return result

@app.post("/api/v1/parse/iterative", response_model=IterativeParseResponse)  
async def parse_logs_iterative_endpoint(request: IterativeParseRequest):
    result = await routes.parse_logs_iterative(request)
    if isinstance(result, ErrorResponse):
        raise HTTPException(status_code=400, detail=result.dict())
    return result

@app.get("/api/v1/health", response_model=HealthResponse)
async def health_check_endpoint():
    return await routes.health_check()

@app.get("/api/v1/formats")
async def get_supported_formats_endpoint():
    return await routes.get_supported_formats()

@app.post("/api/v1/validate")
async def validate_file_endpoint(file_path: str):
    return await routes.validate_file(file_path)
"""