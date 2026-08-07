"""
tests/test_ai_service_error_handling.py — Unit tests for AI service error handling and resilience.

Tests cover:
1. Missing API key handling
2. Invalid/expired API key handling  
3. Rate limit handling with retry logic
4. Quota exceeded handling
5. Server error handling with retry logic
6. Health check functionality
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from groq import GroqError

from services.ai_service import AIService


class TestAIServiceErrorHandling:
    """Test suite for AI service error handling and resilience."""

    def test_missing_api_key_initialization(self):
        """Verify AIService handles missing GROQ_API_KEY gracefully."""
        with patch.dict('os.environ', {}, clear=True):
            ai_service = AIService()
            assert ai_service.api_key is None
            assert ai_service.client is None
            assert ai_service.is_configured() is False

    def test_empty_api_key_initialization(self):
        """Verify AIService handles empty GROQ_API_KEY gracefully."""
        with patch.dict('os.environ', {'GROQ_API_KEY': ''}, clear=True):
            ai_service = AIService()
            assert ai_service.api_key == ''
            assert ai_service.client is None
            assert ai_service.is_configured() is False

    def test_short_api_key_initialization(self):
        """Verify AIService rejects suspiciously short API keys."""
        with patch.dict('os.environ', {'GROQ_API_KEY': 'short'}, clear=True):
            ai_service = AIService()
            assert ai_service.api_key == 'short'
            assert ai_service.client is None
            assert ai_service.is_configured() is False

    def test_valid_api_key_initialization(self):
        """Verify AIService initializes correctly with valid API key."""
        with patch.dict('os.environ', {'GROQ_API_KEY': 'gsk_valid_api_key_that_is_long_enough'}, clear=True):
            ai_service = AIService()
            assert ai_service.api_key == 'gsk_valid_api_key_that_is_long_enough'
            assert ai_service.client is not None
            assert ai_service.is_configured() is True

    def test_health_check_not_configured(self):
        """Verify health check returns error when service not configured."""
        ai_service = AIService()
        # Simulate missing API key
        ai_service.api_key = None
        ai_service.client = None
        
        async def _run():
            result = await ai_service.health_check()
            assert result["groq_configured"] is False
            assert result["groq_reachable"] is False
            assert result["status"] == "error"
            assert "GROQ_API_KEY" in result["reason"]
        
        asyncio.run(_run())

    def test_health_check_success(self):
        """Verify health check succeeds when Groq is reachable."""
        ai_service = AIService()
        ai_service.api_key = "valid_key"
        
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "test"
        
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        ai_service.client = mock_client
        
        async def _run():
            result = await ai_service.health_check()
            assert result["groq_configured"] is True
            assert result["groq_reachable"] is True
            assert result["status"] == "ok"
        
        asyncio.run(_run())

    def test_health_check_groq_error(self):
        """Verify health check handles Groq errors properly."""
        ai_service = AIService()
        ai_service.api_key = "valid_key"
        
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(
            side_effect=GroqError("Authentication failed")
        )
        ai_service.client = mock_client
        
        async def _run():
            result = await ai_service.health_check()
            assert result["groq_configured"] is True
            assert result["groq_reachable"] is False
            assert result["status"] == "error"
        
        asyncio.run(_run())

    def test_analyze_code_not_configured(self):
        """Verify analyze_code handles missing configuration gracefully."""
        ai_service = AIService()
        ai_service.api_key = None
        ai_service.client = None
        
        async def _run():
            result = await ai_service.analyze_code("some diff")
            assert result["status"] == "failed"
            assert result["reason"] == "CLIENT_NOT_INITIALIZED"
        
        asyncio.run(_run())

    def test_analyze_code_empty_diff(self):
        """Verify analyze_code handles empty diff gracefully."""
        ai_service = AIService()
        ai_service.api_key = "valid_key"
        ai_service.client = MagicMock()  # Mock client
        
        async def _run():
            result = await ai_service.analyze_code("")
            assert result["status"] == "failed"
            assert result["reason"] == "EMPTY_DIFF"
        
        asyncio.run(_run())

    def test_analyze_chunk_retry_on_rate_limit(self):
        """Verify retry logic works for rate limit errors."""
        ai_service = AIService()
        ai_service.api_key = "valid_key"
        
        mock_client = MagicMock()
        # First two attempts fail with rate limit, third succeeds
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '{"issues": []}'
        
        call_count = [0]
        async def side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] < 3:
                raise GroqError("Rate limit exceeded (429)")
            return mock_response
        
        mock_client.chat.completions.create = AsyncMock(side_effect=side_effect)
        ai_service.client = mock_client
        
        async def _run():
            result = await ai_service._analyze_chunk_with_retry("some diff")
            assert result is not None
            assert result.get("issues") == []
            assert call_count[0] == 3  # Should have retried
        
        asyncio.run(_run())

    def test_analyze_chunk_auth_error_no_retry(self):
        """Verify auth errors don't trigger retries."""
        ai_service = AIService()
        ai_service.api_key = "valid_key"
        
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(
            side_effect=GroqError("Authentication failed (401)")
        )
        ai_service.client = mock_client
        
        async def _run():
            result = await ai_service._analyze_chunk_with_retry("some diff")
            assert result is not None
            assert result["status"] == "error"
            assert result["reason"] == "AUTH_ERROR"
        
        asyncio.run(_run())

    def test_analyze_chunk_quota_error_no_retry(self):
        """Verify quota errors don't trigger retries."""
        ai_service = AIService()
        ai_service.api_key = "valid_key"
        
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(
            side_effect=GroqError("Quota exceeded")
        )
        ai_service.client = mock_client
        
        async def _run():
            result = await ai_service._analyze_chunk_with_retry("some diff")
            assert result is not None
            assert result["status"] == "error"
            assert result["reason"] == "QUOTA_EXCEEDED"
        
        asyncio.run(_run())

    def test_analyze_chunk_server_error_retry(self):
        """Verify server errors trigger retries."""
        ai_service = AIService()
        ai_service.api_key = "valid_key"
        
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '{"issues": []}'
        
        call_count = [0]
        async def side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] < 2:
                raise GroqError("Internal server error (500)")
            return mock_response
        
        mock_client.chat.completions.create = AsyncMock(side_effect=side_effect)
        ai_service.client = mock_client
        
        async def _run():
            result = await ai_service._analyze_chunk_with_retry("some diff")
            assert result is not None
            assert result.get("issues") == []
            assert call_count[0] == 2  # Should have retried once
        
        asyncio.run(_run())

    def test_analyze_chunk_max_retries_exceeded(self):
        """Verify failure after max retries."""
        ai_service = AIService()
        ai_service.api_key = "valid_key"
        
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(
            side_effect=GroqError("Rate limit exceeded (429)")
        )
        ai_service.client = mock_client
        
        async def _run():
            result = await ai_service._analyze_chunk_with_retry("some diff")
            assert result is not None
            assert result["status"] == "error"
            assert result["reason"] == "RATE_LIMIT"
        
        asyncio.run(_run())

    def test_analyze_chunk_json_parse_error(self):
        """Verify JSON parse errors are handled gracefully."""
        ai_service = AIService()
        ai_service.api_key = "valid_key"
        
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "invalid json"
        
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        ai_service.client = mock_client
        
        async def _run():
            result = await ai_service._analyze_chunk_with_retry("some diff")
            assert result is not None
            assert result["status"] == "error"
            assert result["reason"] == "JSON_PARSE_ERROR"
        
        asyncio.run(_run())