#!/usr/bin/env python3
"""
Token-Aware Context Manager for VRL Development

Provides focused, token-efficient context for different types of LLM requests
instead of dumping all available context. Prevents token waste and LLM confusion.

Context Selection Strategies:
- VRL Creation: Rules + sample patterns + field types
- Performance Debug: Metrics + optimization guides + system info  
- Validation Debug: Errors + syntax rules + current code
- General Help: Summaries + available actions

Token Management:
- Max context limits per request type
- Dynamic content selection based on relevance
- Smart truncation with priority ordering
- Token estimation and budget allocation
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
from loguru import logger


class RequestType(Enum):
    """Types of user requests for context selection"""
    CREATE_VRL = "create_vrl"
    DEBUG_PERFORMANCE = "debug_performance" 
    DEBUG_VALIDATION = "debug_validation"
    OPTIMIZE_VRL = "optimize_vrl"
    GENERAL_HELP = "general_help"
    ANALYZE_SAMPLES = "analyze_samples"


@dataclass
class ContextBudget:
    """Token budget allocation for different context components"""
    max_total_tokens: int = 8000
    external_configs: int = 3000
    sample_data: int = 1500
    iteration_history: int = 2000
    system_info: int = 500
    conversation_context: int = 1000


@dataclass 
class ContextComponent:
    """Individual context component with priority and content"""
    name: str
    content: str
    priority: int  # 1=highest, 5=lowest
    estimated_tokens: int
    component_type: str


class TokenAwareContextManager:
    """Smart context management with token awareness and request-specific focus"""
    
    def __init__(self, external_configs_dir: str = "external"):
        self.external_configs_dir = Path(external_configs_dir)
        self.external_configs = {}
        self.sample_analysis = {}
        self.system_info = {}
        self.vrl_iterations = []
        self.conversation_history = []
        
        # Load and parse external configs
        self._load_and_parse_external_configs()
        
        logger.info("🎯 Token-aware context manager initialized")
        logger.info(f"📁 External configs parsed: {list(self.external_configs.keys())}")
    
    def get_focused_context(self, user_request: str, request_type: Optional[RequestType] = None, 
                          budget: Optional[ContextBudget] = None) -> str:
        """Generate focused context based on user request type and token budget"""
        
        # Auto-detect request type if not provided
        if not request_type:
            request_type = self._classify_request(user_request)
        
        # Use default budget if not provided
        if not budget:
            budget = ContextBudget()
        
        logger.info(f"🎯 Building focused context for {request_type.value}")
        logger.info(f"💰 Token budget: {budget.max_total_tokens} tokens")
        
        # Build context components based on request type
        components = self._build_context_components(request_type, budget)
        
        # Select and prioritize components within budget
        selected_components = self._select_components_within_budget(components, budget)
        
        # Assemble final context
        context_parts = []
        context_parts.append(f"# Focused VRL Context - {request_type.value.replace('_', ' ').title()}")
        context_parts.append(f"Request: {user_request[:100]}...")
        context_parts.append("")
        
        total_tokens = 0
        for component in selected_components:
            context_parts.append(f"## {component.name}")
            context_parts.append(component.content)
            context_parts.append("")
            total_tokens += component.estimated_tokens
        
        context_parts.append(f"---")
        context_parts.append(f"Context optimized for {request_type.value} • {total_tokens} estimated tokens")
        
        final_context = "\n".join(context_parts)
        
        logger.info(f"✅ Context built: {len(selected_components)} components, ~{total_tokens} tokens")
        return final_context
    
    def _classify_request(self, user_request: str) -> RequestType:
        """Automatically classify user request type for context selection"""
        request_lower = user_request.lower()
        
        # VRL creation keywords
        if any(word in request_lower for word in ['create', 'generate', 'write', 'build', 'make']):
            if any(word in request_lower for word in ['vrl', 'parser', 'transform']):
                return RequestType.CREATE_VRL
        
        # Performance debugging keywords
        if any(word in request_lower for word in ['slow', 'performance', 'cpu', 'optimize', 'speed', 'faster']):
            return RequestType.DEBUG_PERFORMANCE
        
        # Validation debugging keywords  
        if any(word in request_lower for word in ['error', 'fail', 'broke', 'invalid', 'syntax', 'debug']):
            return RequestType.DEBUG_VALIDATION
        
        # Optimization keywords
        if any(word in request_lower for word in ['optimize', 'improve', 'faster', 'better', 'efficient']):
            return RequestType.OPTIMIZE_VRL
        
        # Sample analysis keywords
        if any(word in request_lower for word in ['analyze', 'understand', 'examine', 'sample', 'data']):
            return RequestType.ANALYZE_SAMPLES
        
        # Default to general help
        return RequestType.GENERAL_HELP
    
    def _build_context_components(self, request_type: RequestType, budget: ContextBudget) -> List[ContextComponent]:
        """Build context components based on request type with priority ordering"""
        components = []
        
        if request_type == RequestType.CREATE_VRL:
            # Priority 1: VRL system rules (essential)
            if 'vector_vrl_system' in self.external_configs:
                vrl_rules = self._extract_vrl_creation_rules()
                components.append(ContextComponent(
                    name="VRL Creation Rules",
                    content=vrl_rules,
                    priority=1,
                    estimated_tokens=self._estimate_tokens(vrl_rules),
                    component_type="vrl_rules"
                ))
            
            # Priority 2: Sample patterns (essential for parsing logic)
            if self.sample_analysis:
                sample_patterns = self._extract_sample_patterns()
                components.append(ContextComponent(
                    name="Sample Data Patterns",
                    content=sample_patterns,
                    priority=2,
                    estimated_tokens=self._estimate_tokens(sample_patterns),
                    component_type="sample_data"
                ))
            
            # Priority 3: Field type mappings (helpful)
            if 'type_maps' in self.external_configs:
                type_maps = self._extract_relevant_type_maps()
                components.append(ContextComponent(
                    name="Field Type Mappings",
                    content=type_maps,
                    priority=3,
                    estimated_tokens=self._estimate_tokens(type_maps),
                    component_type="type_maps"
                ))
            
            # Priority 4: Successful patterns from history (helpful)
            if self.vrl_iterations:
                success_patterns = self._extract_successful_patterns()
                components.append(ContextComponent(
                    name="Previously Successful Patterns",
                    content=success_patterns,
                    priority=4,
                    estimated_tokens=self._estimate_tokens(success_patterns),
                    component_type="history"
                ))
        
        elif request_type == RequestType.DEBUG_PERFORMANCE:
            # Priority 1: Performance data (essential)
            perf_data = self._extract_performance_data()
            components.append(ContextComponent(
                name="Performance Baselines",
                content=perf_data,
                priority=1,
                estimated_tokens=self._estimate_tokens(perf_data),
                component_type="performance"
            ))
            
            # Priority 2: Optimization guides (essential)
            if 'vector_vrl_system' in self.external_configs:
                opt_guides = self._extract_optimization_guides()
                components.append(ContextComponent(
                    name="Performance Optimization Guides", 
                    content=opt_guides,
                    priority=2,
                    estimated_tokens=self._estimate_tokens(opt_guides),
                    component_type="optimization"
                ))
            
            # Priority 3: System info (helpful)
            if self.system_info:
                sys_info = self._format_system_info()
                components.append(ContextComponent(
                    name="System Performance Context",
                    content=sys_info,
                    priority=3,
                    estimated_tokens=self._estimate_tokens(sys_info),
                    component_type="system"
                ))
        
        elif request_type == RequestType.DEBUG_VALIDATION:
            # Priority 1: Recent errors (essential)
            if self.vrl_iterations:
                recent_errors = self._extract_recent_errors()
                components.append(ContextComponent(
                    name="Recent Validation Errors",
                    content=recent_errors,
                    priority=1,
                    estimated_tokens=self._estimate_tokens(recent_errors),
                    component_type="errors"
                ))
            
            # Priority 2: VRL syntax rules (essential)
            if 'vector_vrl_system' in self.external_configs:
                syntax_rules = self._extract_syntax_rules()
                components.append(ContextComponent(
                    name="VRL Syntax Rules",
                    content=syntax_rules,
                    priority=2,
                    estimated_tokens=self._estimate_tokens(syntax_rules),
                    component_type="syntax"
                ))
            
            # Priority 3: Current iteration context (helpful)
            if self.vrl_iterations:
                current_context = self._extract_current_iteration_context()
                components.append(ContextComponent(
                    name="Current Iteration Context",
                    content=current_context,
                    priority=3,
                    estimated_tokens=self._estimate_tokens(current_context),
                    component_type="current"
                ))
        
        # Add more request types as needed...
        
        return components
    
    def _select_components_within_budget(self, components: List[ContextComponent], 
                                       budget: ContextBudget) -> List[ContextComponent]:
        """Select components that fit within token budget, prioritizing by importance"""
        
        # Sort by priority (1=highest priority first)
        components_sorted = sorted(components, key=lambda x: x.priority)
        
        selected = []
        total_tokens = 0
        
        for component in components_sorted:
            if total_tokens + component.estimated_tokens <= budget.max_total_tokens:
                selected.append(component)
                total_tokens += component.estimated_tokens
                logger.debug(f"✓ Selected {component.name} ({component.estimated_tokens} tokens)")
            else:
                logger.debug(f"✗ Skipped {component.name} (would exceed budget)")
        
        return selected
    
    def _load_and_parse_external_configs(self):
        """Load and parse external config files into searchable structures"""
        try:
            # Load vector-vrl-system.md
            vrl_system_file = self.external_configs_dir / "vector-vrl-system.md"
            if vrl_system_file.exists():
                with open(vrl_system_file, 'r') as f:
                    content = f.read()
                    self.external_configs['vector_vrl_system'] = self._parse_vrl_system_md(content)
                logger.info(f"✓ Parsed vector-vrl-system.md")
            
            # Load parser-system-prompts.md
            parser_prompts_file = self.external_configs_dir / "parser-system-prompts.md"
            if parser_prompts_file.exists():
                with open(parser_prompts_file, 'r') as f:
                    content = f.read()
                    self.external_configs['parser_prompts'] = self._parse_parser_prompts_md(content)
                logger.info(f"✓ Parsed parser-system-prompts.md")
            
            # Load type_maps.csv
            type_maps_file = self.external_configs_dir / "type_maps.csv"
            if type_maps_file.exists():
                with open(type_maps_file, 'r') as f:
                    content = f.read()
                    self.external_configs['type_maps'] = self._parse_type_maps_csv(content)
                logger.info(f"✓ Parsed type_maps.csv")
            
        except Exception as e:
            logger.error(f"Failed to parse external configs: {e}")
    
    def _parse_vrl_system_md(self, content: str) -> Dict[str, str]:
        """Parse VRL system markdown into searchable sections"""
        sections = {}
        
        # Split by headers and extract key sections
        lines = content.split('\n')
        current_section = None
        current_content = []
        
        for line in lines:
            if line.startswith('#'):
                # Save previous section
                if current_section and current_content:
                    sections[current_section] = '\n'.join(current_content).strip()
                
                # Start new section
                current_section = line.strip('#').strip().lower().replace(' ', '_')
                current_content = []
            else:
                current_content.append(line)
        
        # Save final section
        if current_section and current_content:
            sections[current_section] = '\n'.join(current_content).strip()
        
        return sections
    
    def _parse_parser_prompts_md(self, content: str) -> Dict[str, str]:
        """Parse parser prompts markdown into searchable sections"""
        # Similar parsing logic to VRL system
        return {"content": content}  # Simplified for now
    
    def _parse_type_maps_csv(self, content: str) -> Dict[str, List[Dict[str, str]]]:
        """Parse type maps CSV into structured data"""
        parsed = {"mappings": []}
        
        lines = content.strip().split('\n')
        if not lines:
            return parsed
        
        # Assume first line is header
        headers = [h.strip() for h in lines[0].split(',')]
        
        for line in lines[1:]:
            if line.strip() and not line.startswith('#'):
                values = [v.strip() for v in line.split(',')]
                if len(values) == len(headers):
                    mapping = dict(zip(headers, values))
                    parsed["mappings"].append(mapping)
        
        return parsed
    
    def _extract_vrl_creation_rules(self) -> str:
        """Extract essential VRL creation rules from parsed config"""
        if 'vector_vrl_system' not in self.external_configs:
            return "No VRL system rules available"
        
        vrl_config = self.external_configs['vector_vrl_system']
        essential_sections = []
        
        # Extract key sections for VRL creation
        for section_key in ['constraints', 'performance_requirements', 'syntax_rules', 'string_operations']:
            if section_key in vrl_config:
                essential_sections.append(f"### {section_key.replace('_', ' ').title()}")
                essential_sections.append(vrl_config[section_key])
                essential_sections.append("")
        
        return '\n'.join(essential_sections) if essential_sections else "VRL rules not found"
    
    def _extract_sample_patterns(self) -> str:
        """Extract sample data patterns in compressed format (manual pattern recognition)"""
        if not self.sample_analysis:
            return "No sample analysis available"
        
        patterns = []
        patterns.append("### Sample Data Patterns")
        
        # Basic field analysis
        if 'common_fields' in self.sample_analysis:
            fields = self.sample_analysis['common_fields'][:8]  # Limit to 8 most common
            patterns.append(f"**Common Fields:** {', '.join(fields)}")
        
        # Delimiter analysis 
        if 'delimiters_found' in self.sample_analysis:
            delims = list(self.sample_analysis['delimiters_found'])[:5]  # Max 5 delimiters
            patterns.append(f"**Delimiters Found:** {', '.join(delims)}")
        
        # Compressed sample preview - extract key patterns manually
        if 'sample_preview' in self.sample_analysis:
            compressed_preview = self._manually_compress_sample_preview(self.sample_analysis['sample_preview'])
            patterns.append(f"**Pattern Analysis:**")
            patterns.append(compressed_preview)
        
        return '\n'.join(patterns)
    
    def _manually_compress_sample_preview(self, sample_preview: str) -> str:
        """Manually compress sample preview to essential patterns (without logreducer)"""
        try:
            # Try to parse as JSON to extract patterns
            import json
            sample_data = json.loads(sample_preview.split('...')[0])  # Remove truncation marker
            
            compression_lines = []
            
            # Check for syslog patterns
            if 'logoriginal' in sample_data or 'msg' in sample_data:
                msg_field = sample_data.get('logoriginal', sample_data.get('msg', ''))
                if '%' in str(msg_field) and '-' in str(msg_field):
                    compression_lines.append("- **Format**: Syslog with %FACILITY-SEVERITY-MNEMONIC pattern")
                
                # Extract pattern example
                if isinstance(msg_field, str) and len(msg_field) > 10:
                    # Truncate but keep essential structure
                    pattern_example = msg_field[:80] + "..." if len(msg_field) > 80 else msg_field
                    compression_lines.append(f"- **Example**: {pattern_example}")
            
            # Field type analysis
            structured_fields = []
            for key, value in sample_data.items():
                if key in ['facility', 'severity', 'priority', 'hostname', 'timestamp']:
                    field_type = type(value).__name__
                    structured_fields.append(f"{key}({field_type})")
            
            if structured_fields:
                compression_lines.append(f"- **Key Fields**: {', '.join(structured_fields[:6])}")
            
            # Parsing strategy hint
            if any(delim in str(sample_data) for delim in ['%', ':', '|', ',']):
                compression_lines.append("- **Strategy**: Use contains() and split() on delimiters")
            
            return '\n'.join(compression_lines)
            
        except (json.JSONDecodeError, KeyError, AttributeError):
            # Fallback to simple text analysis
            preview_short = sample_preview[:200] + "..."
            return f"- **Raw Pattern**: {preview_short}\n- **Strategy**: Analyze structure for parsing approach"
    
    def _extract_performance_data(self) -> str:
        """Extract performance data from VRL iterations"""
        if not self.vrl_iterations:
            return "No performance data available"
        
        perf_lines = []
        perf_lines.append("### Performance Baselines")
        
        for iteration in self.vrl_iterations[-3:]:  # Last 3 iterations only
            if 'performance_metrics' in iteration:
                metrics = iteration['performance_metrics']
                perf_lines.append(f"**Iteration {iteration['iteration']}:**")
                perf_lines.append(f"- Events/CPU%: {metrics.get('events_per_cpu_percent', 0):.0f}")
                perf_lines.append(f"- Events/sec: {metrics.get('events_per_second', 0):.0f}")
                perf_lines.append(f"- CPU: {metrics.get('cpu_percent', 0):.1f}%")
        
        return '\n'.join(perf_lines)
    
    def _estimate_tokens(self, text: str) -> int:
        """Rough token estimation (1 token ≈ 3.5 characters for English)"""
        return int(len(text) / 3.5)
    
    # Placeholder methods for other extraction functions
    def _extract_relevant_type_maps(self) -> str:
        """Extract relevant type mappings for current context"""
        if 'type_maps' not in self.external_configs:
            return "No type mappings available"
        
        type_config = self.external_configs['type_maps']
        
        if 'mappings' in type_config and type_config['mappings']:
            # Show first 10 mappings as examples
            mappings = type_config['mappings'][:10]
            
            type_lines = []
            type_lines.append("### Field Type Mappings")
            
            for mapping in mappings:
                # Assume CSV has field_name, field_type columns
                if 'field_name' in mapping and 'field_type' in mapping:
                    field_name = mapping['field_name']
                    field_type = mapping['field_type']
                    type_lines.append(f"- **{field_name}**: {field_type}")
            
            return '\n'.join(type_lines)
        
        return "Type mappings format not recognized"
    
    def _extract_successful_patterns(self) -> str:
        """Extract patterns from successful VRL iterations"""
        if not self.vrl_iterations:
            return "No previous iterations available"
        
        successful_iterations = [it for it in self.vrl_iterations if it.get('success', False)]
        
        if not successful_iterations:
            return "No successful patterns found in previous iterations"
        
        pattern_lines = []
        pattern_lines.append("### Previously Successful Patterns")
        
        for iteration in successful_iterations[-3:]:  # Last 3 successful only
            iter_num = iteration.get('iteration', '?')
            
            # Extract key techniques from VRL code
            vrl_code = iteration.get('vrl_code', '')
            techniques = []
            
            if 'contains(' in vrl_code:
                techniques.append('contains() checks')
            if 'split(' in vrl_code:
                techniques.append('split() operations')
            if 'parse_json(' in vrl_code:
                techniques.append('JSON parsing')
            if 'upcase(' in vrl_code or 'downcase(' in vrl_code:
                techniques.append('case normalization')
            
            if techniques:
                pattern_lines.append(f"- **Iteration {iter_num}**: Used {', '.join(techniques)}")
            
            # Add performance if available
            if 'performance_metrics' in iteration:
                perf = iteration['performance_metrics']
                events_cpu = perf.get('events_per_cpu_percent', 0)
                if events_cpu > 0:
                    pattern_lines.append(f"  - Performance: {events_cpu:.0f} events/CPU%")
        
        return '\n'.join(pattern_lines)
    
    def _extract_optimization_guides(self) -> str:
        """Extract performance optimization guides from VRL system config"""
        if 'vector_vrl_system' not in self.external_configs:
            return "No optimization guides available"
        
        vrl_config = self.external_configs['vector_vrl_system']
        
        # Look for performance-related sections
        optimization_content = []
        optimization_content.append("### Performance Optimization Guide")
        
        # Extract performance-related sections
        performance_sections = []
        for section_key, section_content in vrl_config.items():
            if any(keyword in section_key for keyword in ['performance', 'optimization', 'speed', 'tier']):
                performance_sections.append(section_content[:400])  # Truncate for token efficiency
        
        if performance_sections:
            optimization_content.extend(performance_sections)
        else:
            # Fallback basic optimization rules
            optimization_content.append("**Basic Optimization Rules:**")
            optimization_content.append("- NO regex operations (50-100x slower)")
            optimization_content.append("- Use string operations: contains(), split(), upcase()")
            optimization_content.append("- Target 300+ events/CPU% for Tier 1 performance")
            optimization_content.append("- Minimize VRL function calls in hot paths")
        
        return '\n'.join(optimization_content)
    
    def _format_system_info(self) -> str:
        """Format system performance context"""
        if not self.system_info:
            return "No system info available"
        
        sys_lines = []
        sys_lines.append("### System Performance Context")
        
        # CPU info
        if 'cpu_info' in self.system_info:
            cpu_info = self.system_info['cpu_info']
            cpu_model = cpu_info.get('model', 'Unknown')[:50]  # Truncate long model names
            cpu_cores = cpu_info.get('cpu_count_logical', 'Unknown')
            sys_lines.append(f"- **CPU**: {cpu_model}")
            sys_lines.append(f"- **Cores**: {cpu_cores}")
        
        # Benchmark multiplier
        if 'cpu_benchmark_multiplier' in self.system_info:
            multiplier = self.system_info['cpu_benchmark_multiplier']
            sys_lines.append(f"- **Benchmark**: {multiplier:.2f}x baseline performance")
        
        # Vector startup time
        if 'vector_startup_time' in self.system_info:
            startup_time = self.system_info['vector_startup_time']
            sys_lines.append(f"- **Vector Startup**: {startup_time:.2f}s (excluded from metrics)")
        
        return '\n'.join(sys_lines)
    
    def _extract_recent_errors(self) -> str:
        """Extract recent validation errors from VRL iterations"""
        if not self.vrl_iterations:
            return "No iteration history available"
        
        error_lines = []
        error_lines.append("### Recent Validation Errors")
        
        # Get last 3 iterations with errors
        recent_iterations = self.vrl_iterations[-5:]  # Last 5 iterations
        iterations_with_errors = [it for it in recent_iterations if it.get('validation_results', {}).get('errors')]
        
        if not iterations_with_errors:
            return "No recent validation errors found"
        
        for iteration in iterations_with_errors[-3:]:  # Last 3 with errors
            iter_num = iteration.get('iteration', '?')
            errors = iteration.get('validation_results', {}).get('errors', [])
            
            error_lines.append(f"**Iteration {iter_num}:**")
            for error in errors[:2]:  # Max 2 errors per iteration for token efficiency
                # Truncate long error messages
                error_short = error[:100] + "..." if len(error) > 100 else error
                error_lines.append(f"- {error_short}")
        
        return '\n'.join(error_lines)
    
    def _extract_syntax_rules(self) -> str:
        """Extract VRL syntax rules for debugging"""
        if 'vector_vrl_system' not in self.external_configs:
            return "No VRL syntax rules available"
        
        vrl_config = self.external_configs['vector_vrl_system']
        
        syntax_lines = []
        syntax_lines.append("### VRL Syntax Rules")
        
        # Look for syntax-related sections
        syntax_sections = []
        for section_key, section_content in vrl_config.items():
            if any(keyword in section_key for keyword in ['syntax', 'constraint', 'rule', 'format']):
                # Truncate for token efficiency
                syntax_sections.append(section_content[:300])
        
        if syntax_sections:
            syntax_lines.extend(syntax_sections)
        else:
            # Fallback basic syntax rules
            syntax_lines.append("**Basic VRL Syntax:**")
            syntax_lines.append("- Functions end with ! for fallible operations")
            syntax_lines.append("- Use string!() to convert to string type")
            syntax_lines.append("- Parse JSON with parse_json!(string!(.message))")
            syntax_lines.append("- NO regex functions allowed")
            syntax_lines.append("- Return event with single . at end")
        
        return '\n'.join(syntax_lines)
    
    def _extract_current_iteration_context(self) -> str:
        """Extract context about current/latest VRL iteration"""
        if not self.vrl_iterations:
            return "No current iteration available"
        
        latest = self.vrl_iterations[-1]
        
        context_lines = []
        context_lines.append("### Current Iteration Context")
        
        # Iteration info
        iter_num = latest.get('iteration', '?')
        success = latest.get('success', False)
        status = "✅ PASSED" if success else "❌ FAILED"
        
        context_lines.append(f"**Iteration {iter_num}** {status}")
        
        # Validation results
        validation = latest.get('validation_results', {})
        if validation:
            pyvrl_passed = validation.get('pyvrl_passed', False)
            vector_passed = validation.get('vector_passed', False)
            
            context_lines.append(f"- PyVRL: {'✓' if pyvrl_passed else '✗'}")
            context_lines.append(f"- Vector: {'✓' if vector_passed else '✗'}")
            
            # Show extracted fields if available
            if 'extracted_fields' in validation and validation['extracted_fields']:
                fields = validation['extracted_fields'][:5]  # Max 5 fields
                context_lines.append(f"- Extracted Fields: {', '.join(fields)}")
        
        # Performance if available
        if 'performance_metrics' in latest:
            perf = latest['performance_metrics']
            events_cpu = perf.get('events_per_cpu_percent', 0)
            if events_cpu > 0:
                context_lines.append(f"- Performance: {events_cpu:.0f} events/CPU%")
        
        return '\n'.join(context_lines)
    
    # Methods for adding data (to be called by main session manager)
    def set_sample_analysis(self, analysis: Dict[str, Any]):
        """Set sample analysis data"""
        self.sample_analysis = analysis
        logger.info("📊 Sample analysis updated")
    
    def set_system_info(self, info: Dict[str, Any]):
        """Set system info data"""
        self.system_info = info
        logger.info("🖥️  System info updated")
    
    def add_vrl_iteration(self, iteration_data: Dict[str, Any]):
        """Add VRL iteration data"""
        self.vrl_iterations.append(iteration_data)
        logger.info(f"📝 Added VRL iteration {iteration_data.get('iteration', '?')}")
    
    def add_conversation_turn(self, role: str, content: str):
        """Add conversation turn"""
        self.conversation_history.append({'role': role, 'content': content})
        # Keep only last 10 turns for token efficiency
        if len(self.conversation_history) > 10:
            self.conversation_history = self.conversation_history[-10:]


if __name__ == "__main__":
    # Test token-aware context manager
    context_mgr = TokenAwareContextManager()
    
    # Test different request types
    test_requests = [
        "Create a VRL parser for these Cisco logs",
        "Why is my VRL running so slow?", 
        "I'm getting validation errors in my VRL",
        "Help me optimize this VRL for better performance"
    ]
    
    for request in test_requests:
        print("=" * 80)
        print(f"REQUEST: {request}")
        print("=" * 80)
        context = context_mgr.get_focused_context(request)
        print(f"Context length: {len(context)} chars (~{len(context)//3.5:.0f} tokens)")
        print(context[:500] + "...")
        print()