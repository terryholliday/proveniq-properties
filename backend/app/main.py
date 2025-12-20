"""PROVENIQ Properties - FastAPI Application Entry Point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
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
)

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

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],  # Frontend dev
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
