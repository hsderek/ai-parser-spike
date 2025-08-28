#!/usr/bin/env python3
"""
LLM Streaming Monitor - Universal API streaming status detection
Supports vendor-specific implementations while providing unified interface
"""

import asyncio
import time
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Callable, AsyncGenerator, Union
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)

class StreamStatus(Enum):
    """Stream status indicators"""
    STARTING = "starting"
    ACTIVE = "active" 
    THINKING = "thinking"
    GENERATING = "generating"
    COMPLETING = "completing"
    COMPLETED = "completed"
    TIMEOUT = "timeout"
    ERROR = "error"
    HUNG = "hung"

@dataclass
class StreamProgress:
    """Progress information from streaming API"""
    status: StreamStatus
    tokens_generated: int = 0
    estimated_total: Optional[int] = None
    content_preview: str = ""
    elapsed_time: float = 0.0
    last_activity: float = 0.0
    error_message: Optional[str] = None
    raw_event: Optional[Dict[str, Any]] = None

class StreamingMonitor(ABC):
    """Abstract base for vendor-specific streaming monitors"""
    
    def __init__(self, timeout_seconds: int = 300, hang_detection_seconds: int = 60):
        self.timeout_seconds = timeout_seconds
        self.hang_detection_seconds = hang_detection_seconds
        self.start_time = time.time()
        self.last_activity = time.time()
        self.status_callbacks: list[Callable[[StreamProgress], None]] = []
        
    def add_status_callback(self, callback: Callable[[StreamProgress], None]):
        """Add callback for status updates"""
        self.status_callbacks.append(callback)
        
    def _notify_status(self, progress: StreamProgress):
        """Notify all status callbacks"""
        for callback in self.status_callbacks:
            try:
                callback(progress)
            except Exception as e:
                logger.error(f"Status callback error: {e}")
    
    def _check_timeouts(self) -> Optional[StreamStatus]:
        """Check for timeout or hang conditions"""
        now = time.time()
        elapsed = now - self.start_time
        inactive = now - self.last_activity
        
        if elapsed > self.timeout_seconds:
            return StreamStatus.TIMEOUT
        elif inactive > self.hang_detection_seconds:
            return StreamStatus.HUNG
        return None
    
    @abstractmethod
    async def monitor_stream(self, stream_response) -> AsyncGenerator[StreamProgress, None]:
        """Monitor vendor-specific streaming response"""
        pass

class AnthropicStreamingMonitor(StreamingMonitor):
    """Anthropic Claude streaming monitor"""
    
    async def monitor_stream(self, stream_response) -> AsyncGenerator[StreamProgress, None]:
        """Monitor Anthropic Claude streaming response"""
        logger.info("🔄 Starting Anthropic Claude stream monitoring")
        
        tokens_generated = 0
        content_buffer = ""
        current_status = StreamStatus.STARTING
        
        try:
            async for event in stream_response:
                self.last_activity = time.time()
                elapsed = self.last_activity - self.start_time
                
                # Check for timeout/hang conditions
                timeout_status = self._check_timeouts()
                if timeout_status:
                    yield StreamProgress(
                        status=timeout_status,
                        tokens_generated=tokens_generated,
                        content_preview=content_buffer[:200],
                        elapsed_time=elapsed,
                        last_activity=self.last_activity,
                        error_message=f"Stream {timeout_status.value} detected"
                    )
                    return
                
                # Parse Anthropic-specific events
                event_type = getattr(event, 'type', 'unknown')
                
                if event_type == 'message_start':
                    current_status = StreamStatus.ACTIVE
                    yield StreamProgress(
                        status=current_status,
                        tokens_generated=tokens_generated,
                        elapsed_time=elapsed,
                        last_activity=self.last_activity,
                        raw_event={'type': event_type}
                    )
                
                elif event_type == 'content_block_start':
                    current_status = StreamStatus.GENERATING
                    yield StreamProgress(
                        status=current_status,
                        tokens_generated=tokens_generated,
                        elapsed_time=elapsed,
                        last_activity=self.last_activity,
                        raw_event={'type': event_type}
                    )
                
                elif event_type == 'content_block_delta':
                    if hasattr(event, 'delta') and hasattr(event.delta, 'text'):
                        new_text = event.delta.text
                        content_buffer += new_text
                        tokens_generated += len(new_text.split())  # Rough token estimate
                        
                        yield StreamProgress(
                            status=StreamStatus.GENERATING,
                            tokens_generated=tokens_generated,
                            content_preview=content_buffer[:200],
                            elapsed_time=elapsed,
                            last_activity=self.last_activity,
                            raw_event={'type': event_type, 'text': new_text}
                        )
                
                elif event_type == 'content_block_stop':
                    current_status = StreamStatus.COMPLETING
                    yield StreamProgress(
                        status=current_status,
                        tokens_generated=tokens_generated,
                        content_preview=content_buffer[:200],
                        elapsed_time=elapsed,
                        last_activity=self.last_activity,
                        raw_event={'type': event_type}
                    )
                
                elif event_type == 'message_stop':
                    current_status = StreamStatus.COMPLETED
                    yield StreamProgress(
                        status=current_status,
                        tokens_generated=tokens_generated,
                        content_preview=content_buffer[:200],
                        elapsed_time=elapsed,
                        last_activity=self.last_activity,
                        raw_event={'type': event_type}
                    )
                    return
                
                elif event_type == 'ping':
                    # Anthropic ping for connection maintenance
                    yield StreamProgress(
                        status=current_status,
                        tokens_generated=tokens_generated,
                        content_preview=content_buffer[:200],
                        elapsed_time=elapsed,
                        last_activity=self.last_activity,
                        raw_event={'type': 'ping'}
                    )
                
        except Exception as e:
            logger.error(f"Anthropic streaming error: {e}")
            yield StreamProgress(
                status=StreamStatus.ERROR,
                tokens_generated=tokens_generated,
                content_preview=content_buffer[:200],
                elapsed_time=time.time() - self.start_time,
                last_activity=self.last_activity,
                error_message=str(e),
                raw_event={'error': str(e)}
            )

