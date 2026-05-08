import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from real_estate_monitor.database import init_db
from real_estate_monitor.enums import ListingEventType
from real_estate_monitor.models.models import Base, Listing, ListingEvent, Source
from real_estate_monitor.schemas.schemas import NormalizedListing
from real_estate_monitor.services.diff_service import DiffService


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def source(db_session):
    src = Source(
        name="Test Source",
        url="https://test.com",
        adapter="playwright_bs",
        enabled=True,
        config_json="{}",
    )
    db_session.add(src)
    db_session.commit()
    db_session.refresh(src)
    return src


def _make_diff(source_id, db_session):
    engine = db_session.get_bind()
    return DiffService.__new__(DiffService)


class TestDiffServiceNew:
    def test_new_listing_creates_event(self, db_session, source):
        listings = [
            NormalizedListing(
                external_id="ext1",
                title="New House",
                price=1500.0,
                bedrooms=3,
            )
        ]
        diff = DiffService(source.id, "sqlite:///:memory:")
        diff.session = db_session
        events = diff.process_listings(listings)
        assert len(events) == 1
        assert events[0].event_type == ListingEventType.NEW.value
        assert events[0].new_price == 1500.0


class TestDiffServiceRemoved:
    def test_removed_listing_creates_event(self, db_session, source):
        existing = Listing(
            source_id=source.id,
            external_id="ext1",
            fingerprint="abc",
            content_hash="def",
            title="Old House",
            price=1200.0,
            is_active=True,
            missing_runs_count=0,
        )
        db_session.add(existing)
        db_session.commit()

        diff = DiffService.__new__(DiffService)
        diff.source_id = source.id
        diff.db_url = None
        diff.session = db_session
        diff.grace_period = 1  # remove after first miss
        events = diff.process_listings([])
        assert len(events) == 1
        assert events[0].event_type == ListingEventType.REMOVED.value

    def test_grace_period_delays_removal(self, db_session, source):
        existing = Listing(
            source_id=source.id,
            external_id="ext1",
            fingerprint="abc",
            content_hash="def",
            title="Old House",
            price=1200.0,
            is_active=True,
            missing_runs_count=0,
        )
        db_session.add(existing)
        db_session.commit()

        diff = DiffService.__new__(DiffService)
        diff.source_id = source.id
        diff.db_url = None
        diff.session = db_session
        diff.grace_period = 2

        # First miss: not yet removed
        events = diff.process_listings([])
        assert len(events) == 0
        assert existing.missing_runs_count == 1
        assert existing.is_active is True

        # Second miss: now removed
        events = diff.process_listings([])
        assert len(events) == 1
        assert events[0].event_type == ListingEventType.REMOVED.value
        assert existing.is_active is False


class TestDiffServicePriceChanged:
    def test_price_change_detected(self, db_session, source):
        existing = Listing(
            source_id=source.id,
            external_id="ext1",
            fingerprint="old_fp",
            content_hash="old_hash",
            title="House",
            price=1200.0,
            is_active=True,
            missing_runs_count=0,
        )
        db_session.add(existing)
        db_session.commit()

        listings = [
            NormalizedListing(
                external_id="ext1",
                title="House",
                price=1500.0,
                bedrooms=3,
            )
        ]
        diff = DiffService.__new__(DiffService)
        diff.source_id = source.id
        diff.db_url = None
        diff.session = db_session
        diff.grace_period = 2
        events = diff.process_listings(listings)
        assert len(events) == 1
        assert events[0].event_type == ListingEventType.PRICE_CHANGED.value
        assert events[0].old_price == 1200.0
        assert events[0].new_price == 1500.0


class TestDiffServiceReactivated:
    def test_reactivated_listing(self, db_session, source):
        existing = Listing(
            source_id=source.id,
            external_id="ext1",
            fingerprint="fp",
            content_hash="hash",
            title="House",
            price=1200.0,
            is_active=False,
            missing_runs_count=0,
        )
        db_session.add(existing)
        db_session.commit()

        listings = [
            NormalizedListing(
                external_id="ext1",
                title="House",
                price=1200.0,
                bedrooms=3,
            )
        ]
        diff = DiffService.__new__(DiffService)
        diff.source_id = source.id
        diff.db_url = None
        diff.session = db_session
        diff.grace_period = 2
        events = diff.process_listings(listings)
        assert any(e.event_type == ListingEventType.REACTIVATED.value for e in events)
