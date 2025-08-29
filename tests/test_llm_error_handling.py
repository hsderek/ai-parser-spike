"""
Unit Tests for LLM Error Handling

Tests artificial error scenarios to ensure smart exception management works properly.
"""

import pytest
import time
from unittest.mock import Mock, patch
from pathlib import Path
import sys

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dfe_ai_parser_vrl.llm.error_handler import SmartLLMErrorHandler, LLMErrorCategory
from dfe_ai_parser_vrl.llm.safe_llm_wrapper import SafeLLMWrapper


class TestSmartErrorHandling:
    """Test smart LLM error classification and handling"""
    
    def setup_method(self):
        """Setup test environment"""
        self.error_handler = SmartLLMErrorHandler()
    
    def test_network_error_classification(self):
        """Test network error detection"""
        
        network_errors = [
            ConnectionError("Connection refused"),
            TimeoutError("Request timed out"),
            Exception("DNS resolution failed"),
            Exception("Network unreachable")
        ]
        
        for error in network_errors:
            category, should_retry = self.error_handler.classify_error(error)
            
            assert category == LLMErrorCategory.NETWORK_ERROR
            assert should_retry == True, f"Network error should be retryable: {error}"
    
    def test_api_error_classification(self):
        """Test API error detection"""
        
        api_errors = [
            Exception("Rate limit exceeded"),
            Exception("Authentication failed"),
            Exception("Invalid API key"),
            Exception("Service overloaded"),
            Exception("Quota exceeded")
        ]
        
        for error in api_errors:
            category, should_retry = self.error_handler.classify_error(error)
            
            assert category == LLMErrorCategory.API_ERROR
            assert should_retry == True, f"API error should be retryable: {error}"
    
    def test_empty_response_handling(self):
        """Test empty response detection"""
        
        empty_responses = ["", "   ", "\n\n", "null"]
        
        for response in empty_responses:
            category, should_retry = self.error_handler.classify_error(
                Exception("Empty response"), response
            )
            
            assert category == LLMErrorCategory.EMPTY_RESPONSE
            assert should_retry == True, f"Empty response should be retryable: '{response}'"
    
    def test_generation_error_classification(self):
        """Test actual LLM generation error detection"""
        
        generation_errors = [
            Exception("Model generation failed"),
            Exception("Invalid prompt structure"),
            Exception("Content policy violation")
        ]
        
        for error in generation_errors:
            category, should_retry = self.error_handler.classify_error(error)
            
            assert category == LLMErrorCategory.GENERATION_ERROR
            assert should_retry == False, f"Generation error should not be retryable: {error}"
    
    def test_infrastructure_error_classification(self):
        """Test infrastructure error detection"""
        
        infra_errors = [
            FileNotFoundError("Config file not found"),
            PermissionError("Access denied"),
            Exception("Directory not found")
        ]
        
        for error in infra_errors:
            category, should_retry = self.error_handler.classify_error(error)
            
            assert category == LLMErrorCategory.INFRASTRUCTURE_ERROR
            assert should_retry == False, f"Infrastructure error should not be retryable: {error}"
    
    def test_retry_logic(self):
        """Test retry attempt logic"""
        
        # Network errors should retry up to 3 times
        assert self.error_handler.should_retry(LLMErrorCategory.NETWORK_ERROR, 1) == True
        assert self.error_handler.should_retry(LLMErrorCategory.NETWORK_ERROR, 3) == True
        assert self.error_handler.should_retry(LLMErrorCategory.NETWORK_ERROR, 4) == False
        
        # Generation errors should not retry
        assert self.error_handler.should_retry(LLMErrorCategory.GENERATION_ERROR, 1) == False
        
        # Infrastructure errors should not retry
        assert self.error_handler.should_retry(LLMErrorCategory.INFRASTRUCTURE_ERROR, 1) == False
    
    def test_retry_delays(self):
        """Test exponential backoff delays"""
        
        # Network errors should have exponential backoff
        delay1 = self.error_handler.get_retry_delay(LLMErrorCategory.NETWORK_ERROR, 1)
        delay2 = self.error_handler.get_retry_delay(LLMErrorCategory.NETWORK_ERROR, 2)
        delay3 = self.error_handler.get_retry_delay(LLMErrorCategory.NETWORK_ERROR, 3)
        
        assert delay2 > delay1, "Should have exponential backoff"
        assert delay3 > delay2, "Should have exponential backoff"


