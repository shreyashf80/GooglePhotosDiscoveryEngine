"""
Gemini LLM client — wraps google-genai for structured output (JSON mode).
Uses KeyPool for key selection. Logs token usage per call.

References:
  FR-40  — structured output with Pydantic schema
  FR-53  — configurable model ID
  FR-55  — token usage logging
"""

from __future__ import annotations

import json
import logging
import typing
from typing import Any, Type, get_origin, get_args

from pydantic import BaseModel, create_model

from pipeline.llm.key_pool import KeyPool

logger = logging.getLogger(__name__)

def _create_shadow_model(model_cls: Any) -> Any:
    """Recursively create a Pydantic model clone without validation constraints (FR-40)."""
    def _shadow_type(typ: Any) -> Any:
        origin = get_origin(typ)
        if origin is not None:
            args = get_args(typ)
            new_args = tuple(_shadow_type(a) for a in args)
            if origin is list or origin is typing.List:
                return list[new_args[0]]
            elif origin is dict or origin is typing.Dict:
                return dict[new_args[0], new_args[1]]
            elif origin is typing.Union or type(origin).__name__ == "UnionType":
                return typing.Union[new_args]
            return typ
            
        if isinstance(typ, type) and issubclass(typ, BaseModel):
            return _create_shadow_model(typ)
        return typ

    if not (isinstance(model_cls, type) and issubclass(model_cls, BaseModel)):
        origin = get_origin(model_cls)
        if origin is list or origin is typing.List:
            return list[_shadow_type(get_args(model_cls)[0])]
        return model_cls

    fields = {}
    for field_name, field_info in model_cls.model_fields.items():
        new_type = _shadow_type(field_info.annotation)
        if field_info.is_required():
            fields[field_name] = (new_type, ...)
        else:
            fields[field_name] = (new_type, field_info.default)
            
    return create_model(f"{model_cls.__name__}Shadow", **fields)


