from __future__ import annotations

import hashlib
import json

from real_estate_monitor.schemas.schemas import NormalizedListing


def compute_fingerprint(listing: NormalizedListing) -> str:
    data = json.dumps(
        {
            "title": listing.title,
            "address": listing.address,
            "bedrooms": listing.bedrooms,
            "bathrooms": listing.bathrooms,
            "parking": listing.parking,
            "area": listing.area,
        },
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(data.encode("utf-8")).hexdigest()
