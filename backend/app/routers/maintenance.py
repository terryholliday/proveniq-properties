"""Maintenance router."""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user, require_org_member, AuthenticatedUser
from app.models.property import Property, Unit
from app.models.lease import Lease, TenantAccess
from app.models.maintenance import MaintenanceTicket
from app.models.vendor import Vendor
from app.models.enums import MaintenanceStatus
from app.schemas.maintenance import (
    MaintenanceCreate,
    MaintenanceUpdate,
    MaintenanceAssignRequest,
    MaintenanceResponse,
    MaintenanceTriageRequest,
    MaintenanceTriageResponse,
)
from app.services.audit import AuditService
from app.services.mason import MasonService

router = APIRouter(prefix="/maintenance", tags=["maintenance"])


@router.post("", response_model=MaintenanceResponse, status_code=status.HTTP_201_CREATED)
async def create_maintenance_ticket(
    data: MaintenanceCreate,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """Create a maintenance ticket."""
    # Verify unit access
    if current_user.org_id:
        result = await db.execute(
            select(Unit)
            .join(Property)
            .where(
                Unit.id == data.unit_id,
                Property.org_id == current_user.org_id,
            )
        )
    else:
        # Tenant - verify through lease
        result = await db.execute(
            select(Unit)
            .join(Lease)
            .join(TenantAccess)
            .where(
                Unit.id == data.unit_id,
                TenantAccess.tenant_user_id == current_user.db_user_id,
            )
        )

    unit = result.scalar_one_or_none()
    if not unit:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unit not found")

    ticket = MaintenanceTicket(
        unit_id=data.unit_id,
        created_by_id=current_user.db_user_id,
        title=data.title,
        description=data.description,
        category=data.category,
        priority=data.priority,
        is_tenant_visible=data.is_tenant_visible,
    )
    db.add(ticket)
    await db.commit()
    await db.refresh(ticket)

    return MaintenanceResponse.model_validate(ticket)


@router.get("", response_model=List[MaintenanceResponse])
async def list_maintenance_tickets(
    unit_id: Optional[UUID] = None,
    status: Optional[MaintenanceStatus] = None,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """List maintenance tickets."""
    if current_user.org_id:
        query = (
            select(MaintenanceTicket)
            .join(Unit)
            .join(Property)
            .where(Property.org_id == current_user.org_id)
        )
    else:
        # Tenant - only see visible tickets for their units
        query = (
            select(MaintenanceTicket)
            .join(Unit)
            .join(Lease)
            .join(TenantAccess)
            .where(
                TenantAccess.tenant_user_id == current_user.db_user_id,
                MaintenanceTicket.is_tenant_visible == True,
            )
        )

    if unit_id:
        query = query.where(MaintenanceTicket.unit_id == unit_id)
    if status:
        query = query.where(MaintenanceTicket.status == status)

    query = query.order_by(MaintenanceTicket.priority, MaintenanceTicket.created_at.desc())

    result = await db.execute(query)
    tickets = result.scalars().all()

    return [MaintenanceResponse.model_validate(t) for t in tickets]


@router.get("/{ticket_id}", response_model=MaintenanceResponse)
async def get_maintenance_ticket(
    ticket_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """Get a maintenance ticket by ID."""
    if current_user.org_id:
        result = await db.execute(
            select(MaintenanceTicket)
            .join(Unit)
            .join(Property)
            .where(
                MaintenanceTicket.id == ticket_id,
                Property.org_id == current_user.org_id,
            )
        )
    else:
        result = await db.execute(
            select(MaintenanceTicket)
            .join(Unit)
            .join(Lease)
            .join(TenantAccess)
            .where(
                MaintenanceTicket.id == ticket_id,
                TenantAccess.tenant_user_id == current_user.db_user_id,
                MaintenanceTicket.is_tenant_visible == True,
            )
        )

    ticket = result.scalar_one_or_none()
    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")

    return MaintenanceResponse.model_validate(ticket)


@router.patch("/{ticket_id}", response_model=MaintenanceResponse)
async def update_maintenance_ticket(
    ticket_id: UUID,
    data: MaintenanceUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_org_member),
):
    """Update a maintenance ticket (org members only)."""
    result = await db.execute(
        select(MaintenanceTicket)
        .join(Unit)
        .join(Property)
        .where(
            MaintenanceTicket.id == ticket_id,
            Property.org_id == current_user.org_id,
        )
    )
    ticket = result.scalar_one_or_none()

    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")

    update_data = data.model_dump(exclude_unset=True)
    
    # Handle status change to completed
    if update_data.get("status") == MaintenanceStatus.COMPLETED:
        update_data["completed_at"] = datetime.utcnow()

    for field, value in update_data.items():
        setattr(ticket, field, value)

    await db.commit()
    await db.refresh(ticket)

    return MaintenanceResponse.model_validate(ticket)


@router.patch("/{ticket_id}/assign", response_model=MaintenanceResponse)
async def assign_maintenance_ticket(
    ticket_id: UUID,
    data: MaintenanceAssignRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_org_member),
):
    """Assign maintenance ticket to vendor or org member.
    
    Tenants cannot assign vendors (guardrail).
    """
    result = await db.execute(
        select(MaintenanceTicket)
        .join(Unit)
        .join(Property)
        .where(
            MaintenanceTicket.id == ticket_id,
            Property.org_id == current_user.org_id,
        )
    )
    ticket = result.scalar_one_or_none()

    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")

    # Verify vendor belongs to org if assigning vendor
    if data.assigned_vendor_id:
        vendor_result = await db.execute(
            select(Vendor).where(
                Vendor.id == data.assigned_vendor_id,
                Vendor.org_id == current_user.org_id,
                Vendor.is_active == True,
            )
        )
        if not vendor_result.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vendor not found")

    ticket.assigned_vendor_id = data.assigned_vendor_id
    ticket.assigned_org_member_user_id = data.assigned_org_member_user_id
    
    if ticket.status == MaintenanceStatus.OPEN:
        ticket.status = MaintenanceStatus.ACKNOWLEDGED

    # Audit log
    audit = AuditService(db)
    await audit.log_vendor_assigned(
        ticket_id=ticket_id,
        org_id=current_user.org_id,
        user_id=current_user.db_user_id,
        vendor_id=data.assigned_vendor_id,
        org_member_id=data.assigned_org_member_user_id,
        ip_address=request.client.host if request.client else None,
    )

    await db.commit()
    await db.refresh(ticket)

    return MaintenanceResponse.model_validate(ticket)


@router.post("/{ticket_id}/triage", response_model=MaintenanceTriageResponse)
async def triage_maintenance_ticket(
    ticket_id: UUID,
    data: MaintenanceTriageRequest,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_org_member),
):
    """Run Mason AI triage on maintenance ticket.
    
    GUARDRAILS (Mason):
    - Never auto-deny maintenance
    - Never auto-dispatch vendors
    - Advisory only
    """
    result = await db.execute(
        select(MaintenanceTicket)
        .join(Unit)
        .join(Property)
        .where(
            MaintenanceTicket.id == ticket_id,
            Property.org_id == current_user.org_id,
        )
    )
    ticket = result.scalar_one_or_none()

    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")

    mason = MasonService(db)
    triage_result = await mason.triage_maintenance(
        ticket_id=ticket_id,
        title=ticket.title,
        description=ticket.description,
        org_id=current_user.org_id,
    )

    # Store triage result (advisory only - does NOT auto-update ticket)
    ticket.mason_triage_result = triage_result
    ticket.mason_triaged_at = datetime.utcnow()

    # Get suggested vendors if requested
    suggested_vendor_ids = []
    if data.include_vendor_suggestions:
        vendor_result = await db.execute(
            select(Vendor).where(
                Vendor.org_id == current_user.org_id,
                Vendor.specialty == triage_result["suggested_category"],
                Vendor.is_active == True,
            ).order_by(Vendor.is_preferred.desc()).limit(3)
        )
        suggested_vendor_ids = [v.id for v in vendor_result.scalars().all()]

    await db.commit()

    return MaintenanceTriageResponse(
        ticket_id=ticket_id,
        suggested_category=triage_result["suggested_category"],
        suggested_priority=triage_result["suggested_priority"],
        estimated_cost_cents=triage_result.get("estimated_cost_cents"),
        suggested_vendor_ids=suggested_vendor_ids,
        reasoning=triage_result["reasoning"],
        triaged_at=datetime.utcnow(),
    )
