from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from real_estate_monitor.models.models import Base

DEFAULT_DB_URL = "sqlite:///real_estate_monitor.db"

_engines: dict[str, Engine] = {}


def get_db_url() -> str:
    return os.environ.get("DATABASE_URL", DEFAULT_DB_URL)


def _get_engine(url: str | None = None) -> Engine:
    db_url = url or get_db_url()
    if db_url not in _engines:
        _engines[db_url] = create_engine(db_url, echo=False)
    return _engines[db_url]


def init_db(url: str | None = None) -> None:
    Base.metadata.create_all(_get_engine(url))


def get_session(url: str | None = None) -> Session:
    factory = sessionmaker(bind=_get_engine(url), expire_on_commit=False)
    return factory()
