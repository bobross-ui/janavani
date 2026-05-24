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
    SQLModel.metadata.create_all(engine)
