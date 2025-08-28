#!/usr/bin/env python3
"""
Streaming Integration - Retrofit streaming monitoring into existing LLM session code
"""

import asyncio
import time
from typing import Optional, Dict, Any
import logging

from llm_streaming_monitor import UniversalStreamingMonitor, StreamProgress, StreamStatus

logger = logging.getLogger(__name__)

class StreamingLLMSession:
    """Enhanced LLM session with streaming monitoring"""
    
    def __init__(self, original_session, timeout_seconds: int = 180, hang_detection_seconds: int = 30):
        self.original_session = original_session
        self.streaming_monitor = UniversalStreamingMonitor(timeout_seconds, hang_detection_seconds)
        self.last_progress: Optional[StreamProgress] = None
        self.stream_cancelled = False
        
    async def call_llm_with_streaming(
        self, 
        provider: str, 
        messages: list,
        **kwargs
    ) -> tuple[str, Dict[str, Any]]:
        """Enhanced LLM call with streaming monitoring"""
        
        start_time = time.time()
        logger.info(f"🚀 Starting streaming {provider} API call")
        
        # Status callback to track progress
        def status_callback(progress: StreamProgress):
            self.last_progress = progress
            self._log_progress(progress)
            
            # Auto-cancel on timeout/hang
            if progress.status in [StreamStatus.TIMEOUT, StreamStatus.HUNG]:
                logger.error(f"🛑 Cancelling stream due to {progress.status.value}")
                self.stream_cancelled = True
        
        try:
            # Modify request to enable streaming
            streaming_kwargs = kwargs.copy()
            streaming_kwargs['stream'] = True
            
            if provider == 'anthropic':
                response = await self._call_anthropic_streaming(messages, streaming_kwargs, status_callback)
            elif provider == 'openai':
                response = await self._call_openai_streaming(messages, streaming_kwargs, status_callback)
            elif provider == 'gemini':
                response = await self._call_gemini_streaming(messages, streaming_kwargs, status_callback)
            else:
                # Fallback to non-streaming
                logger.warning(f"⚠️ No streaming support for {provider}, falling back to standard call")
                return await self._fallback_to_standard_call(provider, messages, **kwargs)
            
            elapsed_time = time.time() - start_time
            
            # Extract final response and metadata
            content = response.get('content', '')
            metadata = {
                'provider': provider,
                'streaming': True,
                'elapsed_time': elapsed_time,
                'tokens_generated': self.last_progress.tokens_generated if self.last_progress else 0,
                'final_status': self.last_progress.status.value if self.last_progress else 'unknown',
                'cancelled': self.stream_cancelled
            }
            
            logger.info(f"✅ Streaming call completed: {len(content)} chars in {elapsed_time:.1f}s")
            return content, metadata
            
        except Exception as e:
            logger.error(f"❌ Streaming call failed: {e}")
            # Fallback to standard call on streaming failure
            logger.info("🔄 Falling back to standard non-streaming call")
            return await self._fallback_to_standard_call(provider, messages, **kwargs)
    
    def _log_progress(self, progress: StreamProgress):
        """Log progress updates with appropriate level"""
        if progress.status == StreamStatus.GENERATING:
            if progress.tokens_generated % 50 == 0:  # Log every 50 tokens
                logger.info(f"📝 {progress.tokens_generated} tokens ({progress.elapsed_time:.1f}s)")
        
        elif progress.status == StreamStatus.ACTIVE:
            logger.info(f"🔄 Stream active ({progress.elapsed_time:.1f}s)")
        
        elif progress.status == StreamStatus.THINKING:
            logger.info(f"🤔 LLM thinking... ({progress.elapsed_time:.1f}s)")
        
        elif progress.status == StreamStatus.COMPLETING:
            logger.info(f"🏁 Stream completing ({progress.elapsed_time:.1f}s)")
        
        elif progress.status == StreamStatus.COMPLETED:
            logger.info(f"✅ Stream completed: {progress.tokens_generated} tokens in {progress.elapsed_time:.1f}s")
        
        elif progress.status == StreamStatus.TIMEOUT:
            logger.error(f"⏰ Stream timeout after {progress.elapsed_time:.1f}s")
        
        elif progress.status == StreamStatus.HUNG:
            logger.error(f"🔒 Stream hung (inactive for {progress.elapsed_time - progress.last_activity:.1f}s)")
        
        elif progress.status == StreamStatus.ERROR:
            logger.error(f"❌ Stream error: {progress.error_message}")
    
    async def _call_anthropic_streaming(
        self, 
        messages: list, 
        kwargs: Dict[str, Any],
        status_callback
    ) -> Dict[str, Any]:
        """Call Anthropic with streaming monitoring"""
        
        # Use original session's Anthropic client
        import anthropic
        
        client = getattr(self.original_session, 'anthropic_client', None)
        if not client:
            # Create client if it doesn't exist
            client = anthropic.Anthropic()
        
        # Make streaming request
        stream = await client.messages.create(
            messages=messages,
            **kwargs
        )
        
        # Monitor the stream
        content_parts = []
        async for progress in self.streaming_monitor.monitor_llm_stream('anthropic', stream, status_callback):
            if progress.status in [StreamStatus.TIMEOUT, StreamStatus.HUNG, StreamStatus.ERROR]:
                break
            
            if self.stream_cancelled:
                break
                
            # Collect content as it streams
            if hasattr(progress.raw_event, 'get') and progress.raw_event.get('text'):
                content_parts.append(progress.raw_event['text'])
        
        return {
            'content': ''.join(content_parts),
            'streaming': True
        }
    
    async def _call_openai_streaming(
        self, 
        messages: list, 
        kwargs: Dict[str, Any],
        status_callback
    ) -> Dict[str, Any]:
        """Call OpenAI with streaming monitoring"""
        
        # Use original session's OpenAI client
        import openai
        
        client = getattr(self.original_session, 'openai_client', None)
        if not client:
            client = openai.AsyncOpenAI()
        
        # Make streaming request
        stream = await client.chat.completions.create(
            messages=messages,
            **kwargs
        )
        
        # Monitor the stream
        content_parts = []
        async for progress in self.streaming_monitor.monitor_llm_stream('openai', stream, status_callback):
            if progress.status in [StreamStatus.TIMEOUT, StreamStatus.HUNG, StreamStatus.ERROR]:
                break
                
            if self.stream_cancelled:
                break
                
            # Collect content as it streams
            if hasattr(progress.raw_event, 'get') and progress.raw_event.get('content'):
                content_parts.append(progress.raw_event['content'])
        
        return {
            'content': ''.join(content_parts),
            'streaming': True
        }
    
    async def _call_gemini_streaming(
        self, 
        messages: list, 
        kwargs: Dict[str, Any],
        status_callback
    ) -> Dict[str, Any]:
        """Call Gemini with streaming monitoring"""
        
        # Gemini streaming implementation would go here
        # (specific to Gemini's API structure)
        raise NotImplementedError("Gemini streaming not yet implemented")
    
    async def _fallback_to_standard_call(
        self, 
        provider: str, 
        messages: list, 
        **kwargs
    ) -> tuple[str, Dict[str, Any]]:
        """Fallback to standard non-streaming call"""
        
        # Remove streaming parameter
        standard_kwargs = {k: v for k, v in kwargs.items() if k != 'stream'}
        
        # Use original session's call method
        if hasattr(self.original_session, '_call_llm'):
            return await self.original_session._call_llm(provider, messages, **standard_kwargs)
        else:
            # Basic fallback implementation
            content = f"Fallback response for {provider}"
            metadata = {'provider': provider, 'streaming': False, 'fallback': True}
            return content, metadata

