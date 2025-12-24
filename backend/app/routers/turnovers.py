"""Turnovers router - STR cleaning/turnover workflow."""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.security import get_current_user, require_org_member, require_org_admin, AuthenticatedUser
from app.models.turnover import Turnover, TurnoverPhoto, TurnoverInventory
from app.models.property import Property, Unit
from app.models.booking import Booking
from app.models.org import OrgMembership
from app.models.enums import (
    TurnoverStatus, TurnoverPhotoType, OrgRole, BookingStatus
)
from app.services.storage import get_storage_service
from app.services.audit import AuditService

router = APIRouter(prefix="/turnovers", tags=["turnovers"])


# === Schemas ===

class TurnoverCreate(BaseModel):
    unit_id: UUID
    scheduled_date: datetime
    due_by: Optional[datetime] = None
    checkout_booking_id: Optional[UUID] = None
    checkin_booking_id: Optional[UUID] = None
    assigned_cleaner_id: Optional[UUID] = None


class TurnoverUpdate(BaseModel):
    scheduled_date: Optional[datetime] = None
    due_by: Optional[datetime] = None
    assigned_cleaner_id: Optional[UUID] = None
    cleaner_notes: Optional[str] = None
    host_notes: Optional[str] = None
    has_damage: Optional[bool] = None
    needs_restock: Optional[bool] = None


class TurnoverPhotoResponse(BaseModel):
    id: UUID
    photo_type: TurnoverPhotoType
    object_path: str
    file_hash: str
    notes: Optional[str]
    is_flagged: bool
    uploaded_at: datetime

    class Config:
        from_attributes = True


class TurnoverInventoryCreate(BaseModel):
    item_name: str
    location: str = ""
    expected_quantity: int = 0
    actual_quantity: int = 0
    notes: Optional[str] = None


class TurnoverInventoryResponse(BaseModel):
    id: UUID
    item_name: str
    location: str
    expected_quantity: int
    actual_quantity: int
    is_missing: bool
    is_damaged: bool
    notes: Optional[str]

    class Config:
        from_attributes = True


class TurnoverResponse(BaseModel):
    id: UUID
    unit_id: UUID
    checkout_booking_id: Optional[UUID]
    checkin_booking_id: Optional[UUID]
    assigned_cleaner_id: Optional[UUID]
    scheduled_date: datetime
    due_by: Optional[datetime]
    status: TurnoverStatus
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    verified_at: Optional[datetime]
    cleaner_notes: Optional[str]
    host_notes: Optional[str]
    has_damage: bool
    needs_restock: bool
    photos: List[TurnoverPhotoResponse] = []
    inventory_checks: List[TurnoverInventoryResponse] = []
    photos_complete: bool = False

    class Config:
        from_attributes = True


class PhotoPresignRequest(BaseModel):
    photo_type: TurnoverPhotoType
    mime_type: str = "image/jpeg"
    file_size_bytes: int


class PhotoPresignResponse(BaseModel):
    upload_url: str
    object_path: str
    photo_type: TurnoverPhotoType


class PhotoConfirmRequest(BaseModel):
    object_path: str
    photo_type: TurnoverPhotoType
    file_hash: str
    file_size_bytes: int
    notes: Optional[str] = None


# === Helper Functions ===

MANDATORY_PHOTOS = {
    TurnoverPhotoType.BED,
    TurnoverPhotoType.KITCHEN,
    TurnoverPhotoType.BATHROOM,
    TurnoverPhotoType.TOWELS,
    TurnoverPhotoType.KEYS,
}


async def get_turnover_with_auth(
    turnover_id: UUID,
    db: AsyncSession,
    current_user: AuthenticatedUser,
) -> Turnover:
    """Get turnover with authorization check."""
    result = await db.execute(
        select(Turnover)
        .options(
            selectinload(Turnover.photos),
            selectinload(Turnover.inventory_checks),
        )
        .where(Turnover.id == turnover_id)
    )
    turnover = result.scalar_one_or_none()

    if not turnover:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Turnover not found")

    # Verify access through unit -> property -> org
    unit_result = await db.execute(
        select(Unit)
        .join(Property)
        .where(
            Unit.id == turnover.unit_id,
            Property.org_id == current_user.org_id,
        )
    )
    if not unit_result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    return turnover


def check_photos_complete(photos: List[TurnoverPhoto]) -> bool:
    """Check if all mandatory photos have been uploaded."""
    uploaded_types = {p.photo_type for p in photos}
    return MANDATORY_PHOTOS.issubset(uploaded_types)


def is_cleaner_role(org_role: str) -> bool:
    """Check if user has cleaner role (restricted access)."""
    return org_role == OrgRole.ORG_CLEANER.value


