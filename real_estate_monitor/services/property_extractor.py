from __future__ import annotations

import re


def _extract_int(text: str | None) -> int | None:
    if text is None:
        return None
    match = re.search(r"(\d+)", text)
    if match:
        return int(match.group(1))
    return None


def _extract_float(text: str | None) -> float | None:
    if text is None:
        return None
    text = text.replace(",", ".")
    match = re.search(r"(\d+(?:\.\d+)?)", text)
    if match:
        return float(match.group(1))
    return None


def _keyword_int(text: str, keywords: list[str]) -> int | None:
    """Return the number immediately before any of the given keywords (case-insensitive)."""
    pattern = r"(\d+)\D{0,8}(?:" + "|".join(keywords) + r")"
    m = re.search(pattern, text, re.IGNORECASE)
    return int(m.group(1)) if m else None


def extract_bedrooms(text: str | None) -> int | None:
    if text is None:
        return None
    # Suites are subsets of bedrooms; prefer quartos/dormitorios count
    result = _keyword_int(text, [r"quarto", r"dormit"])
    if result is None:
        result = _keyword_int(text, [r"suite", r"suíte"])
    return result if result is not None else _extract_int(text)


def extract_bathrooms(text: str | None) -> int | None:
    if text is None:
        return None
    result = _keyword_int(text, [r"banheir", r"\bwc\b"])
    return result if result is not None else _extract_int(text)


def extract_parking(text: str | None) -> int | None:
    if text is None:
        return None
    result = _keyword_int(text, [r"vaga", r"garagem", r"garage"])
    return result if result is not None else _extract_int(text)


def extract_area(text: str | None) -> float | None:
    if text is None:
        return None
    # Only extract area when m² unit is present; plain numbers are ambiguous
    text_norm = text.replace(",", ".")
    m = re.search(r"([\d]+(?:\.\d+)?)\s*m[²2]", text_norm, re.IGNORECASE)
    if m:
        return float(m.group(1))
    # Fallback: accept plain number only for short strings (single-value selectors)
    if len(text.strip()) <= 10:
        return _extract_float(text)
    return None
