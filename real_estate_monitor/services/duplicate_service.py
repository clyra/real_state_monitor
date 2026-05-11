from __future__ import annotations

import re

from real_estate_monitor.database import get_session
from real_estate_monitor.models.models import Listing, ListingDuplicate
from real_estate_monitor.services.text_utils import extract_neighborhood

SCORE_THRESHOLD = 80

# Patterns to extract property codes from URLs when not stored explicitly.
# Handles: ?ref=07804.001-CIL, /imovel/CA0309-TAN, etc.
_URL_CODE_PATTERNS = [
    re.compile(r"[?&]ref=([A-Z0-9]{3,}(?:[.\-][A-Z0-9]{2,})+)", re.IGNORECASE),
    re.compile(r"/imovel/([A-Z0-9]{3,}(?:[.\-][A-Z0-9]{2,})+)", re.IGNORECASE),
]

# Known code suffixes → agency name. Extend as new suffixes are discovered.
_SUFFIX_TO_AGENCY: dict[str, str] = {
    "TAN":  "Tantus Imóveis",
    "JLAB": "JLA Imóveis",
}


def infer_agency_from_code(code: str | None) -> str | None:
    """Return the agency name inferred from the code suffix (e.g. CA0309-TAN → Tantus)."""
    if not code:
        return None
    suffix = code.rsplit("-", 1)[-1].upper()
    return _SUFFIX_TO_AGENCY.get(suffix)


def _get_property_code(listing: "Listing") -> str | None:  # type: ignore[name-defined]
    """Return the listing's stored code, or try to extract one from its URL."""
    if listing.property_code:
        return listing.property_code.upper()
    for pattern in _URL_CODE_PATTERNS:
        m = pattern.search(listing.url or "")
        if m:
            return m.group(1).upper()
    return None


def _normalize_neighborhood(address: str | None) -> str | None:
    if not address:
        return None
    nb = extract_neighborhood(address)
    return nb.lower().strip() if nb else None


def _compute_score(a: Listing, b: Listing) -> tuple[int, str]:
    """Return (score, method). Score 0 means no match."""
    # Layer 1: property code — definitive match
    code_a = _get_property_code(a)
    code_b = _get_property_code(b)
    if code_a and code_b and code_a == code_b:
        return 100, "property_code"

    # Layer 2: score-based. Requires exact price match to proceed.
    if not (a.price and b.price and a.price == b.price):
        return 0, ""

    score = 40  # exact price match

    nb_a = _normalize_neighborhood(a.address)
    nb_b = _normalize_neighborhood(b.address)
    if nb_a and nb_b and nb_a == nb_b:
        score += 30

    if a.area and b.area and abs(a.area - b.area) <= 5:
        score += 20

    if a.bedrooms and b.bedrooms and a.bedrooms == b.bedrooms:
        score += 5
    if a.bathrooms and b.bathrooms and a.bathrooms == b.bathrooms:
        score += 5

    return (score, "score") if score >= SCORE_THRESHOLD else (0, "")


class DuplicateDetectionService:
    def __init__(self, db_url: str | None = None):
        self.session = get_session(db_url)

    def detect_for_source(self, source_id: int) -> int:
        """Compare this source's active listings against all other sources.
        Returns count of new pairs found."""
        source_listings = (
            self.session.query(Listing)
            .filter(Listing.source_id == source_id, Listing.is_active == True)
            .all()
        )
        other_listings = (
            self.session.query(Listing)
            .filter(Listing.source_id != source_id, Listing.is_active == True)
            .all()
        )

        count = 0
        for a in source_listings:
            for b in other_listings:
                score, method = _compute_score(a, b)
                if score > 0 and self._upsert(a, b, score, method):
                    count += 1

        self._cleanup_inactive()
        self.session.commit()
        return count

    def detect_all(self) -> int:
        """Full cross-source re-detection. Returns count of new pairs."""
        listings = (
            self.session.query(Listing)
            .filter(Listing.is_active == True)
            .all()
        )

        count = 0
        for i, a in enumerate(listings):
            for b in listings[i + 1:]:
                if a.source_id == b.source_id:
                    continue
                score, method = _compute_score(a, b)
                if score > 0 and self._upsert(a, b, score, method):
                    count += 1

        self._cleanup_inactive()
        self.session.commit()
        return count

    def _upsert(self, a: Listing, b: Listing, score: int, method: str) -> bool:
        """Insert or update a duplicate pair. Returns True if newly inserted."""
        id_a, id_b = (a.id, b.id) if a.id < b.id else (b.id, a.id)
        existing = (
            self.session.query(ListingDuplicate)
            .filter_by(listing_id_a=id_a, listing_id_b=id_b)
            .first()
        )
        if existing:
            if existing.confirmed is None:
                existing.score = score
                existing.method = method
            return False

        self.session.add(ListingDuplicate(
            listing_id_a=id_a,
            listing_id_b=id_b,
            score=score,
            method=method,
            confirmed=None,
        ))
        return True

    def _cleanup_inactive(self) -> None:
        """Remove unreviewed pairs where a listing became inactive."""
        inactive_ids = {
            l.id
            for l in self.session.query(Listing.id).filter(Listing.is_active == False)
        }
        if not inactive_ids:
            return
        for dup in self.session.query(ListingDuplicate).filter_by(confirmed=None).all():
            if dup.listing_id_a in inactive_ids or dup.listing_id_b in inactive_ids:
                self.session.delete(dup)

    def close(self) -> None:
        self.session.close()
