"""Dashboard router - aggregate stats and metrics for landlord overview."""

from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, case, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import require_org_member, AuthenticatedUser
from app.models.property import Property, Unit
from app.models.lease import Lease
from app.models.inspection import Inspection
from app.models.maintenance import MaintenanceTicket
from app.models.booking import Booking
from app.models.enums import (
    LeaseStatus,
    InspectionStatus,
    MaintenanceStatus,
    PropertyType,
    OccupancyModel,
)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/stats")
async def get_dashboard_stats(
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_org_member),
):
    """Get aggregate dashboard statistics for the organization.
    
    Returns:
    - Property counts (total, by type)
    - Unit counts (total, occupied, vacant)
    - Lease stats (active, expiring soon, pending)
    - Inspection stats (pending, completed this month)
    - Maintenance stats (open, in_progress, completed this month)
    - Revenue metrics (monthly rent roll, deposits held)
    """
    org_id = current_user.org_id
    now = datetime.utcnow()
    thirty_days = now + timedelta(days=30)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # Property counts by type
    prop_query = await db.execute(
        select(
            func.count(Property.id).label("total"),
            func.sum(case((Property.property_type == PropertyType.RESIDENTIAL, 1), else_=0)).label("residential"),
            func.sum(case((Property.property_type == PropertyType.COMMERCIAL, 1), else_=0)).label("commercial"),
            func.sum(case((Property.property_type == PropertyType.MIXED_USE, 1), else_=0)).label("mixed_use"),
        )
        .where(Property.org_id == org_id)
    )
    prop_stats = prop_query.one()

    # Unit counts
    unit_query = await db.execute(
        select(
            func.count(Unit.id).label("total"),
            func.sum(case((Unit.status == "occupied", 1), else_=0)).label("occupied"),
            func.sum(case((Unit.status == "vacant", 1), else_=0)).label("vacant"),
        )
        .join(Property)
        .where(Property.org_id == org_id)
    )
    unit_stats = unit_query.one()

    # Lease stats
    lease_query = await db.execute(
        select(
            func.count(Lease.id).label("total"),
            func.sum(case((Lease.status == LeaseStatus.ACTIVE, 1), else_=0)).label("active"),
            func.sum(case((Lease.status == LeaseStatus.PENDING, 1), else_=0)).label("pending"),
            func.sum(case((Lease.status == LeaseStatus.DRAFT, 1), else_=0)).label("draft"),
            func.sum(case(
                (and_(Lease.status == LeaseStatus.ACTIVE, Lease.end_date <= thirty_days), 1),
                else_=0
            )).label("expiring_soon"),
        )
        .join(Unit)
        .join(Property)
        .where(Property.org_id == org_id)
    )
    lease_stats = lease_query.one()

    # Revenue metrics (active leases only)
    revenue_query = await db.execute(
        select(
            func.coalesce(func.sum(Lease.rent_amount_cents), 0).label("monthly_rent_roll"),
            func.coalesce(func.sum(Lease.deposit_amount_cents), 0).label("deposits_held"),
        )
        .join(Unit)
        .join(Property)
        .where(
            Property.org_id == org_id,
            Lease.status == LeaseStatus.ACTIVE,
        )
    )
    revenue_stats = revenue_query.one()

    # Inspection stats
    insp_query = await db.execute(
        select(
            func.count(Inspection.id).label("total"),
            func.sum(case((Inspection.status == InspectionStatus.DRAFT, 1), else_=0)).label("pending"),
            func.sum(case(
                (and_(Inspection.status == InspectionStatus.SIGNED, Inspection.signed_at >= month_start), 1),
                else_=0
            )).label("completed_this_month"),
        )
        .join(Unit)
        .join(Property)
        .where(Property.org_id == org_id)
    )
    insp_stats = insp_query.one()

    # Maintenance stats
    maint_query = await db.execute(
        select(
            func.count(MaintenanceTicket.id).label("total"),
            func.sum(case((MaintenanceTicket.status == MaintenanceStatus.OPEN, 1), else_=0)).label("open"),
            func.sum(case((MaintenanceTicket.status == MaintenanceStatus.IN_PROGRESS, 1), else_=0)).label("in_progress"),
            func.sum(case(
                (and_(MaintenanceTicket.status == MaintenanceStatus.COMPLETED, MaintenanceTicket.updated_at >= month_start), 1),
                else_=0
            )).label("completed_this_month"),
        )
        .join(Unit)
        .join(Property)
        .where(Property.org_id == org_id)
    )
    maint_stats = maint_query.one()

    return {
        "properties": {
            "total": prop_stats.total or 0,
            "residential": prop_stats.residential or 0,
            "commercial": prop_stats.commercial or 0,
            "mixed_use": prop_stats.mixed_use or 0,
        },
        "units": {
            "total": unit_stats.total or 0,
            "occupied": unit_stats.occupied or 0,
            "vacant": unit_stats.vacant or 0,
            "occupancy_rate": round((unit_stats.occupied or 0) / max(unit_stats.total or 1, 1) * 100, 1),
        },
        "leases": {
            "total": lease_stats.total or 0,
            "active": lease_stats.active or 0,
            "pending": lease_stats.pending or 0,
            "draft": lease_stats.draft or 0,
            "expiring_soon": lease_stats.expiring_soon or 0,
        },
        "revenue": {
            "monthly_rent_roll_cents": revenue_stats.monthly_rent_roll or 0,
            "deposits_held_cents": revenue_stats.deposits_held or 0,
        },
        "inspections": {
            "pending": insp_stats.pending or 0,
            "completed_this_month": insp_stats.completed_this_month or 0,
        },
        "maintenance": {
            "open": maint_stats.open or 0,
            "in_progress": maint_stats.in_progress or 0,
            "completed_this_month": maint_stats.completed_this_month or 0,
        },
    }


