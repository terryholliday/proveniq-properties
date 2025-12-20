"""Properties and Units router."""

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import require_org_member, AuthenticatedUser
from app.models.property import Property, Unit
from app.models.enums import PropertyType
from app.schemas.property import (
    PropertyCreate,
    PropertyUpdate,
    PropertyResponse,
    UnitCreate,
    UnitUpdate,
    UnitResponse,
)

router = APIRouter(prefix="/properties", tags=["properties"])


@router.post("", response_model=PropertyResponse, status_code=status.HTTP_201_CREATED)
async def create_property(
    data: PropertyCreate,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_org_member),
):
    """Create a new property (org-scoped)."""
    prop = Property(
        org_id=current_user.org_id,
        name=data.name,
        property_type=data.property_type,
        address_line1=data.address_line1,
        address_line2=data.address_line2,
        city=data.city,
        state=data.state,
        zip_code=data.zip_code,
        country=data.country,
        total_leasable_sq_ft=data.total_leasable_sq_ft,
        year_built=data.year_built,
        description=data.description,
    )
    db.add(prop)
    await db.commit()
    await db.refresh(prop)

    return PropertyResponse(
        **prop.__dict__,
        unit_count=0,
    )


@router.get("", response_model=List[PropertyResponse])
async def list_properties(
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_org_member),
):
    """List all properties for the organization."""
    result = await db.execute(
        select(Property, func.count(Unit.id).label("unit_count"))
        .outerjoin(Unit, Property.id == Unit.property_id)
        .where(Property.org_id == current_user.org_id)
        .group_by(Property.id)
        .order_by(Property.name)
    )
    rows = result.all()

    return [
        PropertyResponse(
            **row[0].__dict__,
            unit_count=row[1],
        )
        for row in rows
    ]


@router.get("/{property_id}", response_model=PropertyResponse)
async def get_property(
    property_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_org_member),
):
    """Get a property by ID."""
    result = await db.execute(
        select(Property, func.count(Unit.id).label("unit_count"))
        .outerjoin(Unit, Property.id == Unit.property_id)
        .where(Property.id == property_id, Property.org_id == current_user.org_id)
        .group_by(Property.id)
    )
    row = result.one_or_none()

    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")

    return PropertyResponse(
        **row[0].__dict__,
        unit_count=row[1],
    )


@router.patch("/{property_id}", response_model=PropertyResponse)
async def update_property(
    property_id: UUID,
    data: PropertyUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_org_member),
):
    """Update a property."""
    result = await db.execute(
        select(Property).where(
            Property.id == property_id,
            Property.org_id == current_user.org_id,
        )
    )
    prop = result.scalar_one_or_none()

    if not prop:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(prop, field, value)

    await db.commit()
    await db.refresh(prop)

    # Get unit count
    count_result = await db.execute(
        select(func.count(Unit.id)).where(Unit.property_id == property_id)
    )
    unit_count = count_result.scalar() or 0

    return PropertyResponse(
        **prop.__dict__,
        unit_count=unit_count,
    )


# --- Units ---

@router.post("/{property_id}/units", response_model=UnitResponse, status_code=status.HTTP_201_CREATED)
async def create_unit(
    property_id: UUID,
    data: UnitCreate,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_org_member),
):
    """Create a unit within a property.
    
    Service-layer enforcement: commercial/mixed units REQUIRE sq_ft.
    """
    # Get property
    result = await db.execute(
        select(Property).where(
            Property.id == property_id,
            Property.org_id == current_user.org_id,
        )
    )
    prop = result.scalar_one_or_none()

    if not prop:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")

    # Commercial correctness: commercial units REQUIRE sq_ft
    if prop.property_type in (PropertyType.COMMERCIAL, PropertyType.MIXED):
        if not data.sq_ft:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="sq_ft is required for commercial/mixed property units",
            )

    unit = Unit(
        property_id=property_id,
        unit_number=data.unit_number,
        status=data.status,
        bedrooms=data.bedrooms,
        bathrooms=data.bathrooms,
        sq_ft=data.sq_ft,
        description=data.description,
    )
    db.add(unit)
    await db.commit()
    await db.refresh(unit)

    return UnitResponse.model_validate(unit)


@router.get("/{property_id}/units", response_model=List[UnitResponse])
async def list_units(
    property_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_org_member),
):
    """List all units for a property."""
    # Verify property belongs to org
    prop_result = await db.execute(
        select(Property).where(
            Property.id == property_id,
            Property.org_id == current_user.org_id,
        )
    )
    if not prop_result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")

    result = await db.execute(
        select(Unit)
        .where(Unit.property_id == property_id)
        .order_by(Unit.unit_number)
    )
    units = result.scalars().all()

    return [UnitResponse.model_validate(u) for u in units]


@router.get("/{property_id}/units/{unit_id}", response_model=UnitResponse)
async def get_unit(
    property_id: UUID,
    unit_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_org_member),
):
    """Get a unit by ID."""
    result = await db.execute(
        select(Unit)
        .join(Property)
        .where(
            Unit.id == unit_id,
            Unit.property_id == property_id,
            Property.org_id == current_user.org_id,
        )
    )
    unit = result.scalar_one_or_none()

    if not unit:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unit not found")

    return UnitResponse.model_validate(unit)


@router.patch("/{property_id}/units/{unit_id}", response_model=UnitResponse)
async def update_unit(
    property_id: UUID,
    unit_id: UUID,
    data: UnitUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_org_member),
):
    """Update a unit."""
    result = await db.execute(
        select(Unit)
        .join(Property)
        .where(
            Unit.id == unit_id,
            Unit.property_id == property_id,
            Property.org_id == current_user.org_id,
        )
    )
    unit = result.scalar_one_or_none()

    if not unit:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unit not found")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(unit, field, value)

    await db.commit()
    await db.refresh(unit)

    return UnitResponse.model_validate(unit)