class OpenAIStreamingMonitor(StreamingMonitor):
    """OpenAI GPT streaming monitor"""
    
    async def monitor_stream(self, stream_response) -> AsyncGenerator[StreamProgress, None]:
        """Monitor OpenAI GPT streaming response"""
        logger.info("🔄 Starting OpenAI GPT stream monitoring")
        
        tokens_generated = 0
        content_buffer = ""
        current_status = StreamStatus.STARTING
        
        try:
            async for chunk in stream_response:
                self.last_activity = time.time()
                elapsed = self.last_activity - self.start_time
                
                # Check for timeout/hang conditions
                timeout_status = self._check_timeouts()
                if timeout_status:
                    yield StreamProgress(
                        status=timeout_status,
                        tokens_generated=tokens_generated,
                        content_preview=content_buffer[:200],
                        elapsed_time=elapsed,
                        last_activity=self.last_activity,
                        error_message=f"Stream {timeout_status.value} detected"
                    )
                    return
                
                # Parse OpenAI-specific chunks
                if hasattr(chunk, 'choices') and chunk.choices:
                    choice = chunk.choices[0]
                    
                    if hasattr(choice, 'delta') and choice.delta:
                        if hasattr(choice.delta, 'content') and choice.delta.content:
                            new_text = choice.delta.content
                            content_buffer += new_text
                            tokens_generated += len(new_text.split())  # Rough token estimate
                            current_status = StreamStatus.GENERATING
                            
                            yield StreamProgress(
                                status=current_status,
                                tokens_generated=tokens_generated,
                                content_preview=content_buffer[:200],
                                elapsed_time=elapsed,
                                last_activity=self.last_activity,
                                raw_event={'content': new_text}
                            )
                    
                    # Check for completion
                    if hasattr(choice, 'finish_reason') and choice.finish_reason:
                        current_status = StreamStatus.COMPLETED
                        yield StreamProgress(
                            status=current_status,
                            tokens_generated=tokens_generated,
                            content_preview=content_buffer[:200],
                            elapsed_time=elapsed,
                            last_activity=self.last_activity,
                            raw_event={'finish_reason': choice.finish_reason}
                        )
                        return
                
        except Exception as e:
            logger.error(f"OpenAI streaming error: {e}")
            yield StreamProgress(
                status=StreamStatus.ERROR,
                tokens_generated=tokens_generated,
                content_preview=content_buffer[:200],
                elapsed_time=time.time() - self.start_time,
                last_activity=self.last_activity,
                error_message=str(e),
                raw_event={'error': str(e)}
            )