@router.get("/leases/expiring")
async def get_expiring_leases(
    days: int = Query(default=30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_org_member),
):
    """Get leases expiring within the specified number of days.
    
    Returns lease details with property/unit info for renewal workflow.
    """
    org_id = current_user.org_id
    now = datetime.utcnow()
    cutoff = now + timedelta(days=days)

    result = await db.execute(
        select(Lease, Unit, Property)
        .join(Unit, Lease.unit_id == Unit.id)
        .join(Property, Unit.property_id == Property.id)
        .where(
            Property.org_id == org_id,
            Lease.status == LeaseStatus.ACTIVE,
            Lease.end_date <= cutoff,
            Lease.end_date >= now,
        )
        .order_by(Lease.end_date.asc())
    )
    rows = result.all()

    leases = []
    for lease, unit, prop in rows:
        days_until_expiry = (lease.end_date - now.date()).days if hasattr(lease.end_date, 'days') else (lease.end_date - now).days
        leases.append({
            "id": str(lease.id),
            "tenant_name": lease.tenant_name,
            "tenant_email": lease.tenant_email,
            "start_date": lease.start_date.isoformat() if lease.start_date else None,
            "end_date": lease.end_date.isoformat() if lease.end_date else None,
            "days_until_expiry": max(days_until_expiry, 0),
            "rent_amount_cents": lease.rent_amount_cents,
            "lease_type": lease.lease_type.value if lease.lease_type else None,
            "unit": {
                "id": str(unit.id),
                "unit_number": unit.unit_number,
                "sq_ft": unit.sq_ft,
            },
            "property": {
                "id": str(prop.id),
                "name": prop.name,
                "address": prop.address,
                "property_type": prop.property_type.value if prop.property_type else None,
            },
        })

    return {
        "leases": leases,
        "total": len(leases),
        "days_window": days,
    }