async def require_turnover_access(
    turnover: Turnover,
    current_user: AuthenticatedUser,
    allow_cleaner: bool = True,
) -> None:
    """Verify user has access to this turnover.
    
    Cleaners can only access turnovers assigned to them.
    Owners/Admins/Agents can access all org turnovers.
    """
    if is_cleaner_role(current_user.org_role):
        if not allow_cleaner:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cleaners cannot perform this action"
            )
        if turnover.assigned_cleaner_id != current_user.db_user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not assigned to this turnover"
            )


# === Endpoints ===

@router.post("", response_model=TurnoverResponse)
async def create_turnover(
    data: TurnoverCreate,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_org_member),
):
    """Create a new turnover for an STR unit.
    
    Cleaners cannot create turnovers - only owners/admins/agents.
    """
    if is_cleaner_role(current_user.org_role):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cleaners cannot create turnovers"
        )
    # Verify unit belongs to org
    unit_result = await db.execute(
        select(Unit)
        .join(Property)
        .where(
            Unit.id == data.unit_id,
            Property.org_id == current_user.org_id,
        )
    )
    unit = unit_result.scalar_one_or_none()
    if not unit:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unit not found")

    # Verify cleaner if assigned
    if data.assigned_cleaner_id:
        cleaner_result = await db.execute(
            select(OrgMembership).where(
                OrgMembership.org_id == current_user.org_id,
                OrgMembership.user_id == data.assigned_cleaner_id,
                OrgMembership.role == OrgRole.ORG_CLEANER,
            )
        )
        if not cleaner_result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Assigned user is not a cleaner in this organization"
            )

    turnover = Turnover(
        unit_id=data.unit_id,
        scheduled_date=data.scheduled_date,
        due_by=data.due_by,
        checkout_booking_id=data.checkout_booking_id,
        checkin_booking_id=data.checkin_booking_id,
        assigned_cleaner_id=data.assigned_cleaner_id,
        status=TurnoverStatus.PENDING,
    )
    db.add(turnover)
    await db.commit()
    await db.refresh(turnover)

    return TurnoverResponse(
        **{k: v for k, v in turnover.__dict__.items() if not k.startswith('_')},
        photos=[],
        inventory_checks=[],
        photos_complete=False,
    )


@router.get("", response_model=List[TurnoverResponse])
async def list_turnovers(
    unit_id: Optional[UUID] = None,
    status_filter: Optional[TurnoverStatus] = None,
    assigned_to_me: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_org_member),
):
    """List turnovers for the organization."""
    query = (
        select(Turnover)
        .join(Unit)
        .join(Property)
        .options(
            selectinload(Turnover.photos),
            selectinload(Turnover.inventory_checks),
        )
        .where(Property.org_id == current_user.org_id)
        .order_by(Turnover.scheduled_date.desc())
    )

    if unit_id:
        query = query.where(Turnover.unit_id == unit_id)
    if status_filter:
        query = query.where(Turnover.status == status_filter)
    if assigned_to_me and current_user.db_user_id:
        query = query.where(Turnover.assigned_cleaner_id == current_user.db_user_id)

    result = await db.execute(query)
    turnovers = result.scalars().all()

    return [
        TurnoverResponse(
            **{k: v for k, v in t.__dict__.items() if not k.startswith('_')},
            photos=[TurnoverPhotoResponse.model_validate(p) for p in t.photos],
            inventory_checks=[TurnoverInventoryResponse.model_validate(i) for i in t.inventory_checks],
            photos_complete=check_photos_complete(t.photos),
        )
        for t in turnovers
    ]


@router.get("/{turnover_id}", response_model=TurnoverResponse)
async def get_turnover(
    turnover_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_org_member),
):
    """Get a specific turnover.
    
    Cleaners can only view turnovers assigned to them.
    """
    turnover = await get_turnover_with_auth(turnover_id, db, current_user)
    await require_turnover_access(turnover, current_user)

    return TurnoverResponse(
        **{k: v for k, v in turnover.__dict__.items() if not k.startswith('_')},
        photos=[TurnoverPhotoResponse.model_validate(p) for p in turnover.photos],
        inventory_checks=[TurnoverInventoryResponse.model_validate(i) for i in turnover.inventory_checks],
        photos_complete=check_photos_complete(turnover.photos),
    )


