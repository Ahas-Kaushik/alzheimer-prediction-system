"""NER + regex-based parser that maps raw OCR text to structured clinical fields."""
from __future__ import annotations

import re
from typing import Any, Optional


FIELD_PATTERNS: dict[str, str] = {
    "hemoglobin":        r"hemoglobin[:\s]+(\d+\.?\d*)",
    "glucose_fasting":   r"(?:fasting\s+)?glucose[:\s]+(\d+\.?\d*)",
    "cholesterol_total": r"(?:total\s+)?cholesterol[:\s]+(\d+\.?\d*)",
    "hdl":               r"\bhdl[:\s]+(\d+\.?\d*)",
    "ldl":               r"\bldl[:\s]+(\d+\.?\d*)",
    "triglycerides":     r"triglycerides?[:\s]+(\d+\.?\d*)",
    "vitamin_b12":       r"(?:vitamin\s+)?b[- ]?12[:\s]+(\d+\.?\d*)",
    "thyroid_tsh":       r"tsh[:\s]+(\d+\.?\d*)",
    "mmse_score":        r"mmse[:\s]+(\d+)",
    "moca_score":        r"moca[:\s]+(\d+)",
    "cdr_score":         r"cdr[:\s]+(\d+\.?\d*)",
    "apoe4_status":      r"apoe[- ]?4[:\s]+(positive|negative|carrier|unknown)",
    "amyloid_beta_42":   r"amyloid[- ]?beta[- ]?(?:42)?[:\s]+(\d+\.?\d*)",
    "tau_protein":       r"\btau[:\s]+(\d+\.?\d*)",
    "p_tau_181":         r"p[- ]?tau[- ]?(?:181)?[:\s]+(\d+\.?\d*)",
    "hippocampal_volume": r"hippocampal[- ]?volume[:\s]+(\d+\.?\d*)",
    "cortical_thickness": r"cortical[- ]?thickness[:\s]+(\d+\.?\d*)",
}

_BOOL_KEYWORDS: dict[str, list[str]] = {
    "smoking_history": ["smoker", "smoking history", "tobacco"],
    "diabetes":        ["diabetes", "diabetic", "dm type"],
    "hypertension":    ["hypertension", "htn", "high blood pressure"],
    "depression_history": ["depression", "depressive", "mdd"],
    "family_history_ad": ["family history", "familial alzheimer", "family ad"],
}

_NUMERIC_FIELDS = {
    "hemoglobin", "glucose_fasting", "cholesterol_total", "hdl", "ldl",
    "triglycerides", "vitamin_b12", "thyroid_tsh",
    "mmse_score", "moca_score", "cdr_score",
    "amyloid_beta_42", "tau_protein", "p_tau_181",
    "hippocampal_volume", "cortical_thickness",
}


def parse_report(raw_text: str) -> dict[str, Any]:
    """Extract structured clinical fields from raw OCR text.

    Args:
        raw_text: Plain text extracted by the OCR engine.

    Returns:
        Dict with field names as keys and parsed values (float, str, bool).
        Missing fields are omitted from the dict.
    """
    text = raw_text.lower()
    result: dict[str, Any] = {}

    for field, pattern in FIELD_PATTERNS.items():
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            value_str = match.group(1).strip()
            if field in _NUMERIC_FIELDS:
                try:
                    result[field] = float(value_str)
                except ValueError:
                    pass
            else:
                result[field] = _normalize_categorical(field, value_str)

    for field, keywords in _BOOL_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                result[field] = True
                break

    return result


def _normalize_categorical(field: str, raw: str) -> str:
    raw = raw.lower().strip()
    if field == "apoe4_status":
        if raw in {"positive", "carrier"}:
            return "Positive"
        if raw == "negative":
            return "Negative"
        return "Unknown"
    return raw.title()
