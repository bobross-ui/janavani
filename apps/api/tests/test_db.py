from sqlalchemy import text
from sqlmodel import Session, SQLModel, create_engine

# Import all models so they register with SQLModel.metadata
from app.models import (  # noqa: F401
    ClusterSupport,
    ComplaintDraft,
    EvalRun,
    Grievance,
    IssueCluster,
    User,
)


def test_can_create_in_memory_tables():
    """Verify in-memory SQLite tables can be created from all models."""
    engine = create_engine("sqlite://", echo=False)
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        result = session.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        )
        tables = [row[0] for row in result.fetchall()]

    expected = {
        "users",
        "grievances",
        "issue_clusters",
        "cluster_supports",
        "complaint_drafts",
        "eval_runs",
    }
    found = {t for t in tables if t in expected}
    assert found == expected, f"Missing tables: {expected - found}"
