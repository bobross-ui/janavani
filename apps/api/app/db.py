from sqlmodel import Session, SQLModel, create_engine

from app.config import get_settings

_engine = None


def get_engine():
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_engine(settings.database_url, echo=False)
    return _engine


def get_session():
    with Session(get_engine()) as session:
        yield session


def create_db_and_tables():
    engine = get_engine()
    # pgvector extension (safe to run; no-op if already present)
    with engine.connect() as conn:
        try:
            conn.exec_driver_sql("CREATE EXTENSION IF NOT EXISTS vector")
            conn.commit()
        except Exception:
            pass  # SQLite or extension already loaded
    SQLModel.metadata.create_all(engine)
    # ── Schema migration: coordinate_count (1.4) ──────────────────
    # SQLModel.create_all() does not alter existing tables.  This
    # migration adds the column when upgrading from a previous schema.
    with engine.connect() as conn:
        try:
            conn.exec_driver_sql(
                "ALTER TABLE issue_clusters "
                "ADD COLUMN coordinate_count INTEGER NOT NULL DEFAULT 0"
            )
            conn.commit()
        except Exception:
            pass  # column already exists (fresh DB or already migrated)
