"""Google Gemini client.

If ``GEMINI_API_KEY`` is set the model is used; otherwise callers fall back to
deterministic templated text so the app works fully offline with no key.
"""
from __future__ import annotations

from typing import Optional

from backend.config import settings
from backend.utils.logger import get_logger

logger = get_logger(__name__)

_configured = False


def is_enabled() -> bool:
    """True when a Gemini key is present and the SDK is importable."""
    if not settings.gemini_api_key:
        return False
    try:
        import google.generativeai  # noqa: F401
        return True
    except ImportError:
        logger.warning("google-generativeai not installed; Gemini disabled")
        return False


def _ensure_configured() -> None:
    global _configured
    if _configured:
        return
    import google.generativeai as genai
    genai.configure(api_key=settings.gemini_api_key)
    _configured = True


def complete(prompt: str, system: Optional[str] = None) -> Optional[str]:
    """Generate text with Gemini. Returns None on any failure (caller falls back)."""
    if not is_enabled():
        return None
    try:
        import google.generativeai as genai
        _ensure_configured()
        model = genai.GenerativeModel(
            settings.gemini_model,
            system_instruction=system or (
                "You are a clinical decision-support assistant for an Alzheimer's "
                "screening tool. Be concise, evidence-based and cautious. Always "
                "remind the user that outputs are decision support, not a diagnosis."
            ),
        )
        resp = model.generate_content(prompt)
        return (resp.text or "").strip() or None
    except Exception as e:  # noqa: BLE001
        logger.warning(f"Gemini generation failed ({e}); using templated fallback")
        return None
