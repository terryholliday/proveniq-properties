"""PROVENIQ Properties - FastAPI Application Entry Point."""

import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.env_validation import validate_environment
from app.routers import (
    auth_router,
    org_router,
    properties_router,
    leases_router,
    inspections_router,
    vendors_router,
    maintenance_router,
    bookings_router,
    turnovers_router,
    dashboard_router,
    reports_router,
    mason_agent_router,
)

# CRITICAL: Validate environment before proceeding
# This will hard-fail (exit 1) if required configuration is missing
validate_environment()

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    yield
    # Shutdown


app = FastAPI(
    title=settings.app_name,
    description="Unified landlord platform for residential + commercial properties. Immutable evidence, tenant invites, inspection diffs, and maintenance triage.",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
)

# CORS - Dynamically configured from ALLOWED_ORIGINS environment variable
# In production, wildcard (*) is blocked by env_validation.py
allowed_origins = [origin.strip() for origin in settings.allowed_origins.split(",")]

# Log resolved CORS origins at startup for visibility
print(f"🔒 CORS configured with origins: {allowed_origins}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API v1 routers
app.include_router(auth_router, prefix=settings.api_v1_prefix)
app.include_router(org_router, prefix=settings.api_v1_prefix)
app.include_router(properties_router, prefix=settings.api_v1_prefix)
app.include_router(leases_router, prefix=settings.api_v1_prefix)
app.include_router(inspections_router, prefix=settings.api_v1_prefix)
app.include_router(vendors_router, prefix=settings.api_v1_prefix)
app.include_router(maintenance_router, prefix=settings.api_v1_prefix)
app.include_router(bookings_router, prefix=settings.api_v1_prefix)  # STR support
app.include_router(turnovers_router, prefix=settings.api_v1_prefix)  # STR turnover workflow
app.include_router(dashboard_router, prefix=settings.api_v1_prefix)  # Dashboard & reporting
app.include_router(reports_router, prefix=settings.api_v1_prefix)  # Financial & operational reports
app.include_router(mason_agent_router, prefix=settings.api_v1_prefix)  # Mason Auto-Agent Mode


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": settings.app_name}


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": settings.app_name,
        "version": "1.0.0",
        "docs": "/docs" if settings.debug else "Disabled in production",
    }
