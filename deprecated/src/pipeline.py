import json
import asyncio
from pathlib import Path
from typing import List, Optional, Dict, Any
from rich.console import Console

from .config import Config
from .logging_config import get_logger
from .models import VRLParseResult, ExtractedField, SampleData, DataSource, ParserSource
from .analyzer import DataAnalyzer
from .llm_client import LLMClient
from .vrl_generator import VRLGenerator
from .performance import PerformanceOptimizer

console = Console()


class VRLPipeline:
    def __init__(self, config: Config):
        self.config = config
        self.logger = get_logger("VRLPipeline")
        self.analyzer = DataAnalyzer(config)
        self.llm_client = LLMClient(config)
        self.vrl_generator = VRLGenerator(config)
        self.optimizer = PerformanceOptimizer(config)
    
    async def process(self, input_file: Path, level: str, domains: Optional[List[str]] = None) -> VRLParseResult:
        self.logger.info(f"Starting VRL processing pipeline for {input_file}")
        
        console.print("[dim]Step 1: Loading and analyzing sample data...[/dim]")
        self.logger.debug("Step 1: Loading sample data")
        sample_data = self._load_sample_data(input_file)
        
        console.print("[dim]Step 2: Identifying data source...[/dim]")
        self.logger.debug("Step 2: Identifying data source")
        data_source = await self._identify_data_source(sample_data)
        
        console.print("[dim]Step 3: Extracting field candidates...[/dim]")
        self.logger.debug(f"Step 3: Extracting fields for level={level}, domains={domains}")
        field_candidates = self._extract_field_candidates(sample_data, level, domains)
        
        console.print("[dim]Step 4: Researching existing parsers...[/dim]")
        self.logger.debug("Step 4: Researching existing parsers")
        parser_research = await self._research_parsers(data_source, field_candidates)
        
        console.print("[dim]Step 5: Generating VRL code...[/dim]")
        self.logger.debug("Step 5: Generating VRL code")
        vrl_code = self.vrl_generator.generate(field_candidates, parser_research)
        
        console.print("[dim]Step 6: Optimizing performance...[/dim]")
        self.logger.debug("Step 6: Optimizing performance")
        optimized_vrl = self.optimizer.optimize(vrl_code, field_candidates)
        
        console.print("[dim]Step 7: Final validation...[/dim]")
        self.logger.debug("Step 7: Final validation")
        validated_fields = self._validate_fields(optimized_vrl, field_candidates)
        
        # Extract parser source from research
        parser_source = parser_research.get('parser_source') if parser_research else None
        
        self.logger.info(f"Pipeline completed successfully - generated {len(validated_fields)} fields")
        
        return VRLParseResult(
            vrl_code=optimized_vrl,
            fields=validated_fields,
            data_source=data_source,
            performance_metrics={},
            test_results={},
            llm_usage=self.llm_client.get_usage(),
            parser_source=parser_source
        )
    
    def _load_sample_data(self, input_file: Path) -> SampleData:
        self.logger.info(f"Loading sample data from {input_file}")
        
        with open(input_file, 'r') as f:
            lines = f.readlines()
        
        samples = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                samples.append(json.loads(line))
            except json.JSONDecodeError:
                self.logger.warning(f"Failed to parse JSON line: {line[:100]}...")
                continue
        
        if not samples:
            raise ValueError("No valid JSON objects found in file")
        
        self.logger.info(f"Loaded {len(samples)} valid JSON samples")
        
        return self.analyzer.analyze_samples(samples)
    
    async def _identify_data_source(self, sample_data: SampleData) -> Optional[DataSource]:
        return await self.llm_client.identify_data_source(sample_data)
    
    def _extract_field_candidates(self, sample_data: SampleData, level: str, domains: Optional[List[str]]) -> List[ExtractedField]:
        return self.analyzer.extract_field_candidates(sample_data, level, domains)
    
    async def _research_parsers(self, data_source: Optional[DataSource], fields: List[ExtractedField]) -> Dict[str, Any]:
        return await self.llm_client.research_parsers(data_source, fields)
    
    def _validate_fields(self, vrl_code: str, field_candidates: List[ExtractedField]) -> List[ExtractedField]:
        return field_candidates