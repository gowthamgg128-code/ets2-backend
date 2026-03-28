"""Database connection and session management."""
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session
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

# Add keepalive settings to detect dead connections faster
_connect_args.update({
    "keepalives": 1,
    "keepalives_idle": 30,       # Send keepalive after 30s idle
    "keepalives_interval": 10,   # Retry every 10s
    "keepalives_count": 5,       # Give up after 5 failed keepalives
    "connect_timeout": 10,       # Fail fast instead of hanging
})

engine = create_engine(
    database_url,
    echo=settings.DEBUG,
    connect_args=_connect_args,
    pool_pre_ping=True,      # Test connection before using it
    pool_recycle=300,        # ← Change from 1800 to 300 (5 min)
                             #   Supabase kills idle connections
                             #   around 5-10 min, so recycle before that
    pool_size=3,             # ← Add this: keep only 3 persistent connections
    max_overflow=2,          # ← Add this: allow 2 extra under load = 5 max total
    pool_timeout=30,         # ← Add this: raise error after 30s wait (not hang forever)
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