class GeminiClient:
    """
    Gemini API client with key rotation and structured output support.

    Usage:
        client = GeminiClient(key_pool=pool, model_id="gemini-3.8-flash")
        result = client.generate(prompt="...", response_schema=MyModel)
    """

    def __init__(self, key_pool: KeyPool, model_id: str) -> None:
        self._key_pool = key_pool
        self._model_id = model_id
        self.last_tokens: dict[str, int] = {}

    @property
    def model_id(self) -> str:
        return self._model_id

    def _sanitize_message(self, msg: str) -> str:
        """Strip any API keys from error messages before logging or raising (NFR-6)."""
        import re
        from pipeline.config import GEMINI_API_KEYS
        sanitized = msg
        # Redact any known keys from the pool and config
        for state in self._key_pool._keys:
            if state.key:
                sanitized = sanitized.replace(state.key, "[REDACTED_KEY]")
        for key in GEMINI_API_KEYS:
            if key and len(key) > 4:
                sanitized = sanitized.replace(key, "[REDACTED_KEY]")
        # Redact generic Google API key patterns
        sanitized = re.sub(r"AIza[0-9A-Za-z\-_]{35}", "[REDACTED_KEY]", sanitized)
        # Redact key= query parameters
        sanitized = re.sub(r"(key=)[^& \n]+", r"\1[REDACTED_KEY]", sanitized)
        return sanitized

    def generate(
        self,
        prompt: str,
        response_schema: Type[BaseModel] | None = None,
        system_instruction: str | None = None,
        temperature: float = 0.2,
    ) -> dict[str, Any]:
        """
        Generate a response from Gemini.

        Args:
            prompt: The user prompt text.
            response_schema: Optional Pydantic model for structured JSON output.
            system_instruction: Optional system instruction.
            temperature: Sampling temperature.

        Returns:
            Parsed JSON response as a dict, or {"text": response_text} for unstructured.

        Raises:
            RuntimeError: If the API call fails after retries.
        """
        import time
        from google import genai
        from google.genai import types

        max_attempts = max(self._key_pool.size * 2, 3)
        last_exception = None

        for attempt in range(max_attempts):
            key = self._key_pool.acquire()
            key_index = self._key_pool.get_key_index(key)

            try:
                client = genai.Client(api_key=key)

                # Build config
                config_kwargs: dict[str, Any] = {
                    "temperature": temperature,
                }
                if response_schema:
                    config_kwargs["response_mime_type"] = "application/json"
                    config_kwargs["response_schema"] = _create_shadow_model(response_schema)

                config = types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    **config_kwargs,
                )

                response = client.models.generate_content(
                    model=self._model_id,
                    contents=prompt,
                    config=config,
                )

                self._key_pool.report_success(key)

                # Log token usage (FR-55)
                token_info = {}
                if response.usage_metadata:
                    token_info = {
                        "input_tokens": response.usage_metadata.prompt_token_count or 0,
                        "output_tokens": response.usage_metadata.candidates_token_count or 0,
                    }
                    self.last_tokens = token_info
                    logger.info(
                        "Gemini call: model=%s, key_index=%d, tokens=%s",
                        self._model_id,
                        key_index,
                        json.dumps(token_info),
                    )

                # Parse response
                text = response.text
                if not text:
                    raise RuntimeError("Gemini returned empty response text")

                if response_schema:
                    # Strip markdown code blocks if the model wrapped the JSON
                    cleaned_text = text.strip()
                    if cleaned_text.startswith("```"):
                        lines = cleaned_text.splitlines()
                        if lines[0].startswith("```"):
                            lines = lines[1:]
                        if lines and lines[-1].startswith("```"):
                            lines = lines[:-1]
                        cleaned_text = "\n".join(lines).strip()

                    try:
                        return json.loads(cleaned_text)
                    except json.JSONDecodeError as e:
                        logger.warning(
                            "JSON parse error from model=%s, key_index=%d: %s",
                            self._model_id,
                            key_index,
                            str(e),
                        )
                        raise ValueError(f"jsondecodeerror: {e}") from e

                return {"text": text, "tokens": token_info}

            except Exception as e:
                last_exception = e
                error_type = type(e).__name__
                error_str = str(e).lower()
                sanitized_msg = self._sanitize_message(str(e))

                # Check for rate limit / quota errors (FR-51)
                is_quota_error = (
                    "429" in error_str
                    or "quota" in error_str
                    or "rate" in error_str
                    or "resource_exhausted" in error_str
                    or getattr(e, "code", None) == 429
                    or getattr(e, "status", None) == "RESOURCE_EXHAUSTED"
                )

                if is_quota_error:
                    self._key_pool.report_error(key)
                    logger.warning(
                        "Rate limit/quota error: model=%s, key_index=%d, error_type=%s (attempt %d/%d)",
                        self._model_id,
                        key_index,
                        error_type,
                        attempt + 1,
                        max_attempts,
                    )
                    # Continue to try with remaining keys in pool (FR-51)
                    if attempt < max_attempts - 1:
                        continue
                else:
                    # Check for transient server / network errors
                    is_transient = (
                        "503" in error_str
                        or "500" in error_str
                        or "unavailable" in error_str
                        or "connection" in error_str
                        or "timeout" in error_str
                        or "jsondecodeerror" in error_str
                        or getattr(e, "code", None) in (500, 503)
                    )
                    if is_transient and attempt < max_attempts - 1:
                        logger.warning(
                            "Transient error: model=%s, key_index=%d, error_type=%s, retrying...",
                            self._model_id,
                            key_index,
                            error_type,
                        )
                        time.sleep(1.0)
                        continue

                    logger.error(
                        "Gemini API error: model=%s, key_index=%d, error_type=%s, message=%s",
                        self._model_id,
                        key_index,
                        error_type,
                        sanitized_msg,
                    )
                    raise RuntimeError(f"Gemini API call failed: {sanitized_msg}") from e

        # If all attempts exhausted
        final_msg = self._sanitize_message(str(last_exception)) if last_exception else "All attempts failed"
        raise RuntimeError(
            f"Gemini API call failed after {max_attempts} attempts: {final_msg}"
        ) from last_exception