@router.patch("/{turnover_id}", response_model=TurnoverResponse)
async def update_turnover(
    turnover_id: UUID,
    data: TurnoverUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_org_member),
):
    """Update a turnover."""
    turnover = await get_turnover_with_auth(turnover_id, db, current_user)

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(turnover, field, value)

    await db.commit()
    await db.refresh(turnover)

    return TurnoverResponse(
        **{k: v for k, v in turnover.__dict__.items() if not k.startswith('_')},
        photos=[TurnoverPhotoResponse.model_validate(p) for p in turnover.photos],
        inventory_checks=[TurnoverInventoryResponse.model_validate(i) for i in turnover.inventory_checks],
        photos_complete=check_photos_complete(turnover.photos),
    )


# === Turnover Workflow ===

@router.post("/{turnover_id}/start", response_model=TurnoverResponse)
async def start_turnover(
    turnover_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_org_member),
):
    """Start a turnover (cleaner arrives on-site).
    
    Cleaners can only start turnovers assigned to them.
    """
    turnover = await get_turnover_with_auth(turnover_id, db, current_user)
    await require_turnover_access(turnover, current_user)

    if turnover.status != TurnoverStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot start turnover in {turnover.status} status"
        )

    turnover.status = TurnoverStatus.IN_PROGRESS
    turnover.started_at = datetime.utcnow()

    await db.commit()
    await db.refresh(turnover)

    return TurnoverResponse(
        **{k: v for k, v in turnover.__dict__.items() if not k.startswith('_')},
        photos=[TurnoverPhotoResponse.model_validate(p) for p in turnover.photos],
        inventory_checks=[TurnoverInventoryResponse.model_validate(i) for i in turnover.inventory_checks],
        photos_complete=check_photos_complete(turnover.photos),
    )


@router.post("/{turnover_id}/complete", response_model=TurnoverResponse)
async def complete_turnover(
    turnover_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_org_member),
):
    """Complete a turnover (all photos submitted).
    
    Cleaners can only complete turnovers assigned to them.
    """
    turnover = await get_turnover_with_auth(turnover_id, db, current_user)
    await require_turnover_access(turnover, current_user)

    if turnover.status != TurnoverStatus.IN_PROGRESS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot complete turnover in {turnover.status} status"
        )

    # Verify all mandatory photos are uploaded
    if not check_photos_complete(turnover.photos):
        missing = MANDATORY_PHOTOS - {p.photo_type for p in turnover.photos}
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Missing mandatory photos: {[p.value for p in missing]}"
        )

    turnover.status = TurnoverStatus.COMPLETED
    turnover.completed_at = datetime.utcnow()

    await db.commit()
    await db.refresh(turnover)

    return TurnoverResponse(
        **{k: v for k, v in turnover.__dict__.items() if not k.startswith('_')},
        photos=[TurnoverPhotoResponse.model_validate(p) for p in turnover.photos],
        inventory_checks=[TurnoverInventoryResponse.model_validate(i) for i in turnover.inventory_checks],
        photos_complete=True,
    )


@router.post("/{turnover_id}/verify", response_model=TurnoverResponse)
async def verify_turnover(
    turnover_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_org_member),
):
    """Verify a turnover (host approves)."""
    turnover = await get_turnover_with_auth(turnover_id, db, current_user)

    # Only owners/admins can verify
    membership_result = await db.execute(
        select(OrgMembership).where(
            OrgMembership.org_id == current_user.org_id,
            OrgMembership.user_id == current_user.db_user_id,
            OrgMembership.role.in_([OrgRole.ORG_OWNER, OrgRole.ORG_ADMIN]),
        )
    )
    if not membership_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only owners and admins can verify turnovers"
        )

    if turnover.status != TurnoverStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot verify turnover in {turnover.status} status"
        )

    turnover.status = TurnoverStatus.VERIFIED
    turnover.verified_at = datetime.utcnow()
    turnover.verified_by_id = current_user.db_user_id

    await db.commit()
    await db.refresh(turnover)

    return TurnoverResponse(
        **{k: v for k, v in turnover.__dict__.items() if not k.startswith('_')},
        photos=[TurnoverPhotoResponse.model_validate(p) for p in turnover.photos],
        inventory_checks=[TurnoverInventoryResponse.model_validate(i) for i in turnover.inventory_checks],
        photos_complete=True,
    )


@router.post("/{turnover_id}/flag", response_model=TurnoverResponse)
async def flag_turnover(
    turnover_id: UUID,
    host_notes: str,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_org_member),
):
    """Flag a turnover for issues."""
    turnover = await get_turnover_with_auth(turnover_id, db, current_user)

    turnover.status = TurnoverStatus.FLAGGED
    turnover.host_notes = host_notes

    await db.commit()
    await db.refresh(turnover)

    return TurnoverResponse(
        **{k: v for k, v in turnover.__dict__.items() if not k.startswith('_')},
        photos=[TurnoverPhotoResponse.model_validate(p) for p in turnover.photos],
        inventory_checks=[TurnoverInventoryResponse.model_validate(i) for i in turnover.inventory_checks],
        photos_complete=check_photos_complete(turnover.photos),
    )