class TestSafeLLMWrapper:
    """Test safe LLM wrapper functionality"""
    
    def setup_method(self):
        """Setup test environment"""
        self.config = {
            "use_cases": {
                "test": {
                    "max_tokens": 100,
                    "temperature": 0.5,
                    "top_p": 0.9
                }
            }
        }
        self.wrapper = SafeLLMWrapper(self.config)
    
    def test_hyperparameter_extraction(self):
        """Test hyperparameter loading from config"""
        
        hyperparams = self.wrapper._get_hyperparameters("test")
        
        assert hyperparams["max_tokens"] == 100
        assert hyperparams["temperature"] == 0.5
        assert hyperparams["top_p"] == 0.9
        
        # Should have defaults for missing params
        assert "frequency_penalty" in hyperparams
        assert "presence_penalty" in hyperparams
    
    def test_fallback_model_list(self):
        """Test fallback model configuration"""
        
        assert len(self.wrapper.fallback_models) > 0
        assert all("/" in model for model in self.wrapper.fallback_models)  # Should have provider prefixes
    
    @patch('litellm.completion')
    def test_successful_completion(self, mock_completion):
        """Test successful LLM completion"""
        
        # Mock successful response
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Test VRL code here"
        mock_response.usage = Mock()
        mock_response.usage.completion_tokens = 50
        mock_response.usage.prompt_tokens = 100
        
        mock_completion.return_value = mock_response
        
        # Test completion
        response = self.wrapper.safe_completion(
            model="test-model",
            messages=[{"role": "user", "content": "Generate VRL"}],
            use_case="test"
        )
        
        assert response == mock_response
        mock_completion.assert_called_once()
    
    @patch('litellm.completion')
    def test_network_error_retry(self, mock_completion):
        """Test network error retry logic"""
        
        # Mock network error on first call, success on second
        mock_completion.side_effect = [
            ConnectionError("Network unreachable"),
            Mock(choices=[Mock(message=Mock(content="Success after retry"))])
        ]
        
        # Should retry and succeed
        response = self.wrapper.safe_completion(
            model="test-model", 
            messages=[{"role": "user", "content": "test"}]
        )
        
        assert mock_completion.call_count == 2  # Initial + 1 retry
        assert response.choices[0].message.content == "Success after retry"
    
    @patch('litellm.completion')
    def test_empty_response_fallback(self, mock_completion):
        """Test empty response fallback to next model"""
        
        # Mock empty response from first model, good response from fallback
        mock_completion.side_effect = [
            Mock(choices=[Mock(message=Mock(content=""))]),  # Empty content
            Mock(choices=[Mock(message=Mock(content="Good VRL content"))])  # Fallback success
        ]
        
        response = self.wrapper.safe_completion(
            model="failing-model",
            messages=[{"role": "user", "content": "test"}]
        )
        
        assert mock_completion.call_count == 2  # Primary + fallback
        assert response.choices[0].message.content == "Good VRL content"
    
    @patch('litellm.completion')
    def test_all_models_fail(self, mock_completion):
        """Test behavior when all models fail"""
        
        # All models fail with generation errors
        mock_completion.side_effect = Exception("Model generation failed")
        
        with pytest.raises(Exception) as exc_info:
            self.wrapper.safe_completion(
                model="failing-model",
                messages=[{"role": "user", "content": "test"}]
            )
        
        assert "Model generation failed" in str(exc_info.value)
        assert mock_completion.call_count >= 2  # Should try multiple models


def test_artificial_error_scenarios():
    """Test artificial error scenarios manually"""
    
    print("🧪 Testing Artificial Error Scenarios")
    
    error_handler = SmartLLMErrorHandler()
    
    # Test different error types
    test_scenarios = [
        (ConnectionError("Connection timeout"), "Should be network error"),
        (Exception("Rate limit exceeded"), "Should be API error"),
        (Exception(""), "Should be empty response", ""),
        (FileNotFoundError("Config not found"), "Should be infrastructure error"),
        (Exception("Model failed to generate"), "Should be generation error")
    ]
    
    for i, scenario in enumerate(test_scenarios, 1):
        error = scenario[0]
        description = scenario[1]
        response_content = scenario[2] if len(scenario) > 2 else None
        
        category, should_retry = error_handler.classify_error(error, response_content)
        
        print(f"{i}. {description}")
        print(f"   Error: {error}")
        print(f"   Category: {category}")
        print(f"   Should retry: {should_retry}")
        print()


if __name__ == "__main__":
    # Run manual tests
    test_artificial_error_scenarios()
    
    print("🎯 LLM Error Handling Tests Complete")
    print("Use 'pytest tests/test_llm_error_handling.py' for full test suite")