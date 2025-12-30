"""Reports router - financial and operational reporting for landlords."""

from datetime import datetime, date, timedelta
from typing import Optional, List
from uuid import UUID
from enum import Enum

from fastapi import APIRouter, Depends, Query, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func, case, and_, extract
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.core.database import get_db
from app.core.security import require_org_admin, AuthenticatedUser
from app.models.property import Property, Unit
from app.models.lease import Lease
from app.models.inspection import Inspection, InspectionItem
from app.models.maintenance import MaintenanceTicket
from app.models.enums import (
    LeaseStatus,
    LeaseType,
    InspectionStatus,
    MaintenanceStatus,
    PropertyType,
)

router = APIRouter(prefix="/reports", tags=["reports"])


class ReportPeriod(str, Enum):
    MONTH = "month"
    QUARTER = "quarter"
    YEAR = "year"
    CUSTOM = "custom"


class RentRollResponse(BaseModel):
    """Rent roll report response."""
    generated_at: datetime
    period_start: date
    period_end: date
    total_properties: int
    total_units: int
    occupied_units: int
    vacancy_rate: float
    total_monthly_rent_cents: int
    total_annual_rent_cents: int
    properties: List[dict]


@router.get("/rent-roll", response_model=RentRollResponse)
async def get_rent_roll_report(
    property_id: Optional[UUID] = None,
    as_of_date: Optional[date] = None,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_org_admin),
):
    """Generate rent roll report.
    
    Shows all units with current lease info, rent amounts, and tenant details.
    Can be filtered by property.
    """
    org_id = current_user.org_id
    report_date = as_of_date or date.today()

    # Base query for properties
    prop_query = select(Property).where(Property.org_id == org_id)
    if property_id:
        prop_query = prop_query.where(Property.id == property_id)
    
    prop_result = await db.execute(prop_query.order_by(Property.name))
    properties = prop_result.scalars().all()

    if not properties:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No properties found")

    report_properties = []
    total_monthly_rent = 0
    total_units = 0
    occupied_units = 0

    for prop in properties:
        # Get units with active leases
        unit_query = await db.execute(
            select(Unit, Lease)
            .outerjoin(Lease, and_(
                Lease.unit_id == Unit.id,
                Lease.status == LeaseStatus.ACTIVE,
            ))
            .where(Unit.property_id == prop.id)
            .order_by(Unit.unit_number)
        )
        unit_rows = unit_query.all()

        prop_units = []
        prop_monthly_rent = 0
        prop_occupied = 0

        for unit, lease in unit_rows:
            total_units += 1
            unit_data = {
                "unit_id": str(unit.id),
                "unit_number": unit.unit_number,
                "sq_ft": unit.sq_ft,
                "bedrooms": unit.bedrooms,
                "bathrooms": unit.bathrooms,
                "status": unit.status,
                "lease": None,
            }

            if lease:
                occupied_units += 1
                prop_occupied += 1
                prop_monthly_rent += lease.rent_amount_cents or 0
                total_monthly_rent += lease.rent_amount_cents or 0
                
                unit_data["lease"] = {
                    "lease_id": str(lease.id),
                    "tenant_name": lease.tenant_name,
                    "tenant_email": lease.tenant_email,
                    "lease_type": lease.lease_type.value if lease.lease_type else None,
                    "start_date": lease.start_date.isoformat() if lease.start_date else None,
                    "end_date": lease.end_date.isoformat() if lease.end_date else None,
                    "rent_amount_cents": lease.rent_amount_cents,
                    "deposit_amount_cents": lease.deposit_amount_cents,
                    "pro_rata_share_bps": lease.pro_rata_share_bps,
                    "cam_budget_cents": lease.cam_budget_cents,
                }

            prop_units.append(unit_data)

        report_properties.append({
            "property_id": str(prop.id),
            "name": prop.name,
            "address": prop.address,
            "property_type": prop.property_type.value if prop.property_type else None,
            "total_units": len(prop_units),
            "occupied_units": prop_occupied,
            "vacancy_rate": round((1 - prop_occupied / max(len(prop_units), 1)) * 100, 1),
            "monthly_rent_cents": prop_monthly_rent,
            "units": prop_units,
        })

    vacancy_rate = round((1 - occupied_units / max(total_units, 1)) * 100, 1)

    return RentRollResponse(
        generated_at=datetime.utcnow(),
        period_start=report_date,
        period_end=report_date,
        total_properties=len(report_properties),
        total_units=total_units,
        occupied_units=occupied_units,
        vacancy_rate=vacancy_rate,
        total_monthly_rent_cents=total_monthly_rent,
        total_annual_rent_cents=total_monthly_rent * 12,
        properties=report_properties,
    )


