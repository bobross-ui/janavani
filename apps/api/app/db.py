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
        for sql in [
            # 1.4
            "ALTER TABLE issue_clusters ADD COLUMN coordinate_count INTEGER NOT NULL DEFAULT 0",
            # 1.3
            "ALTER TABLE grievances ADD COLUMN embedding_json TEXT",
            "ALTER TABLE issue_clusters ADD COLUMN centroid_embedding_json TEXT",
            "ALTER TABLE issue_clusters ADD COLUMN embedding_count INTEGER NOT NULL DEFAULT 0",
            # area-based location
            "ALTER TABLE grievances ADD COLUMN area TEXT NOT NULL DEFAULT ''",
            "ALTER TABLE grievances ADD COLUMN area_source TEXT NOT NULL DEFAULT ''",
            "ALTER TABLE issue_clusters ADD COLUMN area TEXT NOT NULL DEFAULT ''",
            "ALTER TABLE issue_clusters ADD COLUMN area_source TEXT NOT NULL DEFAULT ''",
            # reverse geocoding
            "ALTER TABLE grievances ADD COLUMN suburb TEXT NOT NULL DEFAULT ''",
            "ALTER TABLE grievances ADD COLUMN road TEXT NOT NULL DEFAULT ''",
            "ALTER TABLE grievances ADD COLUMN sector TEXT NOT NULL DEFAULT ''",
            "ALTER TABLE grievances ADD COLUMN location_json TEXT",
            "ALTER TABLE issue_clusters ADD COLUMN suburb TEXT NOT NULL DEFAULT ''",
            "ALTER TABLE issue_clusters ADD COLUMN road TEXT NOT NULL DEFAULT ''",
            "ALTER TABLE issue_clusters ADD COLUMN sector TEXT NOT NULL DEFAULT ''",
            "ALTER TABLE issue_clusters ADD COLUMN location_json TEXT",
        ]:
            try:
                conn.exec_driver_sql(sql)
                conn.commit()
            except Exception:
                conn.rollback()
                pass  # column already exists

        # ── Unique constraint: one support per user per cluster ──
        try:
            conn.exec_driver_sql(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_cluster_support_user "
                "ON cluster_supports (cluster_id, user_id)"
            )
            conn.commit()
        except Exception:
            conn.rollback()
            pass  # constraint already exists
    # ── end migration