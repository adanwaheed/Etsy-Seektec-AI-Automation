"""Shared Google Gemini client helpers with retry and model fallback."""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from typing import Callable, Generic, TypeVar

from google import genai
from google.genai import types

LOGGER = logging.getLogger(__name__)
T = TypeVar("T")


class GeminiConfigurationError(RuntimeError):
    """Raised when Gemini is not configured correctly."""


class GeminiRequestError(RuntimeError):
    """Raised after all safe Gemini retries and fallbacks fail."""


@dataclass(frozen=True)
class GeminiCallResult(Generic[T]):
    """A successful response together with the model that produced it."""

    response: T
    model: str
    attempted_models: tuple[str, ...]


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        value = default
    return max(minimum, min(maximum, value))


def _env_float(name: str, default: float, minimum: float, maximum: float) -> float:
    try:
        value = float(os.getenv(name, str(default)))
    except ValueError:
        value = default
    return max(minimum, min(maximum, value))


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        cleaned = value.strip().removeprefix("models/")
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            result.append(cleaned)
    return result


def get_gemini_api_key() -> str:
    """Return the configured API key or raise a readable error."""

    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key or api_key == "your_gemini_api_key_here":
        raise GeminiConfigurationError(
            "GEMINI_API_KEY is missing. Open the .env file and paste a key created in Google AI Studio."
        )
    return api_key


def get_gemini_model() -> str:
    """Return the primary configured multimodal model name."""

    return os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip() or "gemini-2.5-flash"


def get_configured_model_candidates() -> list[str]:
    """Return the primary model followed by explicitly configured fallbacks."""

    fallback_text = os.getenv("GEMINI_FALLBACK_MODELS", "gemini-2.5-flash-lite")
    return _unique([get_gemini_model(), *fallback_text.split(",")])


def create_gemini_client() -> genai.Client:
    """Create a Gemini client with bounded automatic retries for transient failures."""

    retry_attempts = _env_int("GEMINI_RETRY_ATTEMPTS", 4, 1, 8)
    timeout_seconds = _env_int("GEMINI_TIMEOUT_SECONDS", 120, 20, 600)
    initial_delay = _env_float("GEMINI_RETRY_INITIAL_DELAY", 1.0, 0.1, 30.0)
    max_delay = _env_float("GEMINI_RETRY_MAX_DELAY", 12.0, 1.0, 60.0)

    http_options = types.HttpOptions(
        timeout=timeout_seconds * 1000,
        retry_options=types.HttpRetryOptions(
            attempts=retry_attempts,
            initial_delay=initial_delay,
            max_delay=max_delay,
            exp_base=2.0,
            jitter=0.5,
            http_status_codes=[408, 429, 500, 502, 503, 504],
        ),
    )
    return genai.Client(api_key=get_gemini_api_key(), http_options=http_options)


def _error_text(exc: Exception) -> str:
    return str(exc).strip()


def _contains_status(text: str, code: int) -> bool:
    return bool(re.search(rf"(?<!\d){code}(?!\d)", text))


def _is_auth_error(text: str) -> bool:
    lowered = text.lower()
    return (
        _contains_status(text, 401)
        or "unauthenticated" in lowered
        or "api key not valid" in lowered
        or "invalid api key" in lowered
        or "api_key_invalid" in lowered
    )


def _is_permission_error(text: str) -> bool:
    lowered = text.lower()
    return _contains_status(text, 403) or "permission_denied" in lowered


def _is_quota_error(text: str) -> bool:
    lowered = text.lower()
    return (
        _contains_status(text, 429)
        or "resource_exhausted" in lowered
        or "quota exceeded" in lowered
        or "rate limit" in lowered
    )


def _is_temporary_error(text: str) -> bool:
    lowered = text.lower()
    return (
        any(_contains_status(text, code) for code in (408, 500, 502, 503, 504))
        or "temporarily overloaded" in lowered
        or "high demand" in lowered
        or "deadline_exceeded" in lowered
        or "service unavailable" in lowered
    )


def _is_model_specific_error(text: str) -> bool:
    """Return True only for model-name/capability problems, not generic 503 UNAVAILABLE."""

    lowered = text.lower()
    if _contains_status(text, 404) or "not_found" in lowered:
        return True
    model_markers = (
        "model is not found",
        "model not found",
        "model is not available for",
        "not found for api version",
        "does not support generatecontent",
        "does not support generate content",
        "response schema is not supported",
        "structured output is not supported",
        "unsupported model",
    )
    return any(marker in lowered for marker in model_markers)


def _model_name(model: object) -> str:
    value = str(getattr(model, "name", "") or "").strip()
    return value.removeprefix("models/")


def _supports_generate_content(model: object) -> bool:
    actions = getattr(model, "supported_actions", None)
    if actions is None:
        actions = getattr(model, "supported_generation_methods", None)
    if not actions:
        return True
    return any("generatecontent" in str(action).replace("_", "").lower() for action in actions)


