from __future__ import annotations

import json
from pathlib import Path

import yaml

from real_estate_monitor.schemas.schemas import SourceConfig


def load_sources(path: str = "configs/sources.yaml") -> list[SourceConfig]:
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    with open(config_path) as f:
        data = yaml.safe_load(f)
    sources = data.get("sources", [])
    return [SourceConfig(**src) for src in sources]


def sync_sources_to_db(sources: list[SourceConfig], session) -> list:
    from real_estate_monitor.models.models import Source

    db_sources = []
    for src in sources:
        existing = None

        # Match by config_id first — stable even when URL/filters change
        if src.id:
            existing = session.query(Source).filter(Source.config_id == src.id).first()

        # Fall back to URL match for backward compatibility with older DB entries
        if not existing:
            existing = session.query(Source).filter(Source.url == src.url).first()

        if existing:
            existing.config_id = src.id
            existing.name = src.name
            existing.url = src.url  # update if filters changed
            existing.adapter = src.adapter
            existing.enabled = src.enabled
            existing.config_json = json.dumps(src.config)
            db_sources.append(existing)
        else:
            db_source = Source(
                config_id=src.id,
                name=src.name,
                url=src.url,
                adapter=src.adapter,
                enabled=src.enabled,
                config_json=json.dumps(src.config),
            )
            session.add(db_source)
            db_sources.append(db_source)

    session.commit()
    for s in db_sources:
        session.refresh(s)
    return db_sources
