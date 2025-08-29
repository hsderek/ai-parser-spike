"""
Smart LLM Error Handler

Differentiates between LLM generation issues vs infrastructure/network problems.
Prevents treating API/network errors as LLM generation failures.
"""

import time
from typing import Optional, Dict, Any, Tuple
from loguru import logger


class LLMErrorCategory:
    """Categories of LLM errors for smart handling"""
    
    NETWORK_ERROR = "network"           # Connection, timeout, DNS issues
    API_ERROR = "api"                   # Authentication, rate limits, service issues  
    EMPTY_RESPONSE = "empty_response"   # LLM returned nothing/empty content
    GENERATION_ERROR = "generation"     # Actual LLM content generation issues
    INFRASTRUCTURE_ERROR = "infrastructure"  # System/config issues


class SmartLLMErrorHandler:
    """Intelligent LLM error handling and classification"""
    
    def __init__(self):
        self.retry_config = {
            LLMErrorCategory.NETWORK_ERROR: {"max_retries": 3, "base_delay": 2.0},
            LLMErrorCategory.API_ERROR: {"max_retries": 2, "base_delay": 5.0},
            LLMErrorCategory.EMPTY_RESPONSE: {"max_retries": 2, "base_delay": 1.0},
            LLMErrorCategory.GENERATION_ERROR: {"max_retries": 1, "base_delay": 0},
            LLMErrorCategory.INFRASTRUCTURE_ERROR: {"max_retries": 0, "base_delay": 0}
        }
    
    def classify_error(self, error: Exception, response_content: str = None) -> Tuple[str, bool]:
        """
        Classify error and determine if retry is appropriate
        
        Args:
            error: Exception that occurred
            response_content: Response content if any
            
        Returns:
            Tuple of (error_category, should_retry)
        """
        error_str = str(error).lower()
        
        # Network/Connection errors
        if any(keyword in error_str for keyword in [
            'connection', 'timeout', 'network', 'dns', 'resolve', 'unreachable'
        ]):
            logger.warning(f"🌐 NETWORK ERROR: {error}")
            return LLMErrorCategory.NETWORK_ERROR, True
        
        # API-specific errors
        if any(keyword in error_str for keyword in [
            'rate limit', 'quota', 'authentication', 'unauthorized', 'forbidden',
            'api key', 'invalid key', 'overloaded', 'service unavailable'
        ]):
            logger.warning(f"🔑 API ERROR: {error}")
            return LLMErrorCategory.API_ERROR, True
        
        # Empty response handling
        if response_content is not None:
            if not response_content or response_content.strip() == "":
                logger.warning(f"📭 EMPTY RESPONSE: LLM returned no content")
                return LLMErrorCategory.EMPTY_RESPONSE, True
            
            # Check for minimal content that suggests generation issues
            if len(response_content.strip()) < 10:
                logger.warning(f"📝 MINIMAL RESPONSE: Very short content ({len(response_content)} chars)")
                return LLMErrorCategory.EMPTY_RESPONSE, True
        
        # Infrastructure/Configuration errors
        if any(keyword in error_str for keyword in [
            'config', 'not found', 'missing', 'permission', 'access denied',
            'file not found', 'directory', 'path'
        ]):
            logger.error(f"⚙️ INFRASTRUCTURE ERROR: {error}")
            return LLMErrorCategory.INFRASTRUCTURE_ERROR, False
        
        # Everything else is likely an actual generation error
        logger.error(f"🤖 GENERATION ERROR: {error}")
        return LLMErrorCategory.GENERATION_ERROR, False
    
    def should_retry(self, error_category: str, attempt_number: int) -> bool:
        """Check if retry is appropriate for this error category and attempt"""
        
        if error_category not in self.retry_config:
            return False
        
        max_retries = self.retry_config[error_category]["max_retries"]
        return attempt_number <= max_retries
    
    def get_retry_delay(self, error_category: str, attempt_number: int) -> float:
        """Get appropriate delay before retry"""
        
        if error_category not in self.retry_config:
            return 0
        
        base_delay = self.retry_config[error_category]["base_delay"]
        
        # Exponential backoff for network/API errors
        if error_category in [LLMErrorCategory.NETWORK_ERROR, LLMErrorCategory.API_ERROR]:
            return base_delay * (2 ** (attempt_number - 1))  # 2, 4, 8 seconds
        
        return base_delay
    
    def handle_llm_error(self, error: Exception, response_content: str = None, 
                        operation: str = "LLM operation") -> Dict[str, Any]:
        """
        Comprehensive LLM error handling
        
        Args:
            error: Exception that occurred
            response_content: Response content if any
            operation: Description of what operation failed
            
        Returns:
            Dict with error info and retry guidance
        """
        error_category, should_retry = self.classify_error(error, response_content)
        
        error_info = {
            "operation": operation,
            "error_category": error_category,
            "error_message": str(error),
            "should_retry": should_retry,
            "is_llm_issue": error_category == LLMErrorCategory.GENERATION_ERROR,
            "is_infrastructure_issue": error_category == LLMErrorCategory.INFRASTRUCTURE_ERROR,
            "response_length": len(response_content) if response_content else 0
        }
        
        # Log appropriate message based on category
        if error_category == LLMErrorCategory.NETWORK_ERROR:
            logger.warning(f"🌐 {operation} failed due to network issue - retryable")
        elif error_category == LLMErrorCategory.API_ERROR:
            logger.warning(f"🔑 {operation} failed due to API issue - retryable")
        elif error_category == LLMErrorCategory.EMPTY_RESPONSE:
            logger.warning(f"📭 {operation} returned empty content - retryable")
        elif error_category == LLMErrorCategory.GENERATION_ERROR:
            logger.error(f"🤖 {operation} failed due to LLM generation issue - not retryable")
        elif error_category == LLMErrorCategory.INFRASTRUCTURE_ERROR:
            logger.error(f"⚙️ {operation} failed due to infrastructure issue - fix required")
        
        return error_info
    
    def validate_response_content(self, content: str, operation: str = "LLM response") -> Tuple[bool, str]:
        """
        Validate LLM response content for basic sanity checks
        
        Args:
            content: Response content to validate
            operation: Description of operation
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not content:
            return False, f"{operation}: No content returned"
        
        content = content.strip()
        
        if not content:
            return False, f"{operation}: Only whitespace returned"
        
        if len(content) < 5:
            return False, f"{operation}: Content too short ({len(content)} chars)"
        
        # Check for common API error responses
        error_indicators = [
            "error occurred", "try again", "service unavailable",
            "rate limited", "quota exceeded", "authentication failed"
        ]
        
        content_lower = content.lower()
        for indicator in error_indicators:
            if indicator in content_lower:
                return False, f"{operation}: API error in response: {indicator}"
        
        return True, ""


# Global error handler instance
_error_handler = SmartLLMErrorHandler()

def handle_llm_error(error: Exception, response_content: str = None, operation: str = "LLM operation") -> Dict[str, Any]:
    """Handle LLM errors with smart classification"""
    return _error_handler.handle_llm_error(error, response_content, operation)

def should_retry_error(error_category: str, attempt_number: int) -> bool:
    """Check if error should be retried"""
    return _error_handler.should_retry(error_category, attempt_number)

def get_retry_delay(error_category: str, attempt_number: int) -> float:
    """Get retry delay for error category"""
    return _error_handler.get_retry_delay(error_category, attempt_number)

def validate_llm_response(content: str, operation: str = "LLM response") -> Tuple[bool, str]:
    """Validate LLM response content"""
    return _error_handler.validate_response_content(content, operation)