def _discovery_rank(name: str) -> tuple[int, int, tuple[int, ...], str]:
    lowered = name.lower()
    preview_penalty = 1 if any(word in lowered for word in ("preview", "experimental", "exp")) else 0
    # Flash-Lite is usually the least demanding fallback, then standard Flash.
    family_rank = 0 if "flash-lite" in lowered else 1
    versions = tuple(-int(part) for part in re.findall(r"\d+", lowered)[:3])
    return preview_penalty, family_rank, versions, lowered


def discover_flash_models(client: genai.Client, excluded: set[str]) -> list[str]:
    """Discover additional available multimodal Flash models for the current API key."""

    if not _env_bool("GEMINI_AUTO_DISCOVER_MODELS", True):
        return []

    maximum = _env_int("GEMINI_MAX_DISCOVERED_MODELS", 4, 0, 10)
    if maximum == 0:
        return []

    try:
        discovered: list[str] = []
        blocked_terms = ("image", "embedding", "tts", "live", "audio", "aqa", "veo")
        for model in client.models.list():
            name = _model_name(model)
            lowered = name.lower()
            if not name or name in excluded:
                continue
            if "gemini" not in lowered or "flash" not in lowered:
                continue
            if any(term in lowered for term in blocked_terms):
                continue
            if not _supports_generate_content(model):
                continue
            discovered.append(name)

        return _unique(sorted(discovered, key=_discovery_rank))[:maximum]
    except Exception as exc:  # Discovery is optional and must never hide the original error.
        LOGGER.warning("Could not discover Gemini fallback models: %s", exc)
        return []


def friendly_gemini_error(exc: Exception, attempted_models: list[str] | tuple[str, ...] = ()) -> str:
    """Convert common SDK/API errors into an accurate user-facing message."""

    text = _error_text(exc)
    attempted = ", ".join(attempted_models)
    tried_suffix = f" The app tried: {attempted}." if attempted else ""

    # Order matters: a 503 response often includes the words 'model' and 'UNAVAILABLE',
    # but that does not mean the model name is invalid.
    if _is_auth_error(text):
        return (
            "The Gemini API key was rejected. Copy a valid key from Google AI Studio into "
            "GEMINI_API_KEY in .env, save the file, and restart the server."
        )
    if _is_permission_error(text):
        return (
            "Google denied this request. Check that the Gemini API is available to the Google project "
            "linked to this key and that the selected model is allowed for the account or region."
            + tried_suffix
        )
    if _is_quota_error(text):
        return (
            "The Gemini free-tier request limit or quota was reached. The app already retried and tried "
            "available fallback models. Wait for the quota window to reset, reduce request frequency, "
            "or enable billing for higher limits."
            + tried_suffix
        )
    if _is_temporary_error(text):
        return (
            "Gemini is temporarily busy or unavailable. The app already used exponential retries and "
            "tried fallback models. Wait about one minute and press Generate again."
            + tried_suffix
        )
    if _is_model_specific_error(text):
        return (
            "None of the configured Gemini models could handle this request. Open .env and set "
            "GEMINI_MODEL to a model shown in Google AI Studio, or leave automatic model discovery enabled."
            + tried_suffix
        )
    return f"Gemini API request failed: {text}{tried_suffix}"


def generate_content_with_fallback(
    client: genai.Client,
    request: Callable[[str], T],
) -> GeminiCallResult[T]:
    """Run a Gemini request with SDK retries, configured fallbacks, and model discovery.

    The Google SDK performs bounded exponential retries for 429 and transient 5xx
    errors. If one model remains unavailable after those retries, this function
    moves to the next configured or discovered Flash model.
    """

    candidates = get_configured_model_candidates()
    attempted: list[str] = []
    failures: list[tuple[str, Exception]] = []

    def try_models(models: list[str]) -> GeminiCallResult[T] | None:
        for model in models:
            if model in attempted:
                continue
            attempted.append(model)
            try:
                response = request(model)
                return GeminiCallResult(
                    response=response,
                    model=model,
                    attempted_models=tuple(attempted),
                )
            except Exception as exc:
                failures.append((model, exc))
                text = _error_text(exc)
                LOGGER.warning("Gemini model %s failed: %s", model, text)

                # Authentication and general permissions will not improve by changing models.
                if _is_auth_error(text) or (_is_permission_error(text) and not _is_model_specific_error(text)):
                    raise GeminiRequestError(friendly_gemini_error(exc, attempted)) from exc

                # Safe model fallback is intended for capacity, quota, missing-model,
                # and model-capability failures. Other errors indicate a code/input problem.
                if not (
                    _is_temporary_error(text)
                    or _is_quota_error(text)
                    or _is_model_specific_error(text)
                ):
                    raise GeminiRequestError(friendly_gemini_error(exc, attempted)) from exc
        return None

    result = try_models(candidates)
    if result is not None:
        return result

    discovered = discover_flash_models(client, set(attempted))
    result = try_models(discovered)
    if result is not None:
        return result

    if failures:
        last_exc = failures[-1][1]
        raise GeminiRequestError(friendly_gemini_error(last_exc, attempted)) from last_exc

    raise GeminiRequestError("No Gemini model candidates were configured or discovered.")
