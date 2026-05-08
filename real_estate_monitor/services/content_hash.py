from __future__ import annotations

import hashlib
import json

from real_estate_monitor.schemas.schemas import NormalizedListing


def compute_content_hash(listing: NormalizedListing) -> str:
    data = json.dumps(listing.model_dump(), sort_keys=True, default=str)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()
