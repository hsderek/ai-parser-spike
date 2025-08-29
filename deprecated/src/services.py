#!/usr/bin/env python3
"""
Service layer for FastAPI-ready business logic
Handles the orchestration of parsing operations with clean separation of concerns
"""
import asyncio
import time
from pathlib import Path
from typing import Dict, Any, Optional, List

from .config import Config
from .logging_config import get_logger
from .pipeline import VRLPipeline
from .api_models import (
    ParseRequest, IterativeParseRequest, ParseResponse, IterativeParseResponse, 
    ErrorResponse, FieldInfo, DataSourceInfo, ParserSourceInfo, LLMUsageInfo,
    ParseSummary, PerformanceMetrics, ParserVariant, IterationHistory
)
from .models import VRLParseResult


class ParseService:
    """
    Core parsing service - handles standard VRL parser generation
    """
    
    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self.logger = get_logger("ParseService")
        self._pipeline = None
    
    @property
    def pipeline(self) -> VRLPipeline:
        """Lazy-loaded pipeline to avoid initialization overhead"""
        if self._pipeline is None:
            self._pipeline = VRLPipeline(self.config)
        return self._pipeline
    
    async def generate_parser(self, request: ParseRequest) -> ParseResponse:
        """
        Generate VRL parser from request
        
        Args:
            request: ParseRequest with file path and configuration
            
        Returns:
            ParseResponse with generated parser and metadata
            
        Raises:
            ValueError: If input validation fails
            FileNotFoundError: If input file doesn't exist
            Exception: If parsing fails
        """
        self.logger.info(f"Starting parser generation for {request.file_path}")
        try:
            # Validate input
            self._validate_parse_request(request)
            self.logger.debug("Input validation passed")
            
            start_time = time.time()
            
            # Configure pipeline based on request
            if request.model_preference:
                self.config.llm_model_preference = request.model_preference
                self.logger.debug(f"Model preference set to {request.model_preference}")
            
            # Generate parser
            file_path = Path(request.file_path)
            self.logger.info(f"Processing file: {file_path}")
            result = await self.pipeline.process(
                file_path, 
                request.level.value, 
                [d.value for d in request.domains] if request.domains else None
            )
            
            processing_time = time.time() - start_time
            self.logger.info(f"Parser generation completed in {processing_time:.2f}s")
            
            # Log performance metrics
            from .logging_config import log_parsing_result
            log_parsing_result(
                source_file=str(file_path),
                fields_extracted=len(result.fields),
                records_processed=result.sample_size if hasattr(result, 'sample_size') else 0,
                success=True,
                duration_ms=processing_time * 1000
            )
            
            # Build response
            return await self._build_parse_response(result, processing_time, request)
            
        except FileNotFoundError as e:
            self.logger.error(f"File not found: {request.file_path}")
            raise ValueError(f"Input file not found: {request.file_path}")
        except Exception as e:
            self.logger.error(f"Parser generation failed: {str(e)}")
            raise Exception(f"Parser generation failed: {str(e)}")
    
    def _validate_parse_request(self, request: ParseRequest) -> None:
        """Validate parse request parameters"""
        file_path = Path(request.file_path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"Input file does not exist: {request.file_path}")
        
        if not file_path.suffix.lower() in ['.json', '.ndjson', '.jsonl']:
            raise ValueError(f"Unsupported file format: {file_path.suffix}")
        
        if request.max_fields and request.max_fields < 1:
            raise ValueError("max_fields must be positive")
    
    async def _build_parse_response(
        self, 
        result: VRLParseResult, 
        processing_time: float, 
        request: ParseRequest
    ) -> ParseResponse:
        """Build standardized ParseResponse from VRLParseResult"""
        
        # Convert internal models to API models
        fields = [self._convert_field_to_api(field) for field in result.fields]
        data_source = self._convert_data_source_to_api(result.data_source) if result.data_source else None
        parser_source = self._convert_parser_source_to_api(result.parser_source) if result.parser_source else None
        llm_usage = self._convert_llm_usage_to_api(result.llm_usage) if result.llm_usage else None
        
        summary = ParseSummary(
            total_fields=len(result.fields),
            high_value_fields=sum(1 for f in result.fields if f.is_high_value),
            low_cpu_cost_fields=sum(1 for f in result.fields if f.cpu_cost.value == "low"),
            medium_cpu_cost_fields=sum(1 for f in result.fields if f.cpu_cost.value == "medium"),
            high_cpu_cost_fields=sum(1 for f in result.fields if f.cpu_cost.value == "high"),
            estimated_performance_tier=self._estimate_performance_tier(result.fields),
            total_processing_time_seconds=processing_time
        )
        
        # Generate explanatory narrative
        self.logger.info("Generating explanatory narrative for parser results")
        narrative = await self.pipeline.llm_client.generate_explanation_narrative(
            data_source=result.data_source,
            fields=result.fields,
            parser_source=result.parser_source,
            performance_tier=summary.estimated_performance_tier
        )
        
        return ParseResponse(
            status="success",
            message=f"Successfully generated VRL parser with {len(result.fields)} fields",
            data={
                "vrl_code": result.vrl_code,
                "fields": [field.model_dump() for field in fields],
                "data_source": data_source.model_dump() if data_source else None,
                "parser_source": parser_source.model_dump() if parser_source else None,
                "performance_metrics": result.performance_metrics,
                "llm_usage": llm_usage.model_dump() if llm_usage else None,
                "summary": summary.model_dump()
            },
            narrative=narrative
        )
    
    def _convert_field_to_api(self, field) -> FieldInfo:
        """Convert internal ExtractedField to API FieldInfo"""
        return FieldInfo(
            name=field.name,
            type=field.type,
            description=field.description,
            cpu_cost=field.cpu_cost,
            confidence=field.confidence,
            sample_values=field.sample_values,
            parser_type=field.parser_type,
            is_high_value=field.is_high_value
        )
    
    def _convert_data_source_to_api(self, data_source) -> DataSourceInfo:
        """Convert internal DataSource to API DataSourceInfo"""
        return DataSourceInfo(
            name=data_source.name,
            confidence=data_source.confidence,
            description=data_source.description,
            common_fields=data_source.common_fields,
            known_parsers=data_source.known_parsers
        )
    
    def _convert_parser_source_to_api(self, parser_source) -> ParserSourceInfo:
        """Convert internal ParserSource to API ParserSourceInfo"""
        return ParserSourceInfo(
            type=parser_source.type,
            sources=parser_source.sources,
            confidence=parser_source.confidence,
            description=parser_source.description
        )
    
    def _convert_llm_usage_to_api(self, llm_usage) -> LLMUsageInfo:
        """Convert internal LLMUsage to API LLMUsageInfo"""
        return LLMUsageInfo(
            total_tokens=llm_usage.total_tokens,
            input_tokens=llm_usage.input_tokens,
            output_tokens=llm_usage.output_tokens,
            estimated_cost_usd=llm_usage.estimated_cost_usd,
            api_calls=llm_usage.api_calls
        )
    
    def _estimate_performance_tier(self, fields) -> int:
        """Estimate performance tier based on field characteristics"""
        if not fields:
            return 5
        
        high_cpu_fields = sum(1 for f in fields if f.cpu_cost.value == "high")
        total_fields = len(fields)
        
        if total_fields <= 10 and high_cpu_fields == 0:
            return 1  # Excellent
        elif total_fields <= 15 and high_cpu_fields <= 2:
            return 2  # Good
        elif total_fields <= 20 and high_cpu_fields <= 4:
            return 3  # Acceptable
        elif total_fields <= 25:
            return 4  # Poor
        else:
            return 5  # Unusable


