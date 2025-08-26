#!/usr/bin/env python3
"""
LLM Context Manager for Persistent VRL Development Sessions

Manages persistent context for LLM interactions to avoid re-supplying 
external configs (VECTOR-VRL.md, AI-PARSER-PROMPTS.md, type_maps.csv) 
on every interaction.

Key features:
- Load external configs once on startup 
- Maintain conversation state across multiple VRL iterations
- Context packaging for LLM handoff
- Session continuity for K8s deployed environments
"""

import json
import time
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
from dataclasses import dataclass, field, asdict
from loguru import logger


@dataclass
class LLMContextState:
    """Persistent state for LLM interactions"""
    session_id: str
    created_at: str
    last_updated: str
    external_configs: Dict[str, str] = field(default_factory=dict)
    sample_analysis: Dict[str, Any] = field(default_factory=dict)
    system_info: Dict[str, Any] = field(default_factory=dict)
    vrl_iterations: List[Dict[str, Any]] = field(default_factory=list)
    performance_baselines: List[Dict[str, Any]] = field(default_factory=list)
    conversation_history: List[Dict[str, str]] = field(default_factory=list)


class LLMContextManager:
    """Manage persistent LLM context for VRL development sessions"""
    
    def __init__(self, external_configs_dir: str = "external", context_dir: str = ".tmp/llm_context"):
        self.external_configs_dir = Path(external_configs_dir)
        self.context_dir = Path(context_dir)
        self.context_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate unique session ID based on startup time
        self.session_id = f"vrl_session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Initialize context state
        self.context_state = LLMContextState(
            session_id=self.session_id,
            created_at=datetime.now(timezone.utc).isoformat(),
            last_updated=datetime.now(timezone.utc).isoformat()
        )
        
        # Load external configs once on startup
        self._load_external_configs()
        
        logger.info(f"🧠 LLM Context Manager initialized: {self.session_id}")
        logger.info(f"📁 Context directory: {self.context_dir}")
        logger.info(f"⚙️  External configs: {list(self.context_state.external_configs.keys())}")
    
    def _load_external_configs(self):
        """Load external configuration files (K8s deployed, company-wide)"""
        try:
            # Load vector-vrl-system.md (company-wide VRL prompt engineering)
            vector_vrl_file = self.external_configs_dir / "vector-vrl-system.md"
            if vector_vrl_file.exists():
                with open(vector_vrl_file, 'r') as f:
                    self.context_state.external_configs['vector_vrl_prompt'] = f.read()
                logger.info(f"✓ Loaded vector-vrl-system.md ({len(self.context_state.external_configs['vector_vrl_prompt'])} chars)")
            else:
                logger.warning(f"⚠️  vector-vrl-system.md not found at {vector_vrl_file}")
            
            # Load parser-system-prompts.md (project-specific overrides)
            parser_prompts_file = self.external_configs_dir / "parser-system-prompts.md"
            if parser_prompts_file.exists():
                with open(parser_prompts_file, 'r') as f:
                    self.context_state.external_configs['parser_prompts'] = f.read()
                logger.info(f"✓ Loaded parser-system-prompts.md ({len(self.context_state.external_configs['parser_prompts'])} chars)")
            else:
                logger.warning(f"⚠️  parser-system-prompts.md not found at {parser_prompts_file}")
            
            # Load type_maps.csv (field type mappings for product evolution)
            type_maps_file = self.external_configs_dir / "type_maps.csv"
            if type_maps_file.exists():
                with open(type_maps_file, 'r') as f:
                    self.context_state.external_configs['type_maps'] = f.read()
                logger.info(f"✓ Loaded type_maps.csv ({len(self.context_state.external_configs['type_maps'])} chars)")
            else:
                logger.warning(f"⚠️  type_maps.csv not found at {type_maps_file}")
            
        except Exception as e:
            logger.error(f"Failed to load external configs: {e}")
    
    def add_sample_analysis(self, sample_file: str, samples: List[Dict[str, Any]], cpu_info: Dict[str, Any], 
                          cpu_benchmark: float, vector_startup_time: float):
        """Add sample data analysis to persistent context"""
        self.context_state.sample_analysis = {
            'sample_file': sample_file,
            'sample_count': len(samples),
            'first_sample_keys': list(samples[0].keys()) if samples else [],
            'sample_preview': json.dumps(samples[0], indent=2)[:500] + '...' if samples else 'No samples',
            'unique_field_patterns': self._analyze_field_patterns(samples[:10])  # Analyze first 10 samples
        }
        
        self.context_state.system_info = {
            'cpu_info': cpu_info,
            'cpu_benchmark_multiplier': cpu_benchmark,
            'vector_startup_time': vector_startup_time,
            'analysis_timestamp': datetime.now(timezone.utc).isoformat()
        }
        
        self._update_timestamp()
        logger.info(f"📊 Added sample analysis: {len(samples)} samples from {sample_file}")
    
    def add_vrl_iteration(self, iteration: int, vrl_code: str, validation_results: Dict[str, Any], 
                         performance_metrics: Optional[Dict[str, Any]] = None):
        """Record VRL iteration attempt with results"""
        iteration_record = {
            'iteration': iteration,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'vrl_code': vrl_code,
            'validation_results': validation_results,
            'performance_metrics': performance_metrics or {},
            'success': validation_results.get('pyvrl_passed', False) and validation_results.get('vector_passed', False)
        }
        
        self.context_state.vrl_iterations.append(iteration_record)
        self._update_timestamp()
        
        status = "✅ PASSED" if iteration_record['success'] else "❌ FAILED"
        logger.info(f"📝 Recorded VRL iteration {iteration}: {status}")
    
    def add_conversation_turn(self, role: str, content: str):
        """Add conversation turn to history (for context retention)"""
        turn = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'role': role,  # 'user', 'assistant', 'system'
            'content': content[:1000] + '...' if len(content) > 1000 else content  # Truncate long content
        }
        
        self.context_state.conversation_history.append(turn)
        self._update_timestamp()
        
        # Keep only last 20 conversation turns to prevent context bloat
        if len(self.context_state.conversation_history) > 20:
            self.context_state.conversation_history = self.context_state.conversation_history[-20:]
    
    def get_llm_context_prompt(self) -> str:
        """Generate complete context prompt for LLM handoff"""
        prompt_parts = []
        
        # Session info
        prompt_parts.append(f"# VRL Development Session: {self.session_id}")
        prompt_parts.append(f"Created: {self.context_state.created_at}")
        prompt_parts.append(f"Last Updated: {self.context_state.last_updated}")
        prompt_parts.append("")
        
        # External configs (company-wide, K8s deployed)
        prompt_parts.append("## External Configurations (K8s Deployed)")
        prompt_parts.append("These are company-wide configs deployed by K8s on container startup:")
        prompt_parts.append("")
        
        if 'vector_vrl_prompt' in self.context_state.external_configs:
            prompt_parts.append("### vector-vrl-system.md (Company-wide VRL prompt engineering)")
            prompt_parts.append("```markdown")
            prompt_parts.append(self.context_state.external_configs['vector_vrl_prompt'])
            prompt_parts.append("```")
            prompt_parts.append("")
        
        if 'parser_prompts' in self.context_state.external_configs:
            prompt_parts.append("### parser-system-prompts.md (Project-specific overrides)")
            prompt_parts.append("```markdown")
            prompt_parts.append(self.context_state.external_configs['parser_prompts'])
            prompt_parts.append("```")
            prompt_parts.append("")
        
        if 'type_maps' in self.context_state.external_configs:
            prompt_parts.append("### type_maps.csv (Field type mappings)")
            prompt_parts.append("```csv")
            prompt_parts.append(self.context_state.external_configs['type_maps'])
            prompt_parts.append("```")
            prompt_parts.append("")
        
        # Sample analysis
        if self.context_state.sample_analysis:
            prompt_parts.append("## Sample Data Analysis")
            prompt_parts.append(f"File: {self.context_state.sample_analysis.get('sample_file', 'Unknown')}")
            prompt_parts.append(f"Samples: {self.context_state.sample_analysis.get('sample_count', 0)}")
            prompt_parts.append(f"Fields: {', '.join(self.context_state.sample_analysis.get('first_sample_keys', []))}")
            prompt_parts.append("")
            prompt_parts.append("### Sample Preview")
            prompt_parts.append("```json")
            prompt_parts.append(self.context_state.sample_analysis.get('sample_preview', 'No preview available'))
            prompt_parts.append("```")
            prompt_parts.append("")
        
        # System info
        if self.context_state.system_info:
            prompt_parts.append("## System Performance Context")
            cpu_info = self.context_state.system_info.get('cpu_info', {})
            prompt_parts.append(f"CPU: {cpu_info.get('model', 'Unknown')[:50]}")
            prompt_parts.append(f"Cores: {cpu_info.get('cpu_count_logical', 'Unknown')}")
            prompt_parts.append(f"Benchmark Multiplier: {self.context_state.system_info.get('cpu_benchmark_multiplier', 1.0):.2f}x")
            prompt_parts.append(f"Vector Startup Time: {self.context_state.system_info.get('vector_startup_time', 1.0):.2f}s")
            prompt_parts.append("")
        
        # Previous VRL iterations (learning context)
        if self.context_state.vrl_iterations:
            prompt_parts.append("## Previous VRL Iterations")
            prompt_parts.append("Learn from these previous attempts:")
            prompt_parts.append("")
            
            for iteration in self.context_state.vrl_iterations[-5:]:  # Last 5 iterations
                status = "✅ PASSED" if iteration['success'] else "❌ FAILED"
                prompt_parts.append(f"### Iteration {iteration['iteration']} {status}")
                
                # Show validation issues if failed
                if not iteration['success']:
                    validation = iteration['validation_results']
                    if validation.get('errors'):
                        prompt_parts.append("**Errors:**")
                        for error in validation['errors'][:3]:  # Max 3 errors
                            prompt_parts.append(f"- {error}")
                
                prompt_parts.append("")
        
        # Recent conversation context
        if self.context_state.conversation_history:
            prompt_parts.append("## Recent Conversation Context")
            for turn in self.context_state.conversation_history[-5:]:  # Last 5 turns
                role_emoji = {"user": "👤", "assistant": "🤖", "system": "⚙️"}.get(turn['role'], "💬")
                prompt_parts.append(f"{role_emoji} **{turn['role'].title()}**: {turn['content']}")
            prompt_parts.append("")
        
        prompt_parts.append("---")
        prompt_parts.append("**Context Manager**: This persistent context avoids re-supplying external configs on every interaction.")
        prompt_parts.append(f"**Session ID**: {self.session_id}")
        
        return "\n".join(prompt_parts)
    
    def save_context(self):
        """Save current context state to disk"""
        context_file = self.context_dir / f"{self.session_id}.json"
        
        try:
            with open(context_file, 'w') as f:
                json.dump(asdict(self.context_state), f, indent=2)
            
            logger.info(f"💾 Saved context to {context_file}")
            
        except Exception as e:
            logger.error(f"Failed to save context: {e}")
    
    def load_context(self, session_id: str) -> bool:
        """Load existing context state from disk"""
        context_file = self.context_dir / f"{session_id}.json"
        
        try:
            if context_file.exists():
                with open(context_file, 'r') as f:
                    context_data = json.load(f)
                
                self.context_state = LLMContextState(**context_data)
                self.session_id = session_id
                
                logger.info(f"📂 Loaded context from {context_file}")
                return True
            else:
                logger.warning(f"Context file not found: {context_file}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to load context: {e}")
            return False
    
    def _analyze_field_patterns(self, samples: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze patterns in sample fields for LLM context"""
        if not samples:
            return {}
        
        patterns = {
            'common_fields': set(samples[0].keys()),
            'field_types': {},
            'delimiters_found': set(),
            'structured_fields': []
        }
        
        # Find common fields across samples
        for sample in samples[1:]:
            patterns['common_fields'] &= set(sample.keys())
        
        # Analyze field types and patterns
        for field_name in list(patterns['common_fields'])[:10]:  # Limit to 10 fields
            values = [str(sample.get(field_name, '')) for sample in samples[:5]]
            
            # Detect common delimiters
            for value in values:
                if '%' in value:
                    patterns['delimiters_found'].add('%')
                if ',' in value:
                    patterns['delimiters_found'].add(',')
                if '|' in value:
                    patterns['delimiters_found'].add('|')
                if ':' in value:
                    patterns['delimiters_found'].add(':')
        
        # Convert sets to lists for JSON serialization
        patterns['common_fields'] = list(patterns['common_fields'])
        patterns['delimiters_found'] = list(patterns['delimiters_found'])
        
        return patterns
    
    def _update_timestamp(self):
        """Update last_updated timestamp"""
        self.context_state.last_updated = datetime.now(timezone.utc).isoformat()


if __name__ == "__main__":
    # Example usage
    context_mgr = LLMContextManager()
    
    # Simulate adding context
    context_mgr.add_conversation_turn("user", "Create VRL parser for Cisco IOS logs")
    context_mgr.add_conversation_turn("assistant", "I'll analyze the sample data and create a VRL parser...")
    
    # Save context
    context_mgr.save_context()
    
    # Show context prompt
    print("=" * 80)
    print("LLM CONTEXT PROMPT")
    print("=" * 80)
    print(context_mgr.get_llm_context_prompt())