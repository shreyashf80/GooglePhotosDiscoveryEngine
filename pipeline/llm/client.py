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

class ServiceUnavailableError(Exception):
    """Raised when the API returns 503 continuously for 10 minutes."""
    pass

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

        start_time = time.time()
        last_exception = None
        attempt = 0
        transient_503_retries = 0

        while True:
            attempt += 1
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
                        "Rate limit/quota error: model=%s, key_index=%d, error_type=%s (attempt %d)",
                        self._model_id,
                        key_index,
                        error_type,
                        attempt,
                    )
                    if time.time() - start_time > 600:
                        break
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
                    if is_transient:
                        print(f"Exception: {e}")
                        logger.warning(
                            "Transient error: model=%s, key_index=%d, error_type=%s, retrying...",
                            self._model_id,
                            key_index,
                            error_type,
                        )
                        if time.time() - start_time > 600:
                            raise ServiceUnavailableError("Gemini API consistently unavailable for 10 minutes.") from e
                            
                        if "503" in error_str or getattr(e, "code", None) == 503:
                            transient_503_retries += 1
                            if transient_503_retries <= 5:
                                backoff_time = 2 ** transient_503_retries
                                logger.info("503 received. Backing off for %ds (attempt %d/5)", backoff_time, transient_503_retries)
                                time.sleep(backoff_time)
                                continue
                            
                            from pipeline.config import GEMINI_FALLBACK_MODELS
                            
                            # Shift to the next fallback model if any are available and we haven't tried them all
                            if not hasattr(self, '_fallback_idx'):
                                self._fallback_idx = 0
                                
                            if GEMINI_FALLBACK_MODELS and self._fallback_idx < len(GEMINI_FALLBACK_MODELS):
                                self._model_id = GEMINI_FALLBACK_MODELS[self._fallback_idx]
                                self._fallback_idx += 1
                                logger.info("Falling back to model %s due to 503.", self._model_id)
                                transient_503_retries = 0
                            else:
                                raise ServiceUnavailableError("Gemini API consistently unavailable across all fallbacks.") from e

                        time.sleep(2.0)
                        continue

                    logger.error(
                        "Gemini API error: model=%s, key_index=%d, error_type=%s, message=%s",
                        self._model_id,
                        key_index,
                        error_type,
                        sanitized_msg,
                    )
                    raise RuntimeError(f"Gemini API call failed: {sanitized_msg}") from e

        # If we broke out of loop (e.g. quota timeout)
        final_msg = self._sanitize_message(str(last_exception)) if last_exception else "All attempts failed"
        raise RuntimeError(
            f"Gemini API call failed after retries: {final_msg}"
        ) from last_exception