@router.get("/activity/recent")
async def get_recent_activity(
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_org_member),
):
    """Get recent activity across the organization.
    
    Returns mixed feed of recent:
    - New leases
    - Completed inspections
    - Maintenance updates
    - Bookings (for STR properties)
    """
    org_id = current_user.org_id
    activities = []

    # Recent leases (last 30 days)
    lease_result = await db.execute(
        select(Lease, Unit, Property)
        .join(Unit, Lease.unit_id == Unit.id)
        .join(Property, Unit.property_id == Property.id)
        .where(Property.org_id == org_id)
        .order_by(Lease.created_at.desc())
        .limit(limit)
    )
    for lease, unit, prop in lease_result.all():
        activities.append({
            "type": "lease",
            "action": f"Lease {lease.status.value if lease.status else 'created'}",
            "timestamp": lease.created_at.isoformat() if lease.created_at else None,
            "details": {
                "lease_id": str(lease.id),
                "tenant_name": lease.tenant_name,
                "unit": unit.unit_number,
                "property": prop.name,
            },
        })

    # Recent inspections
    insp_result = await db.execute(
        select(Inspection, Unit, Property)
        .join(Unit, Inspection.unit_id == Unit.id)
        .join(Property, Unit.property_id == Property.id)
        .where(Property.org_id == org_id)
        .order_by(Inspection.updated_at.desc())
        .limit(limit)
    )
    for insp, unit, prop in insp_result.all():
        activities.append({
            "type": "inspection",
            "action": f"{insp.inspection_type.value if insp.inspection_type else 'Inspection'} - {insp.status.value if insp.status else 'updated'}",
            "timestamp": insp.updated_at.isoformat() if insp.updated_at else None,
            "details": {
                "inspection_id": str(insp.id),
                "unit": unit.unit_number,
                "property": prop.name,
            },
        })

    # Recent maintenance
    maint_result = await db.execute(
        select(MaintenanceTicket, Unit, Property)
        .join(Unit, MaintenanceTicket.unit_id == Unit.id)
        .join(Property, Unit.property_id == Property.id)
        .where(Property.org_id == org_id)
        .order_by(MaintenanceTicket.updated_at.desc())
        .limit(limit)
    )
    for ticket, unit, prop in maint_result.all():
        activities.append({
            "type": "maintenance",
            "action": f"Maintenance - {ticket.status.value if ticket.status else 'updated'}",
            "timestamp": ticket.updated_at.isoformat() if ticket.updated_at else None,
            "details": {
                "ticket_id": str(ticket.id),
                "title": ticket.title,
                "unit": unit.unit_number,
                "property": prop.name,
            },
        })

    # Sort by timestamp and limit
    activities.sort(key=lambda x: x["timestamp"] or "", reverse=True)
    return {
        "activities": activities[:limit],
        "total": len(activities[:limit]),
    }


@router.get("/occupancy/by-property")
async def get_occupancy_by_property(
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_org_member),
):
    """Get occupancy breakdown by property.
    
    Returns per-property stats for portfolio overview.
    """
    org_id = current_user.org_id

    result = await db.execute(
        select(
            Property.id,
            Property.name,
            Property.property_type,
            Property.occupancy_model,
            func.count(Unit.id).label("total_units"),
            func.sum(case((Unit.status == "occupied", 1), else_=0)).label("occupied_units"),
        )
        .outerjoin(Unit, Unit.property_id == Property.id)
        .where(Property.org_id == org_id)
        .group_by(Property.id)
        .order_by(Property.name)
    )
    rows = result.all()

    properties = []
    for row in rows:
        total = row.total_units or 0
        occupied = row.occupied_units or 0
        properties.append({
            "id": str(row.id),
            "name": row.name,
            "property_type": row.property_type.value if row.property_type else None,
            "occupancy_model": row.occupancy_model.value if row.occupancy_model else None,
            "total_units": total,
            "occupied_units": occupied,
            "vacant_units": total - occupied,
            "occupancy_rate": round(occupied / max(total, 1) * 100, 1),
        })

    return {
        "properties": properties,
        "total": len(properties),
    }
