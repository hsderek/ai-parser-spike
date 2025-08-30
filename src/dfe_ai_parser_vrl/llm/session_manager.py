"""
VRL Generation Session Manager

Implements persistent LLM conversation sessions with layered prompt architecture:
- Layer 1: Derek's VRL Guide (authoritative)
- Layer 2: Project error patterns (learned from testing)
- Layer 3: Template guidance (field conflicts, type safety)
- Layer 4: Model-specific hints (Claude/GPT differences)
"""

import time
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
from loguru import logger

from .client import DFELLMClient
from .prompts import DFEPromptManager
from ..core.error_learning_system import get_error_learning_summary


class VRLGenerationSession:
    """
    Persistent LLM conversation session for VRL generation
    Loads Derek's guide once, maintains conversation context
    """
    
    def __init__(self, device_type: str, baseline_vrl: str = None, session_type: str = "baseline_stage"):
        self.device_type = device_type
        self.baseline_vrl = baseline_vrl
        self.session_type = session_type
        self.session_id = f"vrl_{session_type}_{device_type}_{int(time.time())}"
        
        # Initialize LLM client
        self.llm_client = DFELLMClient()
        self.prompt_manager = DFEPromptManager()
        
        # Conversation state
        self.conversation_history = []
        self.iteration_count = 0
        self.total_cost = 0.0
        self.current_errors = []
        
        # Load layered prompt system at session start
        self._initialize_session_prompts()
        
        logger.info(f"🚀 VRL Generation Session initialized: {self.session_id}")
        logger.info(f"   Session type: {session_type}")
        logger.info(f"   Device type: {device_type}")
        logger.info(f"   Baseline VRL: {'✅ Provided' if baseline_vrl else '❌ None'}")
    
    def _initialize_session_prompts(self):
        """Initialize layered prompt system with Derek's guide as Layer 1"""
        
        logger.info("📚 Loading layered prompt system...")
        
        # Layer 1: Derek's VRL Guide (authoritative)
        self.dereks_guide = self._load_and_tokenize_vrl_guide()
        
        # Layer 2: Project error patterns (learned from testing)
        self.error_patterns = get_error_learning_summary()
        
        # Layer 3: Template guidance (field conflicts, type safety)
        self.template_guidance = self._load_template_guidance()
        
        # Layer 4: Model-specific hints
        self.model_hints = self._load_model_specific_hints()
        
        # Build initial system message with all layers
        self.system_message = self._build_layered_system_message()
        
        logger.info(f"   ✅ Layer 1: Derek's guide loaded ({len(self.dereks_guide)} chars)")
        logger.info(f"   ✅ Layer 2: {self.error_patterns.get('total_learned_fixes', 0)} error patterns")
        logger.info(f"   ✅ Layer 3: Template guidance loaded")
        logger.info(f"   ✅ Layer 4: Model-specific hints loaded")
    
    def _load_and_tokenize_vrl_guide(self) -> str:
        """Load Derek's VRL guide with smart pre-tokenization"""
        
        guide_path = Path(__file__).parent.parent / "prompts" / "VECTOR_VRL_GUIDE.md"
        
        if not guide_path.exists():
            logger.warning(f"Derek's VRL guide not found at {guide_path}")
            return ""
        
        try:
            with open(guide_path, 'r') as f:
                full_guide = f.read()
            
            # Smart pre-tokenization based on session type and current needs
            tokenized_guide = self._smart_tokenize_guide(full_guide)
            
            logger.info(f"📝 Derek's VRL guide: {len(full_guide)} → {len(tokenized_guide)} chars (tokenized)")
            return tokenized_guide
            
        except Exception as e:
            logger.error(f"Failed to load Derek's VRL guide: {e}")
            return ""
    
    def _smart_tokenize_guide(self, full_guide: str, max_tokens: int = 2000) -> str:
        """Smart pre-tokenization based on session type and error patterns"""
        
        # Extract sections based on priority
        sections_to_extract = []
        
        if self.session_type == "baseline_stage":
            # Prioritize sections for functional VRL generation
            sections_to_extract = [
                "## 2) HyperSec DFE defaults",  # Critical - explains 101 transform
                "## 5) Error Handling (Mandatory)",  # Critical - our main issue area
                "## 8) Branching & Classification Patterns",  # Important - nested conditions
                "## 20) LLM Generation Checklist",  # Critical - direct LLM guidance
                "## 14) Performance Guide — BAD / AVOID / GOOD",  # Important - avoid regex
            ]
        elif self.session_type == "performance_stage":
            # Prioritize sections for performance optimization
            sections_to_extract = [
                "## 14) Performance Guide — BAD / AVOID / GOOD",  # Critical - VPI optimization
                "## 13) Early Exits, Guard Clauses & Performance",  # Critical - optimization patterns
                "## 8) Branching & Classification Patterns",  # Important - nested conditions
                "## 7) Strings & Parsing",  # Important - efficient string ops
                "## 5) Error Handling (Mandatory)",  # Important - maintain correctness
            ]
        
        # Extract priority sections
        extracted_content = []
        remaining_tokens = max_tokens
        
        for section_header in sections_to_extract:
            section_content = self._extract_guide_section(full_guide, section_header)
            if section_content:
                section_tokens = len(section_content) // 4  # Rough token estimate
                if section_tokens <= remaining_tokens:
                    extracted_content.append(f"### {section_header}\n{section_content}")
                    remaining_tokens -= section_tokens
                else:
                    # Truncate section to fit remaining budget
                    truncated = section_content[:remaining_tokens * 4]
                    extracted_content.append(f"### {section_header}\n{truncated}...")
                    break
        
        result = "# Derek's VRL Guide (Layer 1 Authority)\n\n" + "\n\n".join(extracted_content)
        
        if len(result) > max_tokens * 4:
            result = result[:max_tokens * 4] + "\n\n... [Guide truncated for token budget]"
        
        logger.debug(f"Pre-tokenized {len(sections_to_extract)} priority sections for {self.session_type}")
        return result
    
    def _extract_guide_section(self, guide: str, section_header: str) -> str:
        """Extract specific section from Derek's guide"""
        
        lines = guide.split('\n')
        section_lines = []
        in_section = False
        
        for line in lines:
            if line.startswith(section_header):
                in_section = True
                continue
            elif line.startswith('## ') and in_section:
                # Hit next section, stop
                break
            elif in_section:
                section_lines.append(line)
        
        return '\n'.join(section_lines).strip()
    
    def _load_template_guidance(self) -> str:
        """Load Layer 3: Template guidance"""
        return """
Layer 3 - Project Template Guidance:
• Mandatory type safety: field_str = if exists(.field) { to_string(.field) ?? "" } else { "" }
• Field conflict prevention: 24 reserved DFE fields (timestamp, event_hash, etc.)
• Meta schema types: 23 types (string_fast, ipv4, int32, etc.)
• No arbitrary fields: Extract only real log data
"""
    
    def _load_model_specific_hints(self) -> str:
        """Load Layer 4: Model-specific hints"""
        model_family = self._get_model_family()
        
        if model_family == "claude":
            return """
Layer 4 - Claude-Specific Hints:
• Claude tends to generate sophisticated but syntax-heavy VRL
• Common issues: E203 (return statements), E651 (unnecessary coalescing)
• Fix approach: Use abort instead of return, avoid ?? on infallible ops
"""
        elif model_family == "gpt":
            return """
Layer 4 - GPT-Specific Hints:
• GPT is good with syntax but needs VRL-specific rules
• Focus on consistent variable naming and grouped logic
"""
        
        return "Layer 4 - Model-Specific Hints: None available"
    
    def _get_model_family(self) -> str:
        """Get model family for specific hints"""
        current_model = getattr(self.llm_client, 'current_model', '').lower()
        
        if 'claude' in current_model:
            return 'claude'
        elif 'gpt' in current_model:
            return 'gpt'
        elif 'gemini' in current_model:
            return 'gemini'
        
        return 'unknown'
    
    def _build_layered_system_message(self) -> str:
        """Build complete system message with all layers"""
        
        layers = [
            self.dereks_guide,  # Layer 1: Authoritative
            f"\\n\\n{self.template_guidance}",  # Layer 3: Project patterns
            f"\\n\\n{self.model_hints}"  # Layer 4: Model-specific
        ]
        
        # Add baseline VRL if provided
        if self.baseline_vrl:
            baseline_section = f"""
\\n\\n🏆 BASELINE VRL (Use as reference):
```vrl
{self.baseline_vrl[:2000]}  # Truncated for tokens
```

This baseline VRL works. Build on these proven patterns.
"""
            layers.insert(1, baseline_section)  # Insert as Layer 1.5
        
        system_message = "".join(layers)
        
        # Add conflict resolution guidance
        conflict_resolution = """

🚨 CONFLICT RESOLUTION:
• Derek's guide has HIGHEST authority (Layer 1)
• Project patterns enhance Derek's guidance (Layer 2)
• When conflicts arise, follow Derek's guidance
• Add project context: "Derek recommends X, our testing shows Y also helps"
"""
        
        system_message += conflict_resolution
        
        return system_message
    
    def generate_vrl(self, sample_logs: str, strategy: Dict[str, str] = None) -> str:
        """Generate VRL using persistent session context"""
        
        self.iteration_count += 1
        
        # Build user message for this specific request
        user_message = f"""Generate VRL parser for {self.device_type} logs.

Sample data:
```
{sample_logs[:3000]}
```

"""
        
        if strategy:
            user_message += f"""
Strategy: {strategy.get('name', 'default')}
Approach: {strategy.get('description', 'standard')}
"""
        
        user_message += "Return only clean VRL code that follows Derek's guidance (Layer 1) with project enhancements."
        
        # Add to conversation history
        if not self.conversation_history:
            # First message in session - include full system message
            messages = [
                {"role": "system", "content": self.system_message},
                {"role": "user", "content": user_message}
            ]
        else:
            # Continue existing conversation
            messages = self.conversation_history + [
                {"role": "user", "content": user_message}
            ]
        
        # Generate response
        response = self.llm_client.completion(messages, max_tokens=8000, temperature=0.3)
        vrl_content = response.choices[0].message.content
        
        # Update conversation history
        self.conversation_history = messages + [
            {"role": "assistant", "content": vrl_content}
        ]
        
        # Track cost
        cost = getattr(self.llm_client, 'last_completion_cost', 0) or 0
        self.total_cost += cost
        
        logger.info(f"📊 Session {self.session_id}: Iteration {self.iteration_count}, Cost: ${cost:.4f}, Total: ${self.total_cost:.4f}")
        
        return self.llm_client._extract_vrl_code(vrl_content)
    
    def fix_vrl_error(self, vrl_code: str, error_message: str, sample_logs: str = None) -> str:
        """Fix VRL error using session context and iteration history"""
        
        self.iteration_count += 1
        
        # Add current error to tracking
        error_code = self._extract_error_code(error_message)
        self.current_errors.append(error_code)
        
        # Build context-aware fix message
        fix_message = f"""Fix this VRL error using Derek's guidance.

Current VRL code:
```vrl
{vrl_code}
```

Error: {error_message}

Context: This is iteration {self.iteration_count} for {self.device_type}.
Previous errors in this session: {self.current_errors}

Fix following Derek's guide (Layer 1) with project error patterns (Layer 2).
Return only the fixed VRL code."""
        
        # Continue conversation
        messages = self.conversation_history + [
            {"role": "user", "content": fix_message}
        ]
        
        # Generate fix
        response = self.llm_client.completion(messages, max_tokens=6000, temperature=0.2)
        fixed_content = response.choices[0].message.content
        
        # Update conversation
        self.conversation_history = messages + [
            {"role": "assistant", "content": fixed_content}
        ]
        
        # Track cost
        cost = getattr(self.llm_client, 'last_completion_cost', 0) or 0
        self.total_cost += cost
        
        logger.info(f"🔧 Session {self.session_id}: Fix iteration {self.iteration_count}, Error: {error_code}")
        
        return self.llm_client._extract_vrl_code(fixed_content)
    
    def _extract_error_code(self, error_message: str) -> str:
        """Extract error code from message"""
        import re
        
        match = re.search(r'error\\[E(\\d+)\\]', error_message)
        if match:
            return f"E{match.group(1)}"
        
        if "syntax" in error_message.lower():
            return "E203"
        elif "coalescing" in error_message.lower():
            return "E651"
        elif "fallible" in error_message.lower():
            return "E103"
        
        return "UNKNOWN"
    
    def get_session_summary(self) -> Dict[str, Any]:
        """Get session performance summary"""
        
        return {
            "session_id": self.session_id,
            "session_type": self.session_type,
            "device_type": self.device_type,
            "iterations": self.iteration_count,
            "total_cost": self.total_cost,
            "conversation_length": len(self.conversation_history),
            "errors_encountered": list(set(self.current_errors)),
            "guide_loaded": bool(self.dereks_guide),
            "baseline_provided": bool(self.baseline_vrl)
        }


