from __future__ import annotations

from abc import ABC, abstractmethod

from real_estate_monitor.models.models import ListingEvent


class BaseNotifier(ABC):
    @abstractmethod
    def notify(self, events: list[ListingEvent]) -> None:
        pass


class ConsoleNotifier(BaseNotifier):
    def notify(self, events: list[ListingEvent]) -> None:
        if not events:
            print("No changes detected.")
            return

        print(f"\n{'=' * 60}")
        print(f"Detected {len(events)} event(s):")
        print(f"{'=' * 60}")

        for event in events:
            print(f"\n  Type: {event.event_type}")
            if event.listing:
                print(f"  Listing: {event.listing.title or event.listing.external_id}")
            if event.old_price is not None or event.new_price is not None:
                print(f"  Old Price: {event.old_price}")
                print(f"  New Price: {event.new_price}")
            if event.snapshot_path:
                print(f"  Snapshot: {event.snapshot_path}")
            print(f"  Time: {event.created_at}")

        print(f"\n{'=' * 60}")
