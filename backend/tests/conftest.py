"""When the suite runs against Postgres (DATABASE_URL=postgresql+psycopg2://...), start from an empty schema so the
run is repeatable; SQLite tests use throwaway temp files and need nothing."""
import os

import pytest


@pytest.fixture(scope="session", autouse=True)
def _fresh_postgres_schema():
    url = os.environ.get("DATABASE_URL", "")
    if url.startswith("postgresql"):
        from sqlalchemy import create_engine, text
        eng = create_engine(url, future=True)
        with eng.begin() as conn:
            conn.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public;"))
        eng.dispose()
    yield
