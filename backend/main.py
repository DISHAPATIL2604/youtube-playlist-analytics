"""
main.py — FastAPI application entry point.
"""
import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.database import create_tables
from backend.routes import playlist
from backend.schemas import HealthResponse

# ---------------------------------------------------------------------------
# Logging configuration
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Application lifespan (startup / shutdown)
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create DB tables on startup."""
    logger.info("Starting YouTube Playlist Analytics API...")
    try:
        create_tables()
        logger.info("Database tables verified/created successfully.")
    except Exception as e:
        logger.error(f"Failed to initialise database: {e}")
        raise
    yield
    logger.info("Shutting down API.")


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------

app = FastAPI(
    title="YouTube Playlist Analytics API",
    description=(
        "Fetch, store, and analyse YouTube playlist statistics. "
        "Powered by YouTube Data API v3 and PostgreSQL."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Allow Streamlit (any origin during development) to call the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(playlist.router)


# ---------------------------------------------------------------------------
# Health endpoint
# ---------------------------------------------------------------------------

@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["system"],
    summary="API health check",
)
def health_check():
    """Verify the API and database are reachable."""
    from sqlalchemy import text
    from backend.database import engine

    db_status = "unreachable"
    message = ""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception as e:
        message = str(e)
        logger.warning(f"Health check DB error: {e}")

    return HealthResponse(
        status="ok" if db_status == "connected" else "degraded",
        database=db_status,
        message=message,
    )


# ---------------------------------------------------------------------------
# Root redirect
# ---------------------------------------------------------------------------

@app.get("/", include_in_schema=False)
def root():
    return {"message": "YouTube Playlist Analytics API", "docs": "/docs"}