@router.get("/lease-expiration")
async def get_lease_expiration_report(
    months_ahead: int = Query(default=12, ge=1, le=24),
    property_id: Optional[UUID] = None,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_org_admin),
):
    """Generate lease expiration report.
    
    Shows leases expiring within the specified timeframe, grouped by month.
    Useful for renewal planning.
    """
    org_id = current_user.org_id
    now = datetime.utcnow()
    end_date = now + timedelta(days=months_ahead * 30)

    query = (
        select(Lease, Unit, Property)
        .join(Unit, Lease.unit_id == Unit.id)
        .join(Property, Unit.property_id == Property.id)
        .where(
            Property.org_id == org_id,
            Lease.status == LeaseStatus.ACTIVE,
            Lease.end_date >= now,
            Lease.end_date <= end_date,
        )
    )
    if property_id:
        query = query.where(Property.id == property_id)
    
    query = query.order_by(Lease.end_date)
    result = await db.execute(query)
    rows = result.all()

    # Group by month
    by_month = {}
    total_rent_at_risk = 0

    for lease, unit, prop in rows:
        month_key = lease.end_date.strftime("%Y-%m") if lease.end_date else "unknown"
        if month_key not in by_month:
            by_month[month_key] = {
                "month": month_key,
                "month_label": lease.end_date.strftime("%B %Y") if lease.end_date else "Unknown",
                "lease_count": 0,
                "rent_at_risk_cents": 0,
                "leases": [],
            }
        
        rent = lease.rent_amount_cents or 0
        total_rent_at_risk += rent
        by_month[month_key]["lease_count"] += 1
        by_month[month_key]["rent_at_risk_cents"] += rent
        by_month[month_key]["leases"].append({
            "lease_id": str(lease.id),
            "tenant_name": lease.tenant_name,
            "end_date": lease.end_date.isoformat() if lease.end_date else None,
            "rent_amount_cents": rent,
            "lease_type": lease.lease_type.value if lease.lease_type else None,
            "unit_number": unit.unit_number,
            "property_name": prop.name,
            "property_id": str(prop.id),
        })

    return {
        "generated_at": datetime.utcnow().isoformat(),
        "months_ahead": months_ahead,
        "total_expiring_leases": len(rows),
        "total_rent_at_risk_cents": total_rent_at_risk,
        "by_month": list(by_month.values()),
    }