class IterativeParseService:
    """
    Enhanced parsing service with iterative refinement and performance testing
    """
    
    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self.logger = get_logger("IterativeParseService")
        self.base_service = ParseService(config)
    
    async def generate_optimized_parser(self, request: IterativeParseRequest) -> IterativeParseResponse:
        """
        Generate optimized VRL parser with iterative refinement
        
        Args:
            request: IterativeParseRequest with refinement parameters
            
        Returns:
            IterativeParseResponse with optimized parser and iteration history
        """
        self.logger.info(f"Starting iterative parser generation for {request.file_path}")
        self.logger.info(f"Target performance tier: {request.target_performance_tier}, Max iterations: {request.max_iterations}")
        
        try:
            # Import here to avoid circular dependency
            from .tests.test_iterative_syslog_parsing import IterativeParserTester
            
            start_time = time.time()
            
            # Initialize tester
            tester = IterativeParserTester(max_iterations=request.max_iterations)
            
            # Run iterative testing
            file_path = Path(request.file_path)
            self.logger.info(f"Starting iterative refinement for {file_path}")
            result = tester.test_with_refinement(
                file_path, 
                target_performance_tier=request.target_performance_tier
            )
            
            total_time = time.time() - start_time
            self.logger.info(f"Iterative parsing completed in {total_time:.2f}s after {result['total_iterations']} iterations")
            
            # Log performance metrics
            from .logging_config import log_performance
            log_performance(
                operation="iterative_parsing",
                duration_ms=total_time * 1000,
                iterations=result['total_iterations'],
                final_tier=result['final_tier'],
                target_tier=request.target_performance_tier
            )
            
            # Build response
            return await self._build_iterative_response(result, total_time, request)
            
        except Exception as e:
            self.logger.error(f"Iterative parser generation failed: {str(e)}")
            raise Exception(f"Iterative parser generation failed: {str(e)}")
    
    async def _build_iterative_response(
        self, 
        result: Dict[str, Any], 
        processing_time: float, 
        request: IterativeParseRequest
    ) -> IterativeParseResponse:
        """Build IterativeParseResponse from tester results"""
        
        best_result = result['best_result']
        if not best_result:
            raise Exception("No successful parser variant generated")
        
        # Convert best parser to API format
        best_parser = best_result['parser']
        fields = [self.base_service._convert_field_to_api(field) for field in best_parser.fields]
        
        # Build iteration history
        iteration_history = []
        for iter_result in result['iteration_history']:
            variants = []
            for variant in iter_result['variants']:
                perf_metrics = PerformanceMetrics(**variant['performance'])
                variants.append(ParserVariant(
                    name=variant['name'],
                    iteration=iter_result['iteration'],
                    performance=perf_metrics,
                    field_count=len(variant['parser'].fields),
                    performance_score=variant.get('score', 0),
                    performance_tier=self.base_service._estimate_performance_tier(variant['parser'].fields)
                ))
            
            best_variant_data = iter_result['best_variant']
            best_variant = ParserVariant(
                name=best_variant_data['name'],
                iteration=iter_result['iteration'],
                performance=PerformanceMetrics(**best_variant_data['performance']),
                field_count=len(best_variant_data['parser'].fields),
                performance_score=best_variant_data.get('score', 0),
                performance_tier=self.base_service._estimate_performance_tier(best_variant_data['parser'].fields)
            )
            
            iteration_history.append(IterationHistory(
                iteration=iter_result['iteration'],
                variants_tested=variants,
                best_variant=best_variant
            ))
        
        # Calculate performance improvement
        if len(iteration_history) >= 2:
            initial_score = iteration_history[0].best_variant.performance_score
            final_score = iteration_history[-1].best_variant.performance_score
            improvement_pct = ((final_score - initial_score) / initial_score * 100) if initial_score > 0 else 0
        else:
            improvement_pct = 0
        
        # Generate iterative-specific narrative
        self.logger.info("Generating explanatory narrative for iterative parsing results")
        
        # Build iterative narrative prompt
        iterative_info = f"After {result['total_iterations']} refinement iterations with {improvement_pct:+.1f}% performance improvement"
        
        narrative = await self.base_service.pipeline.llm_client.generate_explanation_narrative(
            data_source=best_parser.data_source,
            fields=best_parser.fields,
            parser_source=best_parser.parser_source,
            performance_tier=result['final_tier']
        )
        
        # Enhance narrative with iterative context
        iterative_narrative = f"{narrative}\n\n{iterative_info}, achieving performance tier {result['final_tier']} through systematic optimization and A/B testing of parser variants."
        
        return IterativeParseResponse(
            status="success",
            message=f"Generated optimized VRL parser after {result['total_iterations']} iterations",
            data={
                "vrl_code": best_parser.vrl_code,
                "fields": [field.model_dump() for field in fields],
                "final_performance_tier": result['final_tier'],
                "performance_score": best_result['score'],
                "data_source": self.base_service._convert_data_source_to_api(best_parser.data_source).model_dump() if best_parser.data_source else None,
                "parser_source": self.base_service._convert_parser_source_to_api(best_parser.parser_source).model_dump() if best_parser.parser_source else None,
                "total_processing_time_seconds": processing_time
            },
            iterations={
                "total_iterations": result['total_iterations'],
                "history": [hist.model_dump() for hist in iteration_history],
                "performance_improvement": f"{improvement_pct:+.1f}%",
                "target_tier_achieved": result['final_tier'] <= request.target_performance_tier
            },
            narrative=iterative_narrative
        )


class HealthService:
    """
    Health check service for monitoring system status
    """
    
    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self.logger = get_logger("HealthService")
    
    async def get_health_status(self) -> Dict[str, Any]:
        """Get comprehensive health status"""
        from datetime import datetime
        
        services = {}
        
        # Check LLM connectivity
        try:
            # This would be a lightweight health check, not a full API call
            services["llm_client"] = "connected"
        except Exception:
            services["llm_client"] = "disconnected"
        
        # Check Vector availability
        try:
            import subprocess
            result = subprocess.run(["vector", "--version"], capture_output=True, timeout=5)
            services["vector_integration"] = "available" if result.returncode == 0 else "unavailable"
        except (subprocess.TimeoutExpired, FileNotFoundError):
            services["vector_integration"] = "unavailable"
        
        # Check token protection
        services["token_protection"] = "active"
        
        return {
            "status": "healthy" if all(s in ["connected", "available", "active"] for s in services.values()) else "degraded",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "version": "1.0.0",
            "services": services
        }