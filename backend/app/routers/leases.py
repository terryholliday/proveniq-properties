"""Leases router."""

from datetime import datetime
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import require_org_member, AuthenticatedUser
from app.models.property import Property, Unit
from app.models.lease import Lease
from app.models.enums import LeaseType, PropertyType
from app.schemas.lease import (
    LeaseCreate,
    LeaseUpdate,
    LeaseResponse,
    LeaseListResponse,
    LeaseInviteRequest,
    LeaseInviteResponse,
    LeaseRenewalRequest,
    LeaseRenewalResponse,
)
from app.models.inspection import Inspection
from app.services.audit import AuditService

router = APIRouter(prefix="/leases", tags=["leases"])


@router.post("", response_model=LeaseResponse, status_code=status.HTTP_201_CREATED)
async def create_lease(
    data: LeaseCreate,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_org_member),
):
    """Create a new lease (draft status).
    
    NNN validation:
    - NNN leases require sq_ft + total_leasable_sq_ft + pro_rata_share_bps
    """
    # Get unit with property
    result = await db.execute(
        select(Unit, Property)
        .join(Property)
        .where(
            Unit.id == data.unit_id,
            Property.org_id == current_user.org_id,
        )
    )
    row = result.one_or_none()

    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unit not found")

    unit, prop = row

    # NNN lease validation
    if data.lease_type == LeaseType.COMMERCIAL_NNN:
        errors = []
        if not unit.sq_ft:
            errors.append("Unit sq_ft is required for NNN leases")
        if not prop.total_leasable_sq_ft:
            errors.append("Property total_leasable_sq_ft is required for NNN leases")
        if not data.pro_rata_share_bps:
            errors.append("pro_rata_share_bps is required for NNN leases")
        
        if errors:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="; ".join(errors),
            )

    # Commercial lease type validation
    if prop.property_type == PropertyType.RESIDENTIAL:
        if data.lease_type in (LeaseType.COMMERCIAL_GROSS, LeaseType.COMMERCIAL_NNN):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot create commercial lease on residential property",
            )

    lease = Lease(
        unit_id=data.unit_id,
        lease_type=data.lease_type,
        start_date=data.start_date,
        end_date=data.end_date,
        rent_amount_cents=data.rent_amount_cents,
        deposit_amount_cents=data.deposit_amount_cents,
        pro_rata_share_bps=data.pro_rata_share_bps,
        cam_budget_cents=data.cam_budget_cents,
        tenant_email=data.tenant_email,
        tenant_name=data.tenant_name,
        tenant_phone=data.tenant_phone,
        notes=data.notes,
    )
    db.add(lease)
    await db.commit()
    await db.refresh(lease)

    return LeaseResponse.model_validate(lease)


@router.get("", response_model=LeaseListResponse)
async def list_leases(
    unit_id: UUID = None,
    status: str = None,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_org_member),
):
    """List leases (org-scoped) with denormalized property/unit info."""
    from sqlalchemy.orm import selectinload
    
    query = (
        select(Lease, Unit, Property)
        .join(Unit, Lease.unit_id == Unit.id)
        .join(Property, Unit.property_id == Property.id)
        .where(Property.org_id == current_user.org_id)
    )

    if unit_id:
        query = query.where(Lease.unit_id == unit_id)
    if status:
        query = query.where(Lease.status == status)

    query = query.order_by(Lease.created_at.desc())

    result = await db.execute(query)
    rows = result.all()

    # Get inspection counts for each lease
    lease_ids = [row[0].id for row in rows]
    inspection_query = await db.execute(
        select(Inspection.lease_id, Inspection.inspection_type)
        .where(Inspection.lease_id.in_(lease_ids))
        .where(Inspection.status == "signed")
    )
    inspection_rows = inspection_query.all()
    
    # Build lookup
    move_in_leases = set()
    move_out_leases = set()
    for lease_id, insp_type in inspection_rows:
        if insp_type == "move_in":
            move_in_leases.add(lease_id)
        elif insp_type == "move_out":
            move_out_leases.add(lease_id)

    leases = []
    for lease, unit, prop in rows:
        lease_data = LeaseResponse.model_validate(lease)
        lease_data.unit_number = unit.unit_number
        lease_data.property_name = prop.name
        lease_data.property_id = prop.id
        lease_data.occupancy_model = prop.occupancy_model.value if prop.occupancy_model else None
        lease_data.has_move_in_inspection = lease.id in move_in_leases
        lease_data.has_move_out_inspection = lease.id in move_out_leases
        leases.append(lease_data)

    return LeaseListResponse(leases=leases, total=len(leases))


@router.get("/{lease_id}", response_model=LeaseResponse)
async def get_lease(
    lease_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_org_member),
):
    """Get a lease by ID."""
    result = await db.execute(
        select(Lease)
        .join(Unit)
        .join(Property)
        .where(
            Lease.id == lease_id,
            Property.org_id == current_user.org_id,
        )
    )
    lease = result.scalar_one_or_none()

    if not lease:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lease not found")

    return LeaseResponse.model_validate(lease)


@router.patch("/{lease_id}", response_model=LeaseResponse)
async def update_lease(
    lease_id: UUID,
    data: LeaseUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_org_member),
):
    """Update a lease (limited fields)."""
    result = await db.execute(
        select(Lease)
        .join(Unit)
        .join(Property)
        .where(
            Lease.id == lease_id,
            Property.org_id == current_user.org_id,
        )
    )
    lease = result.scalar_one_or_none()

    if not lease:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lease not found")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(lease, field, value)

    await db.commit()
    await db.refresh(lease)

    return LeaseResponse.model_validate(lease)


@router.post("/{lease_id}/invite", response_model=LeaseInviteResponse)
async def send_tenant_invite(
    lease_id: UUID,
    data: LeaseInviteRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_org_member),
):
    """Send tenant magic link invite. Lease status -> pending."""
    import secrets
    import hashlib

    result = await db.execute(
        select(Lease)
        .join(Unit)
        .join(Property)
        .where(
            Lease.id == lease_id,
            Property.org_id == current_user.org_id,
        )
    )
    lease = result.scalar_one_or_none()

    if not lease:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lease not found")

    if lease.status not in ("draft", "pending"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot send invite for lease in this status",
        )

    # Generate token
    from datetime import timedelta
    token = secrets.token_urlsafe(48)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    expires_at = datetime.utcnow() + timedelta(hours=24)

    lease.invite_token_hash = token_hash
    lease.invite_expires_at = expires_at
    lease.invite_sent_at = datetime.utcnow()
    lease.status = "pending"

    # Audit log
    audit = AuditService(db)
    await audit.log_invite_sent(
        lease_id=lease_id,
        org_id=current_user.org_id,
        user_id=current_user.db_user_id,
        tenant_email=lease.tenant_email,
        ip_address=request.client.host if request.client else None,
    )

    await db.commit()

    return LeaseInviteResponse(
        lease_id=lease.id,
        tenant_email=lease.tenant_email,
        invite_sent_at=lease.invite_sent_at,
    )


