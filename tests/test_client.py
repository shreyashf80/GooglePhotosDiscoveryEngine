"""
Unit tests for GeminiClient — key rotation, error handling, markdown parsing, and secrets redaction.

References:
  FR-40  — structured output
  FR-51  — key rotation on 429/quota error
  FR-55  — token usage tracking
  NFR-6  — secrets not logged
"""

from unittest.mock import MagicMock, patch
import pytest
from pydantic import BaseModel

from pipeline.llm.client import GeminiClient
from pipeline.llm.key_pool import KeyPool


class DummySchema(BaseModel):
    name: str
    count: int


class TestGeminiClientKeyRotation:
    """Test FR-51 key rotation on quota error."""

    def test_client_retries_on_quota_error_and_uses_next_key(self):
        pool = KeyPool(keys=["bad_key_1", "good_key_2"], rpm_per_key=100)
        client = GeminiClient(key_pool=pool, model_id="gemini-test")

        # Mock genai.Client
        mock_response = MagicMock()
        mock_response.text = '{"name": "test", "count": 42}'
        mock_response.usage_metadata = MagicMock(prompt_token_count=10, candidates_token_count=20)

        call_keys = []

        def mock_generate_content(*args, **kwargs):
            nonlocal call_keys
            # The client should have been instantiated with one of the keys
            if len(call_keys) == 0:
                call_keys.append("bad_key_1")
                # First call fails with 429 quota error
                err = Exception("429 ResourceExhausted: Quota exceeded")
                err.code = 429
                raise err
            else:
                call_keys.append("good_key_2")
                return mock_response

        with patch("google.genai.Client") as mock_client_cls:
            mock_instance = MagicMock()
            mock_instance.models.generate_content.side_effect = mock_generate_content
            mock_client_cls.return_value = mock_instance

            result = client.generate(prompt="hello", response_schema=DummySchema)

            assert result == {"name": "test", "count": 42}
            # Verify bad_key_1 was put in cooldown and good_key_2 was used
            assert pool.available_count() == 1
            assert pool._find_state("bad_key_1").cooldown_until > 0


class TestGeminiClientSecretsRedaction:
    """Test NFR-6: API keys are never exposed in error messages or logs."""

    def test_client_redacts_api_keys_in_error_messages(self):
        pool = KeyPool(keys=["AIzaSySuperSecretKeyXYZ123"], rpm_per_key=100)
        client = GeminiClient(key_pool=pool, model_id="gemini-test")

        with patch("google.genai.Client") as mock_client_cls:
            mock_instance = MagicMock()
            mock_instance.models.generate_content.side_effect = Exception(
                "Request failed with URL: https://generativelanguage.googleapis.com/v1beta?key=AIzaSySuperSecretKeyXYZ123"
            )
            mock_client_cls.return_value = mock_instance

            with pytest.raises(RuntimeError) as exc_info:
                client.generate(prompt="hello")

            err_msg = str(exc_info.value)
            assert "AIzaSySuperSecretKeyXYZ123" not in err_msg
            assert "[REDACTED_KEY]" in err_msg


class TestGeminiClientResponseHandling:
    """Test structured output parsing and edge cases."""

    def test_client_handles_markdown_wrapped_json(self):
        pool = KeyPool(keys=["k1"], rpm_per_key=100)
        client = GeminiClient(key_pool=pool, model_id="gemini-test")

        mock_response = MagicMock()
        mock_response.text = '```json\n{"name": "wrapped", "count": 7}\n```'
        mock_response.usage_metadata = MagicMock(prompt_token_count=5, candidates_token_count=5)

        with patch("google.genai.Client") as mock_client_cls:
            mock_instance = MagicMock()
            mock_instance.models.generate_content.return_value = mock_response
            mock_client_cls.return_value = mock_instance

            result = client.generate(prompt="hello", response_schema=DummySchema)
            assert result == {"name": "wrapped", "count": 7}

    def test_client_handles_empty_response(self):
        pool = KeyPool(keys=["k1"], rpm_per_key=100)
        client = GeminiClient(key_pool=pool, model_id="gemini-test")

        mock_response = MagicMock()
        mock_response.text = None
        mock_response.usage_metadata = None

        with patch("google.genai.Client") as mock_client_cls:
            mock_instance = MagicMock()
            mock_instance.models.generate_content.return_value = mock_response
            mock_client_cls.return_value = mock_instance

            with pytest.raises(RuntimeError, match="empty response"):
                client.generate(prompt="hello")

    def test_client_tracks_token_usage(self):
        pool = KeyPool(keys=["k1"], rpm_per_key=100)
        client = GeminiClient(key_pool=pool, model_id="gemini-test")

        mock_response = MagicMock()
        mock_response.text = '{"name": "tokens", "count": 1}'
        mock_response.usage_metadata = MagicMock(prompt_token_count=123, candidates_token_count=456)

        with patch("google.genai.Client") as mock_client_cls:
            mock_instance = MagicMock()
            mock_instance.models.generate_content.return_value = mock_response
            mock_client_cls.return_value = mock_instance

            client.generate(prompt="hello", response_schema=DummySchema)
            assert client.last_tokens == {"input_tokens": 123, "output_tokens": 456}
