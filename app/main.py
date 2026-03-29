"""FastAPI application entry point."""
import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi import _rate_limit_exceeded_handler

from app.api import activation, admin, mods, requests, authorized_users
from app.core.config import get_settings
from app.core.database import Base, engine
from app.core.rate_limit import limiter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

settings = get_settings()
app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description="ETS2 Paid Mod Distribution Backend",
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions globally."""
    if isinstance(exc, HTTPException):
        raise exc

    if isinstance(exc, OperationalError):
        logger.exception("Database operation failed")
        return JSONResponse(
            status_code=503,
            content={"detail": "Database temporarily unavailable"},
        )

    logger.exception("Unhandled exception")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


@app.on_event("startup")
def create_tables():
    """Create database tables on startup."""
    Base.metadata.create_all(bind=engine)
    migrate_mods_table()
    logger.info("Database tables created successfully")


def migrate_mods_table() -> None:
    """Apply lightweight schema migration for GitHub storage metadata."""
    statements = [
        "ALTER TABLE mods ADD COLUMN IF NOT EXISTS file_url VARCHAR(1000)",
        "ALTER TABLE mods ADD COLUMN IF NOT EXISTS size BIGINT",
        "ALTER TABLE mods ADD COLUMN IF NOT EXISTS checksum VARCHAR(64)",
    ]
    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))


app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.ADMIN_PANEL_ORIGIN],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-License-Key", "X-PC-ID"],
)

app.include_router(admin.router)
app.include_router(mods.router)
app.include_router(requests.router)
app.include_router(activation.router)
app.include_router(authorized_users.router)


@app.get("/")
def root():
    """Root endpoint."""
    return {
        "message": "ETS2 Backend API",
        "version": "1.0.0",
        "docs": "/docs",
    }


@app.api_route("/health", methods=["GET", "HEAD"])
def health():
    """Health check endpoint."""
    return {"status": "ok"}


@app.api_route("/ready", methods=["GET", "HEAD"])
def ready():
    """Readiness endpoint that verifies database connectivity."""
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return {"status": "ready"}
    except OperationalError:
        return JSONResponse(
            status_code=503,
            content={"detail": "Database temporarily unavailable"},
        )
