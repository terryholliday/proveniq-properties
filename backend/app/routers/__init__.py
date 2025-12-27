"""API Routers for PROVENIQ Properties."""

from app.routers.auth import router as auth_router
from app.routers.org import router as org_router
from app.routers.properties import router as properties_router
from app.routers.leases import router as leases_router
from app.routers.inspections import router as inspections_router
from app.routers.vendors import router as vendors_router
from app.routers.maintenance import router as maintenance_router
from app.routers.bookings import router as bookings_router
from app.routers.turnovers import router as turnovers_router
from app.routers.dashboard import router as dashboard_router
from app.routers.reports import router as reports_router
from app.routers.mason_agent import router as mason_agent_router

__all__ = [
    "auth_router",
    "org_router",
    "properties_router",
    "leases_router",
    "inspections_router",
    "vendors_router",
    "maintenance_router",
    "bookings_router",
    "turnovers_router",
    "dashboard_router",
    "reports_router",
    "mason_agent_router",
]
