"""Database setup. Postgres in production (DATABASE_URL), SQLite fallback for local dev/tests.

Schema management:
* SQLite (dev/tests): `create_all` — simplest thing that works.
* Postgres: Alembic (`backend/alembic/`). `init_db()` runs `alembic upgrade head` at startup, so `docker compose up`
  on a fresh database just works. A v0.1 database that was created by `create_all` (no alembic_version table yet)
  is adopted once: missing tables/columns are added and the database is stamped at head.
"""
import logging
import os
from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./it_tracker.db")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args, future=True, pool_pre_ping=not DATABASE_URL.startswith("sqlite"))
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
log = logging.getLogger("ittracker.db")
BACKEND_DIR = Path(__file__).resolve().parent.parent


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# columns added after v0.1 (only needed when adopting a create_all-made Postgres database)
_V2_COLUMNS = {
    "companies": ["short_name VARCHAR(60)", "owner_phone VARCHAR(30)", "owner_email VARCHAR(200)", "accountant_email VARCHAR(200)",
                  "whatsapp_enabled BOOLEAN DEFAULT FALSE", "email_enabled BOOLEAN DEFAULT FALSE", "reminder_days_before JSON",
                  "weekly_digest_day VARCHAR(3)"],
    "streams": ["extra JSON"],
}


def _alembic_config():
    from alembic.config import Config
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    cfg.set_main_option("sqlalchemy.url", DATABASE_URL.replace("%", "%%"))
    return cfg


def init_db():
    from app import models  # noqa: F401  (register tables)
    if engine.dialect.name != "postgresql":
        Base.metadata.create_all(bind=engine)
        return
    from alembic import command
    insp = inspect(engine)
    tables = set(insp.get_table_names())
    cfg = _alembic_config()
    if "companies" in tables and "alembic_version" not in tables:
        log.info("adopting a pre-Alembic database: adding new tables/columns and stamping head")
        Base.metadata.create_all(bind=engine)   # new tables only
        with engine.begin() as conn:
            for table, cols in _V2_COLUMNS.items():
                for col in cols:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col}"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_streams_status ON streams (status)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_questions_answered ON questions (answered)"))
        command.stamp(cfg, "head")
        return
    command.upgrade(cfg, "head")
