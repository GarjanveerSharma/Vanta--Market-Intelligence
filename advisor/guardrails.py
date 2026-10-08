from __future__ import annotations

import re


def clamp_confidence(value: float) -> float:
    if not 0.0 <= value <= 1.0:
        raise ValueError("confidence must be between 0 and 1")
    return round(value, 4)


def safe_explanation(text: str, fallback: str, max_length: int = 500) -> str:
    cleaned = re.sub(r"\s+", " ", text).strip()
    if not cleaned or len(cleaned) > max_length:
        return fallback
    forbidden = ("guaranteed profit", "risk-free", "will definitely")
    if any(phrase in cleaned.casefold() for phrase in forbidden):
        return fallback
    return cleaned