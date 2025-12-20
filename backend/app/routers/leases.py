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
    LeaseInviteRequest,
    LeaseInviteResponse,
)
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


@router.get("", response_model=List[LeaseResponse])
async def list_leases(
    unit_id: UUID = None,
    status: str = None,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_org_member),
):
    """List leases (org-scoped)."""
    query = (
        select(Lease)
        .join(Unit)
        .join(Property)
        .where(Property.org_id == current_user.org_id)
    )

    if unit_id:
        query = query.where(Lease.unit_id == unit_id)
    if status:
        query = query.where(Lease.status == status)

    query = query.order_by(Lease.created_at.desc())

    result = await db.execute(query)
    leases = result.scalars().all()

    return [LeaseResponse.model_validate(l) for l in leases]


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
