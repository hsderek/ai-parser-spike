#!/usr/bin/env python3
"""
Persistent VRL Development Session

Integrates VRLTestingLoop with LLMContextManager to create a persistent
session that retains external configs and conversation context across
multiple VRL development iterations.

Key Features:
- Single startup load of external configs (K8s deployed files)
- Persistent LLM context across conversation turns
- Session state management for long-running development
- Context handoff for LLM interactions
- Performance tracking across iterations
"""

import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from loguru import logger

from vrl_testing_loop_clean import VRLTestingLoop, VRLCandidate
from llm_context_manager import LLMContextManager
from token_aware_context_manager import TokenAwareContextManager, RequestType, ContextBudget


class PersistentVRLSession:
    """Persistent VRL development session with retained context"""
    
    def __init__(self, sample_file: str, output_dir: str = "samples-parsed", 
                 log_dir: str = "logs", external_configs_dir: str = "external"):
        
        # Initialize token-aware context manager (loads external configs once)
        self.context_manager = TokenAwareContextManager(external_configs_dir=external_configs_dir)
        
        # Initialize VRL testing loop
        self.vrl_loop = VRLTestingLoop(
            sample_file=sample_file,
            output_dir=output_dir, 
            log_dir=log_dir,
            external_configs_dir=external_configs_dir
        )
        
        # Initialize legacy context manager for session persistence
        self.legacy_context = LLMContextManager(external_configs_dir=external_configs_dir)
        
        # Add data to both context managers
        sample_analysis = self._analyze_samples_for_context(self.vrl_loop.samples)
        system_info = {
            'cpu_info': self.vrl_loop.cpu_info,
            'cpu_benchmark_multiplier': self.vrl_loop.cpu_benchmark_multiplier,
            'vector_startup_time': self.vrl_loop.vector_startup_time
        }
        
        # Set data in token-aware context manager
        self.context_manager.set_sample_analysis(sample_analysis)
        self.context_manager.set_system_info(system_info)
        
        # Also set in legacy context for session persistence
        self.legacy_context.add_sample_analysis(
            sample_file=sample_file,
            samples=self.vrl_loop.samples,
            cpu_info=self.vrl_loop.cpu_info,
            cpu_benchmark=self.vrl_loop.cpu_benchmark_multiplier,
            vector_startup_time=self.vrl_loop.vector_startup_time
        )
        
        self.iteration_count = 0
        logger.info(f"🚀 Persistent VRL Session initialized")
        logger.info(f"📋 Session ID: {self.legacy_context.session_id}")
        logger.info(f"🎯 Sample file: {sample_file}")
        logger.info(f"🧠 Token-aware context ready with {len(sample_analysis)} analysis points")
    
    def get_llm_context_for_new_conversation(self, request_type: Optional[RequestType] = None, 
                                           custom_budget: Optional[ContextBudget] = None) -> str:
        """Get focused, token-efficient context for starting a new LLM conversation"""
        
        logger.info("📦 Preparing token-aware LLM context...")
        
        # Use focused context instead of comprehensive dump
        initial_request = "Create a VRL parser for the loaded sample data"
        context_prompt = self.context_manager.get_focused_context(
            user_request=initial_request,
            request_type=request_type or RequestType.CREATE_VRL,
            budget=custom_budget
        )
        
        # Add session info for persistence
        session_header = [
            f"# VRL Development Session",
            f"Session ID: {self.legacy_context.session_id}",
            f"Samples: {len(self.vrl_loop.samples)} loaded",
            f"Token-optimized context for efficient LLM interaction",
            ""
        ]
        
        full_context = "\n".join(session_header) + "\n" + context_prompt
        
        # Record in legacy context for session persistence
        self.legacy_context.add_conversation_turn(
            "system", 
            f"Token-aware context prepared for {request_type or RequestType.CREATE_VRL}"
        )
        
        # Save session state
        self.legacy_context.save_context()
        
        logger.info(f"✅ Token-aware context prepared ({len(full_context)} chars)")
        logger.info(f"💾 Session saved: {self.legacy_context.session_id}")
        
        return full_context
    
    def process_user_request(self, user_message: str, custom_budget: Optional[ContextBudget] = None) -> str:
        """Process user request and return token-efficient focused context"""
        
        logger.info(f"👤 Processing request: {user_message[:100]}...")
        
        # Get focused context based on request
        focused_context = self.context_manager.get_focused_context(
            user_request=user_message,
            budget=custom_budget
        )
        
        # Record in legacy context for session persistence
        self.legacy_context.add_conversation_turn("user", user_message)
        self.legacy_context.add_conversation_turn("system", f"Provided focused context for request")
        
        logger.info(f"✅ Focused context ready ({len(focused_context)} chars)")
        
        return focused_context
    
    def test_llm_generated_vrl(self, vrl_code: str, iteration_note: str = "") -> Dict[str, Any]:
        """Test LLM-generated VRL and track results in persistent context"""
        
        self.iteration_count += 1
        logger.info(f"🔬 Testing LLM-generated VRL (iteration {self.iteration_count})")
        
        if iteration_note:
            logger.info(f"📝 Note: {iteration_note}")
        
        # Run VRL testing loop
        success = self.vrl_loop.run_with_llm_generated_vrl(vrl_code, self.iteration_count)
        
        # Get the latest candidate results
        latest_candidate = self.vrl_loop.candidates[-1] if self.vrl_loop.candidates else None
        
        if latest_candidate:
            # Prepare validation results
            validation_results = {
                'pyvrl_passed': latest_candidate.validated_pyvrl,
                'vector_passed': latest_candidate.validated_vector,
                'errors': latest_candidate.errors,
                'extracted_fields': latest_candidate.extracted_fields
            }
            
            # Add iteration to persistent context
            self.context_manager.add_vrl_iteration(
                iteration=self.iteration_count,
                vrl_code=vrl_code,
                validation_results=validation_results,
                performance_metrics=latest_candidate.performance_metrics
            )
            
            # Record iteration in conversation
            status = "✅ PASSED" if success else "❌ FAILED"
            self.context_manager.add_conversation_turn(
                "system",
                f"VRL iteration {self.iteration_count} {status}: {validation_results}"
            )
            
            # Save context after each iteration
            self.context_manager.save_context()
            
            return {
                'success': success,
                'iteration': self.iteration_count,
                'validation_results': validation_results,
                'performance_metrics': latest_candidate.performance_metrics,
                'candidate': latest_candidate
            }
        
        else:
            logger.error("❌ No candidate generated from VRL code")
            return {
                'success': False,
                'iteration': self.iteration_count,
                'error': 'No candidate generated'
            }
    
    def get_session_summary(self) -> Dict[str, Any]:
        """Get summary of current session state"""
        
        summary = {
            'session_id': self.legacy_context.session_id,
            'created_at': self.legacy_context.context_state.created_at,
            'last_updated': self.legacy_context.context_state.last_updated,
            'iterations_completed': len(self.context_manager.vrl_iterations),
            'successful_iterations': sum(1 for it in self.context_manager.vrl_iterations if it.get('success', False)),
            'external_configs_loaded': list(self.context_manager.external_configs.keys()),
            'sample_info': self.context_manager.sample_analysis,
            'system_info': self.context_manager.system_info,
            'conversation_turns': len(self.context_manager.conversation_history)
        }
        
        return summary
    
    def save_session(self):
        """Save current session state"""
        self.context_manager.save_context()
        
        # Also save VRL loop results if available
        if self.vrl_loop.best_candidate:
            self.vrl_loop.save_results()
    
    def load_session(self, session_id: str) -> bool:
        """Load existing session state"""
        return self.context_manager.load_context(session_id)
    
    def _guide_vrl_creation_request(self) -> str:
        """Guide response for VRL creation requests"""
        guidance = []
        
        guidance.append("🎯 VRL CREATION GUIDANCE")
        guidance.append("")
        guidance.append("I have the complete context loaded including:")
        
        configs = list(self.context_manager.external_configs.keys())
        guidance.append(f"- External configs: {', '.join(configs)}")
        guidance.append(f"- Sample analysis: {self.context_manager.context_state.sample_analysis.get('sample_count', 0)} samples")
        guidance.append(f"- System info: {self.context_manager.context_state.system_info.get('cpu_info', {}).get('model', 'Unknown')[:40]}...")
        
        guidance.append("")
        guidance.append("Key requirements from vector-vrl-system.md:")
        guidance.append("- NO REGEX (50-100x slower than string ops)")
        guidance.append("- Use contains(), split(), upcase(), downcase() instead")  
        guidance.append("- Target 300+ events/CPU% performance")
        guidance.append("- Vector 0.49.0 config format required")
        
        guidance.append("")
        guidance.append("Ready to generate VRL parser. Please provide your VRL code when ready for testing.")
        
        return "\n".join(guidance)
    
    def _guide_testing_request(self) -> str:
        """Guide response for testing requests"""
        guidance = []
        
        guidance.append("🧪 VRL TESTING GUIDANCE")
        guidance.append("")
        guidance.append("Testing pipeline ready with:")
        guidance.append("- PyVRL validation (fast iteration)")
        guidance.append("- Vector CLI validation (actual processing)")
        guidance.append("- Performance measurement with CPU normalization")
        guidance.append("- Regex pattern rejection")
        
        if self.iteration_count > 0:
            successful = sum(1 for it in self.context_manager.context_state.vrl_iterations if it['success'])
            guidance.append(f"- Previous iterations: {successful}/{self.iteration_count} successful")
        
        guidance.append("")
        guidance.append("Provide VRL code to test, and I'll run the complete validation pipeline.")
        
        return "\n".join(guidance)
    
    def _guide_optimization_request(self) -> str:
        """Guide response for optimization requests"""
        guidance = []
        
        guidance.append("⚡ VRL OPTIMIZATION GUIDANCE")  
        guidance.append("")
        guidance.append("Performance optimization targets:")
        guidance.append("- Tier S+: 15,000+ events/CPU%")
        guidance.append("- Tier S: 5,000+ events/CPU%") 
        guidance.append("- Tier 1: 300+ events/CPU%")
        
        if self.vrl_loop.candidates:
            best_perf = max(c.performance_metrics.get('events_per_cpu_percent', 0) for c in self.vrl_loop.candidates)
            guidance.append(f"- Current best: {int(best_perf)} events/CPU%")
        
        guidance.append("")
        guidance.append("Optimization strategies:")
        guidance.append("- Replace any regex with string operations")
        guidance.append("- Minimize VRL function calls")
        guidance.append("- Use early returns for conditional logic")
        guidance.append("- Batch field assignments")
        
        return "\n".join(guidance)
    
    def _analyze_samples_for_context(self, samples: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze samples for token-aware context (without logreducer)"""
        if not samples:
            return {}
        
        analysis = {
            'sample_count': len(samples),
            'common_fields': [],
            'delimiters_found': set(),
            'sample_preview': ''
        }
        
        # Find common fields across first 5 samples
        if samples:
            common_fields = set(samples[0].keys())
            for sample in samples[1:5]:  # Check first 5 samples
                common_fields &= set(sample.keys())
            analysis['common_fields'] = list(common_fields)
        
        # Analyze delimiters in key message fields
        for sample in samples[:3]:  # First 3 samples only
            for field_name in ['msg', 'message', 'logoriginal']:
                if field_name in sample:
                    msg_value = str(sample[field_name])
                    for delimiter in ['%', ':', '|', ',', '-', ' ']:
                        if delimiter in msg_value:
                            analysis['delimiters_found'].add(delimiter)
        
        # Create compressed sample preview
        if samples:
            analysis['sample_preview'] = json.dumps(samples[0], indent=2)[:400]  # First 400 chars
        
        # Convert set to list for JSON serialization
        analysis['delimiters_found'] = list(analysis['delimiters_found'])
        
        return analysis
    
    def _guide_general_request(self) -> str:
        """Guide response for general requests"""
        guidance = []
        
        guidance.append("💬 GENERAL VRL SESSION GUIDANCE")
        guidance.append("")
        guidance.append("Available commands:")
        guidance.append("- Create/Generate: VRL parser creation")
        guidance.append("- Test/Validate: VRL testing pipeline") 
        guidance.append("- Optimize/Improve: Performance optimization")
        
        summary = self.get_session_summary()
        guidance.append("")
        guidance.append(f"Session status:")
        guidance.append(f"- Iterations: {summary['iterations_completed']}")
        guidance.append(f"- Success rate: {summary['successful_iterations']}/{summary['iterations_completed']}")
        guidance.append(f"- Configs loaded: {len(summary['external_configs_loaded'])}")
        
        return "\n".join(guidance)


if __name__ == "__main__":
    # Example usage
    session = PersistentVRLSession("samples/cisco-ios.ndjson")
    
    # Get initial context for LLM
    print("=" * 80)
    print("LLM CONTEXT FOR NEW CONVERSATION")
    print("=" * 80)
    print(session.get_llm_context_for_new_conversation())
    
    # Process example user request
    print("\n" + "=" * 80)
    print("EXAMPLE USER REQUEST PROCESSING")
    print("=" * 80)
    response = session.process_user_request("Create a VRL parser for these Cisco IOS logs")
    print(response)
    
    # Show session summary
    print("\n" + "=" * 80) 
    print("SESSION SUMMARY")
    print("=" * 80)
    print(json.dumps(session.get_session_summary(), indent=2))