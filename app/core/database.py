"""Database connection and session management."""
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from sqlalchemy.pool import QueuePool
from .config import get_settings

settings = get_settings()
database_url = settings.DATABASE_URL

if database_url.startswith("postgresql+psycopg2://"):
    try:
        import psycopg2  # noqa: F401
    except ImportError:
        database_url = database_url.replace(
            "postgresql+psycopg2://", "postgresql+psycopg://", 1
        )

_connect_args = {}
if database_url.startswith("postgresql") and "sslmode=" not in database_url:
    _connect_args["sslmode"] = "require"

_connect_args.update({
    "keepalives": 1,
    "keepalives_idle": 30,
    "keepalives_interval": 10,
    "keepalives_count": 5,
    "connect_timeout": 10,
})

engine = create_engine(
    database_url,
    echo=settings.DEBUG,
    connect_args=_connect_args,
    poolclass=QueuePool,
    pool_size=3,
    max_overflow=2,
    pool_timeout=10,
    pool_recycle=300,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

Base = declarative_base()

def get_db() -> Generator[Session, None, None]:
    """Dependency to get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
