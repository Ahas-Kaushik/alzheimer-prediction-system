"""Google Gemini client.

If ``GEMINI_API_KEY`` is set the model is used; otherwise callers fall back to
deterministic templated text so the app works fully offline with no key.

Calls use a short HTTP timeout and never raise. A stalled Gemini request must
not block the API.
"""
from __future__ import annotations

from typing import Optional

from backend.config import settings
from backend.utils.logger import get_logger

logger = get_logger(__name__)

_client = None
_TIMEOUT_MS = 20_000

_SYSTEM = (
    "You are a clinical decision-support assistant for an Alzheimer's "
    "screening tool. Be concise, evidence-based and cautious. Always "
    "remind the user that outputs are decision support, not a diagnosis."
)


def is_enabled() -> bool:
    """True when a Gemini key is present and the current SDK imports."""
    if not settings.gemini_api_key:
        return False
    try:
        from google import genai  # noqa: F401
        return True
    except ImportError:
        logger.warning("google-genai not installed; Gemini disabled")
        return False


def _get_client():
    global _client
    if _client is not None:
        return _client
    from google import genai
    from google.genai import types

    _client = genai.Client(
        api_key=settings.gemini_api_key,
        http_options=types.HttpOptions(timeout=_TIMEOUT_MS),
    )
    return _client


def complete(prompt: str, system: Optional[str] = None) -> Optional[str]:
    """Generate text with Gemini. Returns None on any failure (caller falls back)."""
    if not is_enabled():
        return None
    try:
        from google.genai import types

        client = _get_client()
        resp = client.models.generate_content(
            model=settings.gemini_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system or _SYSTEM,
            ),
        )
        text = getattr(resp, "text", None)
        return (text or "").strip() or None
    except Exception as e:  # noqa: BLE001
        logger.warning(f"Gemini generation failed ({e}); using templated fallback")
        return None
