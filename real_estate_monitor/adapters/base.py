from __future__ import annotations

from abc import ABC, abstractmethod

from real_estate_monitor.schemas.schemas import NormalizedListing


class BaseAdapter(ABC):
    def __init__(self, source_config: dict):
        self.source_config = source_config

    @abstractmethod
    async def fetch_listings(self) -> list[NormalizedListing]:
        pass

    @abstractmethod
    async def fetch_page_html(self) -> str:
        pass
