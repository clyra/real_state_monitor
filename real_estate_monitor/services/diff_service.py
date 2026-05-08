from __future__ import annotations

from datetime import UTC, datetime

from real_estate_monitor.database import get_session
from real_estate_monitor.enums import ListingEventType
from real_estate_monitor.models.models import Listing, ListingEvent, Source
from real_estate_monitor.schemas.schemas import NormalizedListing
from real_estate_monitor.services.content_hash import compute_content_hash
from real_estate_monitor.services.fingerprint import compute_fingerprint


class DiffService:
    def __init__(
        self,
        source_id: int,
        db_url: str | None = None,
        grace_period: int = 2,
    ):
        self.source_id = source_id
        self.db_url = db_url
        self.grace_period = grace_period
        self.session = get_session(db_url)

    def process_listings(
        self, new_listings: list[NormalizedListing]
    ) -> list[ListingEvent]:
        source = self.session.get(Source, self.source_id)
        if not source:
            raise ValueError(f"Source {self.source_id} not found")

        external_ids = {l.external_id for l in new_listings}
        existing = (
            self.session.query(Listing)
            .filter(Listing.source_id == self.source_id)
            .all()
        )
        existing_by_id = {l.external_id: l for l in existing}

        events: list[ListingEvent] = []

        for listing in new_listings:
            fingerprint = compute_fingerprint(listing)
            content_hash = compute_content_hash(listing)

            if listing.external_id not in existing_by_id:
                db_listing = Listing(
                    source_id=self.source_id,
                    external_id=listing.external_id,
                    fingerprint=fingerprint,
                    content_hash=content_hash,
                    title=listing.title,
                    price=listing.price,
                    currency=listing.currency,
                    address=listing.address,
                    url=listing.url,
                    bedrooms=listing.bedrooms,
                    bathrooms=listing.bathrooms,
                    parking=listing.parking,
                    area=listing.area,
                    description=listing.description,
                    image_url=listing.image_url,
                    is_active=True,
                    missing_runs_count=0,
                )
                self.session.add(db_listing)
                self.session.flush()

                event = ListingEvent(
                    source_id=self.source_id,
                    listing_id=db_listing.id,
                    event_type=ListingEventType.NEW.value,
                    new_price=listing.price,
                    created_at=datetime.now(UTC),
                )
                events.append(event)
            else:
                db_listing = existing_by_id[listing.external_id]
                old_price = db_listing.price

                # Reset miss counter — listing is present this run
                db_listing.missing_runs_count = 0

                if not db_listing.is_active:
                    db_listing.is_active = True
                    event = ListingEvent(
                        source_id=self.source_id,
                        listing_id=db_listing.id,
                        event_type=ListingEventType.REACTIVATED.value,
                        new_price=listing.price,
                        created_at=datetime.now(UTC),
                    )
                    events.append(event)

                if db_listing.fingerprint != fingerprint:
                    if old_price != listing.price:
                        event = ListingEvent(
                            source_id=self.source_id,
                            listing_id=db_listing.id,
                            event_type=ListingEventType.PRICE_CHANGED.value,
                            old_price=old_price,
                            new_price=listing.price,
                            created_at=datetime.now(UTC),
                        )
                    else:
                        event = ListingEvent(
                            source_id=self.source_id,
                            listing_id=db_listing.id,
                            event_type=ListingEventType.UPDATED.value,
                            created_at=datetime.now(UTC),
                        )
                    events.append(event)

                    db_listing.fingerprint = fingerprint
                    db_listing.content_hash = content_hash
                    db_listing.title = listing.title
                    db_listing.price = listing.price
                    db_listing.address = listing.address
                    db_listing.bedrooms = listing.bedrooms
                    db_listing.bathrooms = listing.bathrooms
                    db_listing.parking = listing.parking
                    db_listing.area = listing.area
                    db_listing.description = listing.description
                    db_listing.image_url = listing.image_url

        # Grace period: only mark REMOVED after missing from N consecutive runs
        for db_listing in existing:
            if db_listing.external_id not in external_ids and db_listing.is_active:
                db_listing.missing_runs_count = (db_listing.missing_runs_count or 0) + 1
                if db_listing.missing_runs_count >= self.grace_period:
                    db_listing.is_active = False
                    db_listing.missing_runs_count = 0
                    event = ListingEvent(
                        source_id=self.source_id,
                        listing_id=db_listing.id,
                        event_type=ListingEventType.REMOVED.value,
                        old_price=db_listing.price,
                        created_at=datetime.now(UTC),
                    )
                    events.append(event)

        for event in events:
            self.session.add(event)

        self.session.commit()
        return events

    def close(self):
        self.session.close()
