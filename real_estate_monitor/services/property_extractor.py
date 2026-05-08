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


def extract_bedrooms(text: str | None) -> int | None:
    return _extract_int(text)


def extract_bathrooms(text: str | None) -> int | None:
    return _extract_int(text)


def extract_parking(text: str | None) -> int | None:
    return _extract_int(text)


def extract_area(text: str | None) -> float | None:
    return _extract_float(text)