# Integration function to retrofit existing code
def enable_streaming_monitoring(session_instance, timeout_seconds: int = 180, hang_detection_seconds: int = 30):
    """Enable streaming monitoring for existing LLM session instance"""
    
    # Store original call method
    original_call_llm = getattr(session_instance, '_call_llm', None)
    if not original_call_llm:
        logger.warning("⚠️ No _call_llm method found, streaming monitoring may not work correctly")
        return session_instance
    
    # Create streaming wrapper
    streaming_session = StreamingLLMSession(session_instance, timeout_seconds, hang_detection_seconds)
    
    # Replace the call method with streaming version
    async def enhanced_call_llm(provider: str, messages: list, **kwargs) -> tuple[str, Dict[str, Any]]:
        """Enhanced _call_llm with streaming monitoring"""
        try:
            return await streaming_session.call_llm_with_streaming(provider, messages, **kwargs)
        except Exception as e:
            logger.error(f"Streaming call failed, using original method: {e}")
            return await original_call_llm(provider, messages, **kwargs)
    
    # Monkey patch the enhanced method
    session_instance._call_llm = enhanced_call_llm
    session_instance._streaming_monitor = streaming_session
    
    logger.info(f"✅ Streaming monitoring enabled (timeout: {timeout_seconds}s, hang detection: {hang_detection_seconds}s)")
    return session_instance

# Quick integration for existing VRL testing code
def retrofit_vrl_session_streaming(vrl_session_instance):
    """Specifically retrofit VRL testing session with streaming"""
    
    if hasattr(vrl_session_instance, 'llm_session'):
        # Enable streaming for the nested LLM session
        enable_streaming_monitoring(vrl_session_instance.llm_session, timeout_seconds=120, hang_detection_seconds=45)
        logger.info("🔄 VRL session streaming monitoring enabled")
    else:
        logger.warning("⚠️ VRL session has no llm_session attribute, cannot enable streaming")
    
    return vrl_session_instance