class GroqClient:
    """Groq API client with key rotation and structured output support."""

    def __init__(self, key_pool: KeyPool, model_id: str) -> None:
        self._key_pool = key_pool
        self._model_id = model_id
        self.last_tokens: dict[str, int] = {}

    @property
    def model_id(self) -> str:
        return self._model_id

    def generate(
        self,
        prompt: str,
        response_schema: Type[BaseModel] | None = None,
        system_instruction: str | None = None,
        temperature: float = 0.2,
    ) -> dict[str, Any]:
        import time
        from groq import Groq

        start_time = time.time()
        last_exception = None
        attempt = 0

        while True:
            attempt += 1
            key = self._key_pool.acquire()
            key_index = self._key_pool.get_key_index(key)

            try:
                client = Groq(api_key=key, max_retries=0)

                is_list_schema = False
                if response_schema:
                    import typing
                    from typing import get_origin
                    origin = get_origin(response_schema)
                    if origin in (list, typing.List):
                        is_list_schema = True

                prompt_content = prompt
                if is_list_schema:
                    prompt_content += "\n\nIMPORTANT: Return a JSON object with key 'records' containing the list of items matching the schema: {\"records\": [...]}. Output ONLY valid JSON."
                elif response_schema and "json" not in prompt_content.lower():
                    prompt_content += "\n\nOutput ONLY valid JSON."

                messages = []
                if system_instruction:
                    messages.append({"role": "system", "content": system_instruction})
                messages.append({"role": "user", "content": prompt_content})

                kwargs: dict[str, Any] = {
                    "model": self._model_id,
                    "messages": messages,
                    "temperature": temperature,
                }
                
                # Note: Groq structured JSON mode requires 'json' in the prompt and an object at the root.
                if response_schema:
                    kwargs["response_format"] = {"type": "json_object"}

                response = client.chat.completions.create(**kwargs)

                self._key_pool.report_success(key)

                token_info = {}
                if response.usage:
                    token_info = {
                        "input_tokens": response.usage.prompt_tokens or 0,
                        "output_tokens": response.usage.completion_tokens or 0,
                    }
                    self.last_tokens = token_info
                    logger.info("Groq call: model=%s, key_index=%d, tokens=%s", self._model_id, key_index, json.dumps(token_info))

                text = response.choices[0].message.content
                if not text:
                    raise RuntimeError("Groq returned empty response text")

                if response_schema:
                    cleaned_text = text.strip()
                    if cleaned_text.startswith("```"):
                        lines = cleaned_text.splitlines()
                        if lines[0].startswith("```"):
                            lines = lines[1:]
                        if lines and lines[-1].startswith("```"):
                            lines = lines[:-1]
                        cleaned_text = "\n".join(lines).strip()

                    try:
                        parsed = json.loads(cleaned_text)
                    except json.JSONDecodeError as e:
                        logger.warning("JSON parse error from model=%s, key_index=%d: %s", self._model_id, key_index, str(e))
                        raise ValueError(f"jsondecodeerror: {e}") from e

                    if is_list_schema:
                        if isinstance(parsed, list):
                            return parsed
                        if isinstance(parsed, dict):
                            for key_candidate in ("records", "items", "data", "results", "episodes"):
                                if key_candidate in parsed and isinstance(parsed[key_candidate], list):
                                    return parsed[key_candidate]
                            for k, v in parsed.items():
                                if isinstance(v, list):
                                    return v
                            return [parsed]

                    return parsed

                return {"text": text, "tokens": token_info}

            except Exception as e:
                last_exception = e
                error_str = str(e).lower()

                is_quota_error = "429" in error_str or "quota" in error_str or "rate limit" in error_str or "tpm" in error_str or "token" in error_str
                
                if is_quota_error:
                    self._key_pool.report_error(key)
                    logger.warning("Rate limit/quota on key_index=%d, rotating to next key (attempt %d)", key_index, attempt)
                    if time.time() - start_time > 600:
                        break
                    time.sleep(1.0)
                    continue
                else:
                    is_transient = "503" in error_str or "500" in error_str or "timeout" in error_str or "connection" in error_str
                    if is_transient:
                        logger.warning("Transient error: model=%s, key_index=%d, retrying...", self._model_id, key_index)
                        if time.time() - start_time > 600:
                            raise ServiceUnavailableError("Groq API consistently unavailable") from e
                        time.sleep(2.0)
                        continue

                    raise RuntimeError(f"Groq API call failed: {e}") from e

        raise RuntimeError(f"Groq API call failed after retries: {last_exception}") from last_exception


class HybridClient:
    """Tries primary client first, falls back to secondary on persistent error or exhaustion."""

    def __init__(self, primary_client, fallback_client):
        self.primary = primary_client
        self.fallback = fallback_client
        self.last_tokens: dict[str, int] = {}
        
    @property
    def model_id(self) -> str:
        return f"{self.primary.model_id} / {self.fallback.model_id}"

    def generate(self, prompt: str, response_schema: Type[BaseModel] | None = None, system_instruction: str | None = None, temperature: float = 0.2) -> dict[str, Any]:
        try:
            res = self.primary.generate(prompt, response_schema, system_instruction, temperature)
            self.last_tokens = self.primary.last_tokens
            return res
        except Exception as e:
            logger.warning("Primary client failed with %s. Falling back to secondary client.", type(e).__name__)
            res = self.fallback.generate(prompt, response_schema, system_instruction, temperature)
            self.last_tokens = self.fallback.last_tokens
            return res

def get_client(model_type: str = "extract") -> HybridClient:
    from pipeline.config import (
        GEMINI_API_KEYS, GEMINI_RPM_PER_KEY, GEMINI_EXTRACT_MODEL, GEMINI_FILTER_MODEL, GEMINI_CHAT_MODEL,
        GROQ_API_KEYS, GROQ_RPM_PER_KEY, GROQ_EXTRACT_MODEL
    )
    
    groq_pool = KeyPool(keys=GROQ_API_KEYS, rpm_per_key=GROQ_RPM_PER_KEY)
    gemini_pool = KeyPool(keys=GEMINI_API_KEYS, rpm_per_key=GEMINI_RPM_PER_KEY)
    
    if model_type == "extract":
        gemini_model = GEMINI_EXTRACT_MODEL
    elif model_type == "filter":
        gemini_model = GEMINI_FILTER_MODEL
    else:
        gemini_model = GEMINI_CHAT_MODEL
        
    groq_model = GROQ_EXTRACT_MODEL
    
    primary = GroqClient(key_pool=groq_pool, model_id=groq_model)
    fallback = GeminiClient(key_pool=gemini_pool, model_id=gemini_model)
    
    return HybridClient(primary, fallback)
