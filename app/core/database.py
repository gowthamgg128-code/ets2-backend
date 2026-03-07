"""Database connection and session management."""
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from .config import get_settings

# Create SQLAlchemy engine
settings = get_settings()
database_url = settings.DATABASE_URL
if database_url.startswith("postgresql+psycopg2://"):
    try:
        import psycopg2  # noqa: F401
    except ImportError:
        database_url = database_url.replace("postgresql+psycopg2://", "postgresql+psycopg://", 1)

_connect_args = {}
if database_url.startswith("postgresql") and "sslmode=" not in database_url:
    _connect_args["sslmode"] = "require"

engine = create_engine(
    database_url,
    echo=settings.DEBUG,
    connect_args=_connect_args,
    pool_pre_ping=True,  # Test connections before using
    pool_recycle=1800,  # Recycle connections after 30 minutes
)

# Create session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

# Declarative base for models
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """Dependency to get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

