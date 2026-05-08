from __future__ import annotations

import re


def parse_money(text: str | None) -> float | None:
    if text is None:
        return None
    # Extract first continuous numeric token; stops at non-digit/dot/comma chars
    # (handles concatenated prices like "R$ 3.900R$ 4.300" → "3.900")
    m = re.search(r"([\d][\d.,]*)", text)
    if not m:
        return None
    text = m.group(1).rstrip(".,")
    if not text:
        return None

    has_dot = "." in text
    has_comma = "," in text

    if has_dot and has_comma:
        # Formato brasileiro: 3.500,00
        text = text.replace(".", "").replace(",", ".")
    elif has_comma and not has_dot:
        # Brasileiro sem milhar: 3500,00
        text = text.replace(",", ".")
    elif has_dot and not has_comma:
        last_dot = text.rfind(".")
        decimals = text[last_dot + 1:]
        if len(decimals) == 2 and decimals.isdigit():
            pass  # Formato americano: 3500.00
        elif len(decimals) == 3 and decimals.isdigit() and last_dot > 0:
            # Separador de milhar brasileiro: 3.500
            text = text.replace(".", "")

    match = re.search(r"(\d+(?:\.\d+)?)", text)
    if match:
        return float(match.group(1))
    return None