@router.get("/maintenance-summary")
async def get_maintenance_summary_report(
    period: ReportPeriod = ReportPeriod.MONTH,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    property_id: Optional[UUID] = None,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_org_admin),
):
    """Generate maintenance summary report.
    
    Shows maintenance ticket counts, costs, and response times.
    """
    org_id = current_user.org_id
    now = datetime.utcnow()

    # Determine date range
    if period == ReportPeriod.CUSTOM and start_date and end_date:
        period_start = datetime.combine(start_date, datetime.min.time())
        period_end = datetime.combine(end_date, datetime.max.time())
    elif period == ReportPeriod.YEAR:
        period_start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        period_end = now
    elif period == ReportPeriod.QUARTER:
        quarter_start_month = ((now.month - 1) // 3) * 3 + 1
        period_start = now.replace(month=quarter_start_month, day=1, hour=0, minute=0, second=0, microsecond=0)
        period_end = now
    else:  # MONTH
        period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        period_end = now

    # Base query
    query = (
        select(MaintenanceTicket, Unit, Property)
        .join(Unit, MaintenanceTicket.unit_id == Unit.id)
        .join(Property, Unit.property_id == Property.id)
        .where(
            Property.org_id == org_id,
            MaintenanceTicket.created_at >= period_start,
            MaintenanceTicket.created_at <= period_end,
        )
    )
    if property_id:
        query = query.where(Property.id == property_id)

    result = await db.execute(query)
    rows = result.all()

    # Aggregate stats
    total_tickets = len(rows)
    by_status = {"open": 0, "in_progress": 0, "completed": 0, "cancelled": 0}
    by_priority = {"low": 0, "medium": 0, "high": 0, "emergency": 0}
    total_cost = 0
    completed_count = 0

    for ticket, unit, prop in rows:
        status_key = ticket.status.value if ticket.status else "open"
        by_status[status_key] = by_status.get(status_key, 0) + 1
        
        priority_key = ticket.priority.value if ticket.priority else "medium"
        by_priority[priority_key] = by_priority.get(priority_key, 0) + 1
        
        if ticket.actual_cost_cents:
            total_cost += ticket.actual_cost_cents
        
        if ticket.status == MaintenanceStatus.COMPLETED:
            completed_count += 1

    return {
        "generated_at": datetime.utcnow().isoformat(),
        "period": period.value,
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "total_tickets": total_tickets,
        "by_status": by_status,
        "by_priority": by_priority,
        "total_cost_cents": total_cost,
        "completion_rate": round(completed_count / max(total_tickets, 1) * 100, 1),
    }


@router.get("/inspection-summary")
async def get_inspection_summary_report(
    period: ReportPeriod = ReportPeriod.MONTH,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    property_id: Optional[UUID] = None,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_org_admin),
):
    """Generate inspection summary report.
    
    Shows inspection counts by type and status, plus damage findings.
    """
    org_id = current_user.org_id
    now = datetime.utcnow()

    # Determine date range (same logic as maintenance)
    if period == ReportPeriod.CUSTOM and start_date and end_date:
        period_start = datetime.combine(start_date, datetime.min.time())
        period_end = datetime.combine(end_date, datetime.max.time())
    elif period == ReportPeriod.YEAR:
        period_start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        period_end = now
    elif period == ReportPeriod.QUARTER:
        quarter_start_month = ((now.month - 1) // 3) * 3 + 1
        period_start = now.replace(month=quarter_start_month, day=1, hour=0, minute=0, second=0, microsecond=0)
        period_end = now
    else:
        period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        period_end = now

    # Get inspections
    query = (
        select(Inspection, Unit, Property)
        .join(Unit, Inspection.unit_id == Unit.id)
        .join(Property, Unit.property_id == Property.id)
        .where(
            Property.org_id == org_id,
            Inspection.created_at >= period_start,
            Inspection.created_at <= period_end,
        )
    )
    if property_id:
        query = query.where(Property.id == property_id)

    result = await db.execute(query)
    rows = result.all()

    # Get inspection IDs for item query
    inspection_ids = [insp.id for insp, _, _ in rows]

    # Get damage items
    damage_query = await db.execute(
        select(InspectionItem)
        .where(
            InspectionItem.inspection_id.in_(inspection_ids),
            InspectionItem.condition.in_(["damaged", "missing", "needs_repair"]),
        )
    )
    damage_items = damage_query.scalars().all()

    # Aggregate
    by_type = {}
    by_status = {"draft": 0, "pending": 0, "signed": 0}
    signed_count = 0

    for insp, unit, prop in rows:
        type_key = insp.inspection_type.value if insp.inspection_type else "other"
        by_type[type_key] = by_type.get(type_key, 0) + 1
        
        status_key = insp.status.value if insp.status else "draft"
        by_status[status_key] = by_status.get(status_key, 0) + 1
        
        if insp.status == InspectionStatus.SIGNED:
            signed_count += 1

    return {
        "generated_at": datetime.utcnow().isoformat(),
        "period": period.value,
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "total_inspections": len(rows),
        "by_type": by_type,
        "by_status": by_status,
        "completion_rate": round(signed_count / max(len(rows), 1) * 100, 1),
        "damage_items_found": len(damage_items),
    }


@router.get("/commercial/cam-reconciliation")
async def get_cam_reconciliation_report(
    property_id: UUID,
    year: int = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_org_admin),
):
    """Generate CAM (Common Area Maintenance) reconciliation report.
    
    For NNN commercial leases - shows pro-rata shares and CAM allocations.
    """
    org_id = current_user.org_id
    report_year = year or datetime.utcnow().year

    # Get property
    prop_result = await db.execute(
        select(Property)
        .where(Property.id == property_id, Property.org_id == org_id)
    )
    prop = prop_result.scalar_one_or_none()
    
    if not prop:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")
    
    if prop.property_type == PropertyType.RESIDENTIAL:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CAM reconciliation only applies to commercial properties"
        )

    # Get units with NNN leases
    query = await db.execute(
        select(Unit, Lease)
        .join(Lease, and_(
            Lease.unit_id == Unit.id,
            Lease.status == LeaseStatus.ACTIVE,
            Lease.lease_type == LeaseType.COMMERCIAL_NNN,
        ))
        .where(Unit.property_id == property_id)
        .order_by(Unit.unit_number)
    )
    rows = query.all()

    tenants = []
    total_pro_rata_bps = 0
    total_cam_budget = 0

    for unit, lease in rows:
        pro_rata = lease.pro_rata_share_bps or 0
        cam_budget = lease.cam_budget_cents or 0
        annual_cam = int(cam_budget * 12)
        
        total_pro_rata_bps += pro_rata
        total_cam_budget += annual_cam
        
        tenants.append({
            "unit_id": str(unit.id),
            "unit_number": unit.unit_number,
            "sq_ft": unit.sq_ft,
            "tenant_name": lease.tenant_name,
            "pro_rata_share_bps": pro_rata,
            "pro_rata_share_pct": round(pro_rata / 100, 2),
            "monthly_cam_budget_cents": cam_budget,
            "annual_cam_budget_cents": annual_cam,
        })

    return {
        "generated_at": datetime.utcnow().isoformat(),
        "year": report_year,
        "property": {
            "id": str(prop.id),
            "name": prop.name,
            "address": prop.address,
            "total_leasable_sq_ft": prop.total_leasable_sq_ft,
        },
        "total_nnn_tenants": len(tenants),
        "total_pro_rata_bps": total_pro_rata_bps,
        "total_annual_cam_budget_cents": total_cam_budget,
        "tenants": tenants,
    }