class GeminiStreamingMonitor(StreamingMonitor):
    """Google Gemini streaming monitor"""
    
    async def monitor_stream(self, stream_response) -> AsyncGenerator[StreamProgress, None]:
        """Monitor Google Gemini streaming response"""
        logger.info("🔄 Starting Google Gemini stream monitoring")
        
        tokens_generated = 0
        content_buffer = ""
        current_status = StreamStatus.STARTING
        
        try:
            async for response in stream_response:
                self.last_activity = time.time()
                elapsed = self.last_activity - self.start_time
                
                # Check for timeout/hang conditions
                timeout_status = self._check_timeouts()
                if timeout_status:
                    yield StreamProgress(
                        status=timeout_status,
                        tokens_generated=tokens_generated,
                        content_preview=content_buffer[:200],
                        elapsed_time=elapsed,
                        last_activity=self.last_activity,
                        error_message=f"Stream {timeout_status.value} detected"
                    )
                    return
                
                # Parse Gemini-specific response
                if hasattr(response, 'text') and response.text:
                    new_text = response.text
                    content_buffer += new_text
                    tokens_generated += len(new_text.split())  # Rough token estimate
                    current_status = StreamStatus.GENERATING
                    
                    yield StreamProgress(
                        status=current_status,
                        tokens_generated=tokens_generated,
                        content_preview=content_buffer[:200],
                        elapsed_time=elapsed,
                        last_activity=self.last_activity,
                        raw_event={'text': new_text}
                    )
                
                # Gemini completion handling would go here
                # (specific to Gemini's response structure)
                
        except Exception as e:
            logger.error(f"Gemini streaming error: {e}")
            yield StreamProgress(
                status=StreamStatus.ERROR,
                tokens_generated=tokens_generated,
                content_preview=content_buffer[:200],
                elapsed_time=time.time() - self.start_time,
                last_activity=self.last_activity,
                error_message=str(e),
                raw_event={'error': str(e)}
            )

class UniversalStreamingMonitor:
    """Universal interface for all LLM streaming monitors"""
    
    def __init__(self, timeout_seconds: int = 300, hang_detection_seconds: int = 60):
        self.timeout_seconds = timeout_seconds
        self.hang_detection_seconds = hang_detection_seconds
        self.monitors = {
            'anthropic': AnthropicStreamingMonitor,
            'openai': OpenAIStreamingMonitor, 
            'gemini': GeminiStreamingMonitor,
        }
    
    def create_monitor(self, provider: str) -> StreamingMonitor:
        """Create appropriate monitor for provider"""
        if provider not in self.monitors:
            raise ValueError(f"Unsupported provider: {provider}. Supported: {list(self.monitors.keys())}")
        
        return self.monitors[provider](
            timeout_seconds=self.timeout_seconds,
            hang_detection_seconds=self.hang_detection_seconds
        )
    
    async def monitor_llm_stream(
        self, 
        provider: str, 
        stream_response,
        status_callback: Optional[Callable[[StreamProgress], None]] = None
    ) -> AsyncGenerator[StreamProgress, None]:
        """Universal streaming monitor with status callbacks"""
        
        monitor = self.create_monitor(provider)
        if status_callback:
            monitor.add_status_callback(status_callback)
        
        logger.info(f"🚀 Starting {provider} streaming monitor (timeout: {self.timeout_seconds}s, hang detection: {self.hang_detection_seconds}s)")
        
        async for progress in monitor.monitor_stream(stream_response):
            yield progress

# Usage example and status callback functions
def log_stream_status(progress: StreamProgress):
    """Example status callback for logging"""
    if progress.status == StreamStatus.GENERATING:
        logger.info(f"📝 Generating: {progress.tokens_generated} tokens, {progress.elapsed_time:.1f}s")
    elif progress.status in [StreamStatus.TIMEOUT, StreamStatus.HUNG, StreamStatus.ERROR]:
        logger.error(f"❌ Stream {progress.status.value}: {progress.error_message}")
    elif progress.status == StreamStatus.COMPLETED:
        logger.info(f"✅ Completed: {progress.tokens_generated} tokens in {progress.elapsed_time:.1f}s")

def progress_bar_callback(progress: StreamProgress):
    """Example callback for progress bar updates"""
    if progress.estimated_total and progress.tokens_generated:
        percentage = min(100, (progress.tokens_generated / progress.estimated_total) * 100)
        print(f"\rProgress: {percentage:.1f}% ({progress.tokens_generated} tokens)", end='', flush=True)

if __name__ == "__main__":
    # Example usage
    monitor = UniversalStreamingMonitor(timeout_seconds=180, hang_detection_seconds=30)
    
    # This would be called from your actual LLM integration code:
    # async for progress in monitor.monitor_llm_stream('anthropic', stream_response, log_stream_status):
    #     # Handle progress updates
    #     pass