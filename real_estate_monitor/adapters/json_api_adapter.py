from __future__ import annotations

import json
import re
import unicodedata
import urllib.request

from real_estate_monitor.adapters.base import BaseAdapter
from real_estate_monitor.schemas.schemas import NormalizedListing
from real_estate_monitor.services.text_utils import normalize_text


def _slugify(text: str) -> str:
    """Convert text to URL-friendly slug (handles Portuguese accents)."""
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    text = re.sub(r"\s+", "-", text.strip())
    return text


def _get_nested(item: dict, path: str):
    """Access nested fields using dot notation, e.g. 'images.0.url'."""
    parts = path.split(".")
    val = item
    for part in parts:
        if isinstance(val, list):
            try:
                val = val[int(part)]
            except (ValueError, IndexError):
                return None
        elif isinstance(val, dict):
            val = val.get(part)
        else:
            return None
    return val


def _build_url(template: str, item: dict) -> str:
    """Fill URL template with item fields. Supports {key} and {key_slug} placeholders."""
    result = template
    for key, val in item.items():
        slug_ph = f"{{{key}_slug}}"
        plain_ph = f"{{{key}}}"
        if slug_ph in result:
            result = result.replace(slug_ph, _slugify(str(val)))
        if plain_ph in result:
            result = result.replace(plain_ph, str(val))
    return result


class JsonApiAdapter(BaseAdapter):
    """Adapter for sources that expose listings via a JSON REST API."""

    def __init__(self, source_config: dict):
        super().__init__(source_config)
        self.config = source_config.get("config", {})
        self.fields = self.config.get("fields", {})
        self.data_key = self.config.get("data_key", "data")
        self.url = source_config["url"]
        self.listing_url_template = self.config.get("listing_url_template", "")
        self._raw_json: str = ""

    def _fetch_raw(self) -> dict | list:
        req = urllib.request.Request(
            self.url,
            headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read())
        self._raw_json = json.dumps(data, ensure_ascii=False)
        return data

    def _parse_item(self, item: dict) -> NormalizedListing | None:
        def get(fname: str):
            key = self.fields.get(fname, "")
            if not key:
                return None
            return _get_nested(item, key) if "." in key else item.get(key)

        external_id = get("external_id")
        if not external_id:
            return None
        external_id = str(external_id)

        price_raw = get("price")
        price = float(price_raw) if price_raw is not None else None

        area_raw = get("area")
        area = float(area_raw) if area_raw is not None else None

        address = get("address") or ""
        neighborhood = get("neighborhood") or ""
        if neighborhood and neighborhood.lower() not in address.lower():
            full_address = f"{address}, {neighborhood}"
        else:
            full_address = address

        beds = get("bedrooms")
        baths = get("bathrooms")
        parking = get("parking")

        prop_code = get("property_code")

        url = _build_url(self.listing_url_template, item) if self.listing_url_template else None

        return NormalizedListing(
            external_id=external_id,
            title=normalize_text(get("title") or ""),
            price=price,
            address=normalize_text(full_address) or None,
            url=url,
            bedrooms=int(beds) if beds is not None else None,
            bathrooms=int(baths) if baths is not None else None,
            parking=int(parking) if parking is not None else None,
            area=area,
            image_url=get("image_url") or None,
            property_code=prop_code.upper() if prop_code else None,
        )

    async def fetch_listings(self) -> list[NormalizedListing]:
        raw = self._fetch_raw()
        items = raw.get(self.data_key, raw) if isinstance(raw, dict) else raw
        if not isinstance(items, list):
            return []
        results = []
        for item in items:
            listing = self._parse_item(item)
            if listing:
                results.append(listing)
        return results

    async def fetch_page_html(self) -> str:
        return self._raw_json
