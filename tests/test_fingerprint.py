from real_estate_monitor.schemas.schemas import NormalizedListing
from real_estate_monitor.services.content_hash import compute_content_hash
from real_estate_monitor.services.fingerprint import compute_fingerprint


class TestFingerprint:
    def test_deterministic(self):
        listing = NormalizedListing(
            external_id="abc123",
            title="Nice House",
            address="123 Main St",
            bedrooms=3,
            bathrooms=2,
            parking=1,
            area=120.0,
        )
        fp1 = compute_fingerprint(listing)
        fp2 = compute_fingerprint(listing)
        assert fp1 == fp2

    def test_different_listings_different_fingerprints(self):
        l1 = NormalizedListing(external_id="1", title="A", bedrooms=2)
        l2 = NormalizedListing(external_id="1", title="B", bedrooms=2)
        assert compute_fingerprint(l1) != compute_fingerprint(l2)

    def test_same_data_same_fingerprint(self):
        l1 = NormalizedListing(external_id="1", title="A", bedrooms=2)
        l2 = NormalizedListing(external_id="1", title="A", bedrooms=2)
        assert compute_fingerprint(l1) == compute_fingerprint(l2)

    def test_price_does_not_affect_fingerprint(self):
        l1 = NormalizedListing(external_id="1", title="A", price=1000.0)
        l2 = NormalizedListing(external_id="1", title="A", price=2000.0)
        assert compute_fingerprint(l1) == compute_fingerprint(l2)


class TestContentHash:
    def test_deterministic(self):
        listing = NormalizedListing(
            external_id="abc123",
            title="Nice House",
            price=1500.0,
            bedrooms=3,
        )
        h1 = compute_content_hash(listing)
        h2 = compute_content_hash(listing)
        assert h1 == h2

    def test_different_listings_different_hashes(self):
        l1 = NormalizedListing(external_id="1", price=1000.0)
        l2 = NormalizedListing(external_id="1", price=2000.0)
        assert compute_content_hash(l1) != compute_content_hash(l2)

    def test_hash_length(self):
        listing = NormalizedListing(external_id="1")
        h = compute_content_hash(listing)
        assert len(h) == 64
