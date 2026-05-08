from __future__ import annotations

import re
import unicodedata


def normalize_text(text: str | None) -> str:
    if text is None:
        return ""
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def extract_neighborhood(address: str | None) -> str:
    if not address:
        return ""
    address = normalize_text(address)

    patterns = [
        (r"[\d.]+-\d{3}\s+([A-Za-z ]+?)\s+Curitiba", 1),
        (r"([A-Za-z ]+?)\s+-\s+Curitiba", 1),
        (r"([A-Za-z ]+?)\s*/\s*Curitiba", 1),
        (r"^([A-Za-z ]+?)$", 1),
    ]
    for pattern, group in patterns:
        match = re.search(pattern, address, re.IGNORECASE)
        if match:
            return match.group(group).strip()
    return address.strip()