class SessionManager:
    """Manages multiple VRL generation sessions"""
    
    def __init__(self):
        self.active_sessions: Dict[str, VRLGenerationSession] = {}
    
    def get_session(self, device_type: str, session_type: str = "baseline_stage", 
                   baseline_vrl: str = None) -> VRLGenerationSession:
        """Get or create VRL generation session"""
        
        session_key = f"{session_type}_{device_type}"
        
        if session_key not in self.active_sessions:
            self.active_sessions[session_key] = VRLGenerationSession(
                device_type=device_type,
                baseline_vrl=baseline_vrl,
                session_type=session_type
            )
        
        return self.active_sessions[session_key]
    
    def cleanup_session(self, device_type: str, session_type: str = "baseline_stage"):
        """Clean up completed session"""
        session_key = f"{session_type}_{device_type}"
        
        if session_key in self.active_sessions:
            session = self.active_sessions[session_key]
            logger.info(f"🧹 Cleaning up session: {session.session_id}")
            del self.active_sessions[session_key]
    
    def get_all_session_summaries(self) -> List[Dict[str, Any]]:
        """Get summaries of all active sessions"""
        return [session.get_session_summary() for session in self.active_sessions.values()]


# Global session manager
_session_manager = SessionManager()

def get_vrl_session(device_type: str, session_type: str = "baseline_stage", 
                   baseline_vrl: str = None) -> VRLGenerationSession:
    """Get VRL generation session with Derek's guide loaded"""
    return _session_manager.get_session(device_type, session_type, baseline_vrl)

def cleanup_vrl_session(device_type: str, session_type: str = "baseline_stage"):
    """Clean up VRL generation session"""
    _session_manager.cleanup_session(device_type, session_type)

def get_all_session_summaries() -> List[Dict[str, Any]]:
    """Get all session summaries"""
    return _session_manager.get_all_session_summaries()