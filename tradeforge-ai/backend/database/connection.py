"""
TradeForge AI - Database Engine & Session Management.

Provides SQLAlchemy engine configuration, session factories, and
database initialization utilities with automatic transaction handling.
"""

from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from config import settings
from database.models import Base

# ---------------------------------------------------------------------------
# Engine & Session Factory
# ---------------------------------------------------------------------------

# SQLite requires `check_same_thread=False` for multi-threaded usage
# (e.g., when using async workers or background training jobs).
_connect_args: dict = (
    {"check_same_thread": False}
    if "sqlite" in settings.DATABASE_URL
    else {}
)

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=_connect_args,
    echo=settings.DEBUG,
    pool_pre_ping=True,
    future=True,
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    future=True,
)

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def init_db() -> None:
    """Create all tables defined in :class:`database.models.Base`.

    Safe to call multiple times — existing tables are left untouched.
    Invoke this once at application startup (e.g., in lifespan handler).
    """
    Base.metadata.create_all(bind=engine)


@contextmanager
def get_db() -> Generator[Session, None, None]:
    """Database session context manager with automatic commit / rollback.

    Usage::

        with get_db() as db:
            db.add(some_strategy)
            # commit is automatic on clean exit

    Raises:
        Exception: Re-raised after rolling back the current transaction.
    """
    db: Session = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_db_session() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a database session per request.

    Usage::

        @app.get("/strategies")
        def list_strategies(db: Session = Depends(get_db_session)):
            ...

    The session is automatically closed when the request finishes.
    """
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