# === Photo Upload ===

@router.post("/{turnover_id}/photos/presign", response_model=PhotoPresignResponse)
async def presign_photo_upload(
    turnover_id: UUID,
    data: PhotoPresignRequest,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_org_member),
):
    """Get presigned URL for photo upload.
    
    Cleaners can only upload photos to turnovers assigned to them.
    """
    turnover = await get_turnover_with_auth(turnover_id, db, current_user)
    await require_turnover_access(turnover, current_user)

    if turnover.status not in (TurnoverStatus.PENDING, TurnoverStatus.IN_PROGRESS):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot upload photos to completed turnover"
        )

    # Check if this photo type already exists
    existing = [p for p in turnover.photos if p.photo_type == data.photo_type]
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Photo type {data.photo_type.value} already uploaded"
        )

    storage = get_storage_service()
    object_path = f"turnovers/{turnover_id}/{data.photo_type.value}.jpg"
    
    upload_url = await storage.get_upload_url(
        object_path=object_path,
        content_type=data.mime_type,
        ttl_seconds=300,
    )

    return PhotoPresignResponse(
        upload_url=upload_url,
        object_path=object_path,
        photo_type=data.photo_type,
    )


@router.post("/{turnover_id}/photos/confirm", response_model=TurnoverPhotoResponse)
async def confirm_photo_upload(
    turnover_id: UUID,
    data: PhotoConfirmRequest,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_org_member),
):
    """Confirm photo upload after successful upload to storage.
    
    Cleaners can only confirm photos for turnovers assigned to them.
    """
    turnover = await get_turnover_with_auth(turnover_id, db, current_user)
    await require_turnover_access(turnover, current_user)

    if turnover.status not in (TurnoverStatus.PENDING, TurnoverStatus.IN_PROGRESS):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot upload photos to completed turnover"
        )

    # Create photo record
    photo = TurnoverPhoto(
        turnover_id=turnover_id,
        photo_type=data.photo_type,
        object_path=data.object_path,
        file_hash=data.file_hash,
        file_size_bytes=data.file_size_bytes,
        notes=data.notes,
        uploaded_by_id=current_user.db_user_id,
    )
    db.add(photo)
    
    # Auto-start turnover if first photo
    if turnover.status == TurnoverStatus.PENDING:
        turnover.status = TurnoverStatus.IN_PROGRESS
        turnover.started_at = datetime.utcnow()

    await db.commit()
    await db.refresh(photo)

    return TurnoverPhotoResponse.model_validate(photo)


# === Inventory ===

@router.post("/{turnover_id}/inventory", response_model=TurnoverInventoryResponse)
async def add_inventory_check(
    turnover_id: UUID,
    data: TurnoverInventoryCreate,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_org_member),
):
    """Add an inventory check to a turnover.
    
    Cleaners can only add inventory checks to turnovers assigned to them.
    """
    turnover = await get_turnover_with_auth(turnover_id, db, current_user)
    await require_turnover_access(turnover, current_user)

    inventory = TurnoverInventory(
        turnover_id=turnover_id,
        item_name=data.item_name,
        location=data.location,
        expected_quantity=data.expected_quantity,
        actual_quantity=data.actual_quantity,
        is_missing=data.actual_quantity < data.expected_quantity,
        is_damaged=False,
        notes=data.notes,
    )
    db.add(inventory)
    await db.commit()
    await db.refresh(inventory)

    return TurnoverInventoryResponse.model_validate(inventory)


@router.get("/cleaners/my-turnovers", response_model=List[TurnoverResponse])
async def get_my_turnovers(
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_org_member),
):
    """Get turnovers assigned to the current user (cleaner view)."""
    if not current_user.db_user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User not found")

    result = await db.execute(
        select(Turnover)
        .options(
            selectinload(Turnover.photos),
            selectinload(Turnover.inventory_checks),
        )
        .where(
            Turnover.assigned_cleaner_id == current_user.db_user_id,
            Turnover.status.in_([TurnoverStatus.PENDING, TurnoverStatus.IN_PROGRESS]),
        )
        .order_by(Turnover.scheduled_date)
    )
    turnovers = result.scalars().all()

    return [
        TurnoverResponse(
            **{k: v for k, v in t.__dict__.items() if not k.startswith('_')},
            photos=[TurnoverPhotoResponse.model_validate(p) for p in t.photos],
            inventory_checks=[TurnoverInventoryResponse.model_validate(i) for i in t.inventory_checks],
            photos_complete=check_photos_complete(t.photos),
        )
        for t in turnovers
    ]