@router.post("/{lease_id}/renew", response_model=LeaseRenewalResponse)
async def renew_lease(
    lease_id: UUID,
    data: LeaseRenewalRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_org_member),
):
    """Initiate lease renewal.
    
    Creates a new lease starting from the old lease's end date.
    The original lease remains unchanged (for historical record).
    
    Flow:
    1. Validate original lease is active and not already renewed
    2. Create new lease with updated terms
    3. Link new lease to original (via notes for now)
    4. Return both lease IDs
    """
    # Get original lease with property context
    result = await db.execute(
        select(Lease, Unit, Property)
        .join(Unit, Lease.unit_id == Unit.id)
        .join(Property, Unit.property_id == Property.id)
        .where(
            Lease.id == lease_id,
            Property.org_id == current_user.org_id,
        )
    )
    row = result.one_or_none()

    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lease not found")

    original_lease, unit, prop = row

    # Validate lease can be renewed
    if original_lease.status != "active":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot renew lease with status '{original_lease.status}'. Only active leases can be renewed.",
        )

    # Check new end date is after original end date
    if data.new_end_date <= original_lease.end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New end date must be after current lease end date",
        )

    # Calculate rent change
    old_rent = original_lease.rent_amount_cents or 0
    new_rent = data.new_rent_amount_cents
    rent_change = new_rent - old_rent
    rent_change_pct = round((rent_change / max(old_rent, 1)) * 100, 2)

    # Create renewal lease
    renewal_notes = f"Renewal of lease {lease_id}"
    if data.notes:
        renewal_notes += f"\n{data.notes}"

    new_lease = Lease(
        unit_id=original_lease.unit_id,
        lease_type=original_lease.lease_type,
        start_date=original_lease.end_date,  # New lease starts when old ends
        end_date=data.new_end_date,
        rent_amount_cents=data.new_rent_amount_cents,
        deposit_amount_cents=data.new_deposit_amount_cents or original_lease.deposit_amount_cents,
        pro_rata_share_bps=original_lease.pro_rata_share_bps,
        cam_budget_cents=data.new_cam_budget_cents or original_lease.cam_budget_cents,
        tenant_email=original_lease.tenant_email,
        tenant_name=original_lease.tenant_name,
        tenant_phone=original_lease.tenant_phone,
        notes=renewal_notes,
        status="draft",  # Renewal starts as draft, needs tenant acceptance
    )
    db.add(new_lease)

    # Audit log
    audit = AuditService(db)
    await audit.log(
        action="LEASE_RENEWED",
        org_id=current_user.org_id,
        user_id=current_user.db_user_id,
        resource_type="lease",
        resource_id=str(lease_id),
        details={
            "original_lease_id": str(lease_id),
            "new_end_date": data.new_end_date.isoformat(),
            "old_rent_cents": old_rent,
            "new_rent_cents": new_rent,
            "rent_change_pct": rent_change_pct,
        },
        ip_address=request.client.host if request.client else None,
    )

    await db.commit()
    await db.refresh(new_lease)

    return LeaseRenewalResponse(
        original_lease_id=original_lease.id,
        renewed_lease_id=new_lease.id,
        new_start_date=new_lease.start_date,
        new_end_date=new_lease.end_date,
        new_rent_amount_cents=new_lease.rent_amount_cents,
        rent_change_cents=rent_change,
        rent_change_pct=rent_change_pct,
    )


@router.post("/{lease_id}/terminate")
async def terminate_lease(
    lease_id: UUID,
    request: Request,
    early_termination: bool = False,
    termination_date: datetime = None,
    reason: str = None,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_org_member),
):
    """Terminate a lease.
    
    Marks the lease as terminated. For active leases, this triggers
    the move-out inspection workflow.
    """
    result = await db.execute(
        select(Lease)
        .join(Unit)
        .join(Property)
        .where(
            Lease.id == lease_id,
            Property.org_id == current_user.org_id,
        )
    )
    lease = result.scalar_one_or_none()

    if not lease:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lease not found")

    if lease.status == "terminated":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Lease is already terminated",
        )

    lease.status = "terminated"
    
    # Audit log
    audit = AuditService(db)
    await audit.log(
        action="LEASE_TERMINATED",
        org_id=current_user.org_id,
        user_id=current_user.db_user_id,
        resource_type="lease",
        resource_id=str(lease_id),
        details={
            "early_termination": early_termination,
            "termination_date": termination_date.isoformat() if termination_date else None,
            "reason": reason,
        },
        ip_address=request.client.host if request.client else None,
    )

    await db.commit()

    return {
        "lease_id": str(lease.id),
        "status": "terminated",
        "early_termination": early_termination,
        "message": "Lease terminated successfully. Move-out inspection should be scheduled.",
    }
