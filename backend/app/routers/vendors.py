"""Vendors router."""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import require_org_member, AuthenticatedUser
from app.models.vendor import Vendor
from app.models.enums import VendorSpecialty
from app.schemas.vendor import VendorCreate, VendorUpdate, VendorResponse

router = APIRouter(prefix="/vendors", tags=["vendors"])


@router.post("", response_model=VendorResponse, status_code=status.HTTP_201_CREATED)
async def create_vendor(
    data: VendorCreate,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_org_member),
):
    """Create a new vendor (org-scoped)."""
    vendor = Vendor(
        org_id=current_user.org_id,
        name=data.name,
        specialty=data.specialty,
        contact_name=data.contact_name,
        email=data.email,
        phone=data.phone,
        address=data.address,
        is_preferred=data.is_preferred,
        notes=data.notes,
    )
    db.add(vendor)
    await db.commit()
    await db.refresh(vendor)

    return VendorResponse.model_validate(vendor)


@router.get("", response_model=List[VendorResponse])
async def list_vendors(
    specialty: Optional[VendorSpecialty] = None,
    is_active: Optional[bool] = None,
    is_preferred: Optional[bool] = None,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_org_member),
):
    """List vendors for the organization."""
    query = select(Vendor).where(Vendor.org_id == current_user.org_id)

    if specialty:
        query = query.where(Vendor.specialty == specialty)
    if is_active is not None:
        query = query.where(Vendor.is_active == is_active)
    if is_preferred is not None:
        query = query.where(Vendor.is_preferred == is_preferred)

    query = query.order_by(Vendor.is_preferred.desc(), Vendor.name)

    result = await db.execute(query)
    vendors = result.scalars().all()

    return [VendorResponse.model_validate(v) for v in vendors]


@router.get("/{vendor_id}", response_model=VendorResponse)
async def get_vendor(
    vendor_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_org_member),
):
    """Get a vendor by ID."""
    result = await db.execute(
        select(Vendor).where(
            Vendor.id == vendor_id,
            Vendor.org_id == current_user.org_id,
        )
    )
    vendor = result.scalar_one_or_none()

    if not vendor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vendor not found")

    return VendorResponse.model_validate(vendor)


@router.patch("/{vendor_id}", response_model=VendorResponse)
async def update_vendor(
    vendor_id: UUID,
    data: VendorUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_org_member),
):
    """Update a vendor."""
    result = await db.execute(
        select(Vendor).where(
            Vendor.id == vendor_id,
            Vendor.org_id == current_user.org_id,
        )
    )
    vendor = result.scalar_one_or_none()

    if not vendor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vendor not found")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(vendor, field, value)

    await db.commit()
    await db.refresh(vendor)

    return VendorResponse.model_validate(vendor)


@router.delete("/{vendor_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_vendor(
    vendor_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_org_member),
):
    """Delete a vendor (soft delete by setting is_active=False)."""
    result = await db.execute(
        select(Vendor).where(
            Vendor.id == vendor_id,
            Vendor.org_id == current_user.org_id,
        )
    )
    vendor = result.scalar_one_or_none()

    if not vendor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vendor not found")

    vendor.is_active = False
    await db.commit()
