"""
database.py
SQLAlchemy engine and session factory.

SQLite is used for the prototype. To migrate to PostgreSQL:
  1. Change DATABASE_URL in config.py (or .env) to your PostgreSQL connection string.
  2. Install psycopg2-binary.
  3. No other code changes are needed — SQLAlchemy handles the rest.

connect_args={"check_same_thread": False} is SQLite-specific and can be removed
when switching to PostgreSQL.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from app.config import settings

# SQLite requires check_same_thread=False when used with FastAPI's async handlers
_connect_args = (
    {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}
)

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=_connect_args,
    echo=settings.DEBUG,  # Logs SQL to console in debug mode
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""
    pass


def get_db():
    """
    FastAPI dependency: yields a DB session, closes it after the request.
    Usage in a route:
        def my_route(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_all_tables():
    """Creates all tables defined via Base subclasses. Called once at startup."""
    # Import all models here so Base knows about them before create_all()
    import app.models  # noqa: F401
    Base.metadata.create_all(bind=engine)
