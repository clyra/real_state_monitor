from __future__ import annotations

from datetime import datetime, UTC
from pathlib import Path


class SnapshotService:
    def __init__(self, base_dir: str = "snapshots"):
        self.base_dir = Path(base_dir)

    def save(self, source_id: int, html: str) -> str:
        source_dir = self.base_dir / str(source_id)
        source_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}.html"
        filepath = source_dir / filename
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(html)
        return str(filepath)
