from __future__ import annotations

import json

from real_estate_monitor.adapters.base import BaseAdapter
from real_estate_monitor.adapters.apolar_adapter import ApolarAdapter
from real_estate_monitor.adapters.json_api_adapter import JsonApiAdapter
from real_estate_monitor.adapters.playwright_bs_adapter import PlaywrightBSAdapter
from real_estate_monitor.configs.config_loader import load_sources, sync_sources_to_db
from real_estate_monitor.database import get_session
from real_estate_monitor.models.models import Listing, Source
from real_estate_monitor.services.diff_service import DiffService
from real_estate_monitor.services.duplicate_service import DuplicateDetectionService
from real_estate_monitor.services.notifier import ConsoleNotifier
from real_estate_monitor.services.snapshot_service import SnapshotService

_DEFAULT_HEALTH_THRESHOLD = 0.6
_HEALTH_MIN_LISTINGS = 5


class RunnerService:
    def __init__(
        self, db_url: str | None = None, config_path: str = "configs/sources.yaml"
    ):
        self.db_url = db_url
        self.config_path = config_path
        self.notifier = ConsoleNotifier()
        self.snapshot_service = SnapshotService()

    def _create_adapter(self, source: Source) -> BaseAdapter:
        config = json.loads(source.config_json) if source.config_json else {}
        source_config = {
            "url": source.url,
            "config": config,
        }
        if source.adapter == "playwright_bs":
            return PlaywrightBSAdapter(source_config)
        if source.adapter == "json_api":
            return JsonApiAdapter(source_config)
        if source.adapter == "apolar":
            return ApolarAdapter(source_config)
        raise ValueError(f"Unknown adapter type: {source.adapter}")

    async def run_source(self, source_id: int) -> None:
        config_raw: dict = {}

        diff = DiffService(source_id, self.db_url)
        source = diff.session.get(Source, source_id)
        if not source:
            print(f"Source {source_id} not found.")
            diff.close()
            return
        if not source.enabled:
            print(f"Source {source_id} is disabled.")
            diff.close()
            return

        if source.config_json:
            config_raw = json.loads(source.config_json)

        grace_period = config_raw.get("removal_grace_period", 2)
        health_threshold = config_raw.get("scrape_health_threshold", _DEFAULT_HEALTH_THRESHOLD)
        diff.grace_period = grace_period

        adapter = self._create_adapter(source)
        listings = await adapter.fetch_listings()

        # Health guard: abort diff if scrape returned suspiciously few listings
        active_count = (
            diff.session.query(Listing)
            .filter(Listing.source_id == source_id, Listing.is_active == True)
            .count()
        )
        if active_count >= _HEALTH_MIN_LISTINGS and len(listings) < health_threshold * active_count:
            print(
                f"[AVISO] {source.name}: scraping retornou {len(listings)} imóveis "
                f"(esperado ≥ {int(health_threshold * active_count)}). "
                f"Diff abortado para evitar remoções falsas."
            )
            diff.close()
            return

        events = diff.process_listings(listings)

        html = await adapter.fetch_page_html()
        snapshot_path = self.snapshot_service.save(source_id, html)
        for event in events:
            event.snapshot_path = snapshot_path
        diff.session.commit()

        self.notifier.notify(events)
        diff.close()

        dup_svc = DuplicateDetectionService(self.db_url)
        new_dupes = dup_svc.detect_for_source(source_id)
        if new_dupes > 0:
            print(f"  {new_dupes} novo(s) par(es) de duplicata(s) encontrado(s).")
        dup_svc.close()

    async def run_all(self) -> None:
        session = get_session(self.db_url)
        sources = sync_sources_to_db(load_sources(self.config_path), session)
        session.close()

        for source in sources:
            if source.enabled:
                print(f"\nRunning source: {source.name} ({source.id})")
                try:
                    await self.run_source(source.id)
                except Exception as exc:
                    print(f"[ERRO] {source.name}: {exc}")

    async def dry_run_source(self, source_id: int) -> None:
        session = get_session(self.db_url)
        source = session.get(Source, source_id)
        if not source:
            print(f"Source {source_id} not found.")
            session.close()
            return

        adapter = self._create_adapter(source)
        listings = await adapter.fetch_listings()
        session.close()

        print(f"\nDry run for source: {source.name}")
        print(f"Found {len(listings)} listing(s):")
        for listing in listings:
            print(
                f"  - {listing.title or listing.external_id} | Price: {listing.price}"
            )
