"""
Unit tests for ANTHROPIC_API_KEY validation function.

Tests verify that the validation function correctly handles:
- Missing API keys
- Empty API keys
- Invalid API keys
- Valid API keys
- Network errors
- Timeout scenarios
"""

import os
import sys
from unittest.mock import patch, MagicMock
import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(__file__).rsplit('/', 2)[0])

from adw_modules.utils import validate_anthropic_api_key


class TestValidateAnthropicApiKey:
    """Test suite for validate_anthropic_api_key function."""

    def test_validate_api_key_missing(self):
        """Test validation fails when ANTHROPIC_API_KEY is not set."""
        with patch.dict(os.environ, {}, clear=False):
            # Remove the key if it exists
            if "ANTHROPIC_API_KEY" in os.environ:
                del os.environ["ANTHROPIC_API_KEY"]

            success, error = validate_anthropic_api_key()

            assert success is False
            assert error is not None
            assert "not set" in error.lower()

    def test_validate_api_key_empty(self):
        """Test validation fails when ANTHROPIC_API_KEY is empty string."""
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": ""}, clear=False):
            success, error = validate_anthropic_api_key()

            assert success is False
            assert error is not None
            assert "empty" in error.lower()

    def test_validate_api_key_whitespace_only(self):
        """Test validation fails when ANTHROPIC_API_KEY is whitespace only."""
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "   "}, clear=False):
            success, error = validate_anthropic_api_key()

            assert success is False
            assert error is not None
            assert "empty" in error.lower()

    def test_validate_api_key_valid(self):
        """Test validation succeeds when API key is valid."""
        # Mock the Anthropic module
        mock_anthropic_module = MagicMock()
        mock_anthropic_class = MagicMock()
        mock_client = MagicMock()
        mock_message = MagicMock()

        mock_anthropic_module.Anthropic = mock_anthropic_class
        mock_anthropic_class.return_value = mock_client
        mock_client.messages.create.return_value = mock_message

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test-key"}, clear=False):
            with patch.dict('sys.modules', {'anthropic': mock_anthropic_module}):
                success, error = validate_anthropic_api_key()

                assert success is True
                assert error is None

                # Verify client was created with correct parameters
                mock_anthropic_class.assert_called_once()
                call_kwargs = mock_anthropic_class.call_args[1]
                assert call_kwargs['api_key'] == "sk-ant-test-key"
                assert call_kwargs['timeout'] == 5.0

                # Verify message creation was called
                mock_client.messages.create.assert_called_once()

    def test_validate_api_key_invalid_authentication(self):
        """Test validation fails with authentication error."""
        mock_anthropic_module = MagicMock()
        mock_anthropic_class = MagicMock()
        mock_client = MagicMock()

        mock_anthropic_module.Anthropic = mock_anthropic_class
        mock_anthropic_class.return_value = mock_client
        mock_client.messages.create.side_effect = Exception("401 Unauthorized: Invalid API key")

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-invalid-key"}, clear=False):
            with patch.dict('sys.modules', {'anthropic': mock_anthropic_module}):
                success, error = validate_anthropic_api_key()

                assert success is False
                assert error is not None
                assert "invalid" in error.lower() or "unauthorized" in error.lower()

    def test_validate_api_key_permission_error(self):
        """Test validation fails with permission error."""
        mock_anthropic_module = MagicMock()
        mock_anthropic_class = MagicMock()
        mock_client = MagicMock()

        mock_anthropic_module.Anthropic = mock_anthropic_class
        mock_anthropic_class.return_value = mock_client
        mock_client.messages.create.side_effect = Exception("403 Forbidden: Insufficient permissions")

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test-key"}, clear=False):
            with patch.dict('sys.modules', {'anthropic': mock_anthropic_module}):
                success, error = validate_anthropic_api_key()

                assert success is False
                assert error is not None
                assert "permission" in error.lower()

    def test_validate_api_key_network_error(self):
        """Test validation fails gracefully with network error."""
        mock_anthropic_module = MagicMock()
        mock_anthropic_class = MagicMock()
        mock_client = MagicMock()

        mock_anthropic_module.Anthropic = mock_anthropic_class
        mock_anthropic_class.return_value = mock_client
        mock_client.messages.create.side_effect = Exception("Connection refused")

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test-key"}, clear=False):
            with patch.dict('sys.modules', {'anthropic': mock_anthropic_module}):
                success, error = validate_anthropic_api_key()

                assert success is False
                assert error is not None
                assert "failed to validate" in error.lower()

    def test_validate_api_key_timeout(self):
        """Test validation fails with timeout error."""
        mock_anthropic_module = MagicMock()
        mock_anthropic_class = MagicMock()
        mock_client = MagicMock()

        mock_anthropic_module.Anthropic = mock_anthropic_class
        mock_anthropic_class.return_value = mock_client
        import socket
        mock_client.messages.create.side_effect = socket.timeout("Request timed out")

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test-key"}, clear=False):
            with patch.dict('sys.modules', {'anthropic': mock_anthropic_module}):
                success, error = validate_anthropic_api_key()

                assert success is False
                assert error is not None
                assert len(error) > 0

    def test_validate_api_key_import_error(self):
        """Test validation fails gracefully when anthropic package is not installed."""
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test-key"}, clear=False):
            # Mock the import to raise ImportError
            with patch('builtins.__import__', side_effect=ImportError("No module named 'anthropic'")):
                success, error = validate_anthropic_api_key()

                assert success is False
                assert error is not None
                assert "anthropic package" in error.lower() or "not installed" in error.lower()

    def test_validate_api_key_unexpected_error(self):
        """Test validation handles unexpected errors gracefully."""
        mock_anthropic_module = MagicMock()
        mock_anthropic_class = MagicMock()
        mock_client = MagicMock()

        mock_anthropic_module.Anthropic = mock_anthropic_class
        mock_anthropic_class.return_value = mock_client
        mock_client.messages.create.side_effect = RuntimeError("Something went wrong")

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test-key"}, clear=False):
            with patch.dict('sys.modules', {'anthropic': mock_anthropic_module}):
                success, error = validate_anthropic_api_key()

                assert success is False
                assert error is not None
                assert "failed to validate" in error.lower() or "runtimeerror" in error.lower()

    def test_validate_api_key_uses_minimal_request(self):
        """Test that validation uses minimal tokens to reduce cost."""
        mock_anthropic_module = MagicMock()
        mock_anthropic_class = MagicMock()
        mock_client = MagicMock()
        mock_message = MagicMock()

        mock_anthropic_module.Anthropic = mock_anthropic_class
        mock_anthropic_class.return_value = mock_client
        mock_client.messages.create.return_value = mock_message

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test-key"}, clear=False):
            with patch.dict('sys.modules', {'anthropic': mock_anthropic_module}):
                validate_anthropic_api_key()

                # Verify that the API call uses minimal tokens
                call_args = mock_client.messages.create.call_args
                assert call_args[1]['max_tokens'] == 1  # Should use only 1 token
                assert call_args[1]['model'] == "claude-3-5-haiku-20241022"  # Should use cheapest model


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
