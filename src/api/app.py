"""FastAPI application entrypoint."""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import FastAPI, Depends, HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from src.config import settings
from src.db import get_db, Base, engine
from src.api import routes

# Setup logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Security
security = HTTPBearer()


def verify_token(credentials: HTTPAuthorizationCredentials = Security(security)) -> str:
    """Verify API token.

    Args:
        credentials: HTTP Bearer credentials

    Returns:
        Token value

    Raises:
        HTTPException: If token invalid
    """
    if credentials.credentials != settings.api_auth_token:
        raise HTTPException(status_code=401, detail="Invalid authentication token")
    return credentials.credentials


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager.

    Args:
        app: FastAPI application

    Yields:
        None
    """
    # Startup
    logger.info("Starting Alpha Wallet Scout API")
    Base.metadata.create_all(bind=engine)

    yield

    # Shutdown
    logger.info("Shutting down Alpha Wallet Scout API")


# Create app
app = FastAPI(
    title="Alpha Wallet Scout API",
    description="On-chain trader discovery and alerting system",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routes
app.include_router(routes.router, prefix="/api/v1")


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint.

    Returns:
        Health status
    """
    return {"status": "healthy", "service": "alpha-wallet-scout"}


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint.

    Returns:
        API info
    """
    return {
        "service": "Alpha Wallet Scout",
        "version": "0.1.0",
        "docs": "/docs",
    }
