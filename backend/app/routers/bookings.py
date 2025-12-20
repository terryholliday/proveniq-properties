"""Bookings router for STR (Short-Term Rental) support."""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.security import require_org_member, AuthenticatedUser, compute_content_hash
from app.models.property import Property, Unit
from app.models.lease import Lease
from app.models.booking import Booking
from app.models.inspection import Inspection, InspectionItem, InspectionEvidence
from app.models.enums import (
    BookingStatus, 
    OccupancyModel, 
    InspectionType, 
    InspectionScope, 
    InspectionStatus,
    InspectionSignedBy,
)
from app.schemas.booking import (
    BookingCreate,
    BookingUpdate,
    BookingResponse,
    BookingCheckInRequest,
    BookingCheckOutRequest,
    ClaimPacketRequest,
    ClaimPacketResponse,
)
from app.services.audit import AuditService
from app.services.mason import MasonService

router = APIRouter(prefix="/bookings", tags=["bookings"])


async def get_unit_with_str_check(
    unit_id: UUID,
    db: AsyncSession,
    current_user: AuthenticatedUser,
) -> Unit:
    """Get unit and verify it belongs to an STR property in user's org."""
    result = await db.execute(
        select(Unit)
        .join(Property)
        .where(
            Unit.id == unit_id,
            Property.org_id == current_user.org_id,
        )
    )
    unit = result.scalar_one_or_none()

    if not unit:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unit not found")

    # Verify property is STR
    prop_result = await db.execute(
        select(Property).where(Property.id == unit.property_id)
    )
    prop = prop_result.scalar_one()

    if prop.occupancy_model != OccupancyModel.SHORT_TERM_RENTAL:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bookings are only available for STR properties. Update property occupancy_model first.",
        )

    return unit


@router.post("", response_model=BookingResponse, status_code=status.HTTP_201_CREATED)
async def create_booking(
    data: BookingCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_org_member),
):
    """Create a new STR booking.
    
    On create, auto-generates PRE_STAY inspection draft.
    """
    unit = await get_unit_with_str_check(data.unit_id, db, current_user)

    # Get a lease for this unit (STR units still need a lease for the property)
    # For STR, we use a single "master" lease or create one if needed
    lease_result = await db.execute(
        select(Lease).where(Lease.unit_id == unit.id).limit(1)
    )
    lease = lease_result.scalar_one_or_none()

    if not lease:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unit must have at least one lease configured for STR inspections",
        )

    # Create booking
    booking = Booking(
        unit_id=data.unit_id,
        created_by_id=current_user.db_user_id,
        external_id=data.external_id,
        source=data.source,
        guest_name=data.guest_name,
        guest_count=data.guest_count,
        check_in_date=data.check_in_date,
        check_out_date=data.check_out_date,
        notes=data.notes,
    )
    db.add(booking)
    await db.flush()

    # Auto-create PRE_STAY inspection draft
    pre_stay_inspection = Inspection(
        lease_id=lease.id,
        created_by_id=current_user.db_user_id,
        inspection_type=InspectionType.PRE_STAY,
        scope=InspectionScope.BOOKING,
        booking_id=str(booking.id),
        inspection_date=datetime.combine(data.check_in_date, datetime.min.time()),
        status=InspectionStatus.DRAFT,
    )
    db.add(pre_stay_inspection)

    # Audit log
    audit = AuditService(db)
    await audit.log(
        action="booking_created",
        resource_type="booking",
        resource_id=booking.id,
        org_id=current_user.org_id,
        user_id=current_user.db_user_id,
        details={
            "unit_id": str(data.unit_id),
            "check_in": str(data.check_in_date),
            "check_out": str(data.check_out_date),
        },
        ip_address=request.client.host if request.client else None,
    )

    await db.commit()
    await db.refresh(booking)

    return BookingResponse(
        **booking.__dict__,
        pre_stay_inspection_id=pre_stay_inspection.id,
        post_stay_inspection_id=None,
    )


@router.get("", response_model=List[BookingResponse])
async def list_bookings(
    unit_id: Optional[UUID] = None,
    status_filter: Optional[BookingStatus] = None,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_org_member),
):
    """List bookings for the organization."""
    query = (
        select(Booking)
        .join(Unit)
        .join(Property)
        .where(Property.org_id == current_user.org_id)
    )

    if unit_id:
        query = query.where(Booking.unit_id == unit_id)
    if status_filter:
        query = query.where(Booking.status == status_filter)

    query = query.order_by(Booking.check_in_date.desc())

    result = await db.execute(query)
    bookings = result.scalars().all()

    # Get linked inspections
    responses = []
    for booking in bookings:
        insp_result = await db.execute(
            select(Inspection).where(
                Inspection.booking_id == str(booking.id),
                Inspection.scope == InspectionScope.BOOKING,
            )
        )
        inspections = insp_result.scalars().all()
        
        pre_stay_id = None
        post_stay_id = None
        for insp in inspections:
            if insp.inspection_type == InspectionType.PRE_STAY:
                pre_stay_id = insp.id
            elif insp.inspection_type == InspectionType.POST_STAY:
                post_stay_id = insp.id

        responses.append(BookingResponse(
            **booking.__dict__,
            pre_stay_inspection_id=pre_stay_id,
            post_stay_inspection_id=post_stay_id,
        ))

    return responses


@router.get("/{booking_id}", response_model=BookingResponse)
async def get_booking(
    booking_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_org_member),
):
    """Get a booking by ID."""
    result = await db.execute(
        select(Booking)
        .join(Unit)
        .join(Property)
        .where(
            Booking.id == booking_id,
            Property.org_id == current_user.org_id,
        )
    )
    booking = result.scalar_one_or_none()

    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")

    # Get linked inspections
    insp_result = await db.execute(
        select(Inspection).where(
            Inspection.booking_id == str(booking.id),
            Inspection.scope == InspectionScope.BOOKING,
        )
    )
    inspections = insp_result.scalars().all()
    
    pre_stay_id = None
    post_stay_id = None
    for insp in inspections:
        if insp.inspection_type == InspectionType.PRE_STAY:
            pre_stay_id = insp.id
        elif insp.inspection_type == InspectionType.POST_STAY:
            post_stay_id = insp.id

    return BookingResponse(
        **booking.__dict__,
        pre_stay_inspection_id=pre_stay_id,
        post_stay_inspection_id=post_stay_id,
    )


@router.post("/{booking_id}/check-in", response_model=BookingResponse)
async def check_in_booking(
    booking_id: UUID,
    data: BookingCheckInRequest,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_org_member),
):
    """Mark booking as checked in."""
    result = await db.execute(
        select(Booking)
        .join(Unit)
        .join(Property)
        .where(
            Booking.id == booking_id,
            Property.org_id == current_user.org_id,
        )
    )
    booking = result.scalar_one_or_none()

    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")

    if booking.status != BookingStatus.UPCOMING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Booking is not in UPCOMING status",
        )

    booking.actual_check_in = data.actual_check_in or datetime.utcnow()
    booking.status = BookingStatus.CHECKED_IN

    await db.commit()
    await db.refresh(booking)

    return await get_booking(booking_id, db, current_user)


@router.post("/{booking_id}/check-out", response_model=BookingResponse)
async def check_out_booking(
    booking_id: UUID,
    data: BookingCheckOutRequest,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_org_member),
):
    """Mark booking as checked out and create POST_STAY inspection draft."""
    result = await db.execute(
        select(Booking)
        .join(Unit)
        .join(Property)
        .where(
            Booking.id == booking_id,
            Property.org_id == current_user.org_id,
        )
    )
    booking = result.scalar_one_or_none()

    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")

    if booking.status != BookingStatus.CHECKED_IN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Booking is not in CHECKED_IN status",
        )

    # Get lease for this unit
    unit_result = await db.execute(select(Unit).where(Unit.id == booking.unit_id))
    unit = unit_result.scalar_one()
    
    lease_result = await db.execute(
        select(Lease).where(Lease.unit_id == unit.id).limit(1)
    )
    lease = lease_result.scalar_one()

    booking.actual_check_out = data.actual_check_out or datetime.utcnow()
    booking.status = BookingStatus.CHECKED_OUT

    # Create POST_STAY inspection draft
    post_stay_inspection = Inspection(
        lease_id=lease.id,
        created_by_id=current_user.db_user_id,
        inspection_type=InspectionType.POST_STAY,
        scope=InspectionScope.BOOKING,
        booking_id=str(booking.id),
        inspection_date=booking.actual_check_out,
        status=InspectionStatus.DRAFT,
    )
    db.add(post_stay_inspection)

    await db.commit()

    return await get_booking(booking_id, db, current_user)


@router.get("/{booking_id}/claim-packet", response_model=ClaimPacketResponse)
async def get_claim_packet(
    booking_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_org_member),
):
    """Generate STR platform-ready damage claim packet.
    
    Requires both PRE_STAY and POST_STAY inspections to be SIGNED.
    """
    # Get booking
    result = await db.execute(
        select(Booking)
        .join(Unit)
        .join(Property)
        .where(
            Booking.id == booking_id,
            Property.org_id == current_user.org_id,
        )
    )
    booking = result.scalar_one_or_none()

    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")

    # Get PRE_STAY inspection
    pre_stay_result = await db.execute(
        select(Inspection)
        .options(selectinload(Inspection.items).selectinload(InspectionItem.evidence))
        .where(
            Inspection.booking_id == str(booking.id),
            Inspection.inspection_type == InspectionType.PRE_STAY,
            Inspection.status == InspectionStatus.SIGNED,
        )
    )
    pre_stay = pre_stay_result.scalar_one_or_none()

    if not pre_stay:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No signed PRE_STAY inspection found for this booking",
        )

    # Get POST_STAY inspection
    post_stay_result = await db.execute(
        select(Inspection)
        .options(selectinload(Inspection.items).selectinload(InspectionItem.evidence))
        .where(
            Inspection.booking_id == str(booking.id),
            Inspection.inspection_type == InspectionType.POST_STAY,
            Inspection.status == InspectionStatus.SIGNED,
        )
    )
    post_stay = post_stay_result.scalar_one_or_none()

    if not post_stay:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No signed POST_STAY inspection found for this booking",
        )

    # Build diff
    pre_items = {(i.room_name, i.item_name): i for i in pre_stay.items}
    diff_summary = []
    evidence_hashes = []
    total_estimate = 0

    for item in post_stay.items:
        key = (item.room_name, item.item_name)
        pre_item = pre_items.get(key)

        pre_condition = pre_item.condition_rating if pre_item else None
        post_condition = item.condition_rating
        
        condition_change = 0
        if pre_condition and post_condition:
            condition_change = post_condition - pre_condition

        is_new_damage = item.is_damaged and (not pre_item or not pre_item.is_damaged)

        if condition_change < 0 or is_new_damage:
            diff_summary.append({
                "room_name": item.room_name,
                "item_name": item.item_name,
                "pre_condition": pre_condition,
                "post_condition": post_condition,
                "condition_change": condition_change,
                "is_new_damage": is_new_damage,
                "damage_description": item.damage_description,
                "estimated_repair_cents": item.mason_estimated_repair_cents or 0,
            })
            if item.mason_estimated_repair_cents:
                total_estimate += item.mason_estimated_repair_cents

        # Collect evidence hashes
        for ev in item.evidence:
            if ev.is_confirmed:
                evidence_hashes.append({
                    "item": f"{item.room_name} - {item.item_name}",
                    "file_hash": ev.file_hash,
                    "file_name": ev.file_name,
                    "inspection_type": "post_stay",
                })

    for item in pre_stay.items:
        for ev in item.evidence:
            if ev.is_confirmed:
                evidence_hashes.append({
                    "item": f"{item.room_name} - {item.item_name}",
                    "file_hash": ev.file_hash,
                    "file_name": ev.file_name,
                    "inspection_type": "pre_stay",
                })

    # Generate narrative
    narrative = f"Damage claim for booking {booking.id}.\n\n"
    narrative += f"Guest: {booking.guest_name or 'N/A'}\n"
    narrative += f"Check-in: {booking.check_in_date}\n"
    narrative += f"Check-out: {booking.check_out_date}\n\n"
    narrative += f"Damage summary ({len(diff_summary)} items):\n"
    for item in diff_summary:
        narrative += f"- {item['room_name']} - {item['item_name']}: "
        if item['is_new_damage']:
            narrative += f"NEW DAMAGE - {item['damage_description']}\n"
        else:
            narrative += f"Condition degraded from {item['pre_condition']} to {item['post_condition']}\n"
    narrative += f"\nTotal estimated repair cost: ${total_estimate / 100:.2f}"

    # Audit log
    audit = AuditService(db)
    await audit.log(
        action="claim_packet_generated",
        resource_type="booking",
        resource_id=booking.id,
        org_id=current_user.org_id,
        user_id=current_user.db_user_id,
        details={
            "pre_stay_hash": pre_stay.content_hash,
            "post_stay_hash": post_stay.content_hash,
            "damaged_items": len(diff_summary),
        },
    )

    await db.commit()

    return ClaimPacketResponse(
        booking_id=booking.id,
        unit_id=booking.unit_id,
        guest_name=booking.guest_name,
        check_in_date=booking.check_in_date,
        check_out_date=booking.check_out_date,
        pre_stay_inspection_id=pre_stay.id,
        pre_stay_content_hash=pre_stay.content_hash,
        pre_stay_signed_at=pre_stay.signed_at,
        post_stay_inspection_id=post_stay.id,
        post_stay_content_hash=post_stay.content_hash,
        post_stay_signed_at=post_stay.signed_at,
        diff_summary=diff_summary,
        total_items=len(post_stay.items),
        damaged_items=len(diff_summary),
        total_estimated_repair_cents=total_estimate,
        evidence_hash_list=evidence_hashes,
        narrative=narrative,
        generated_at=datetime.utcnow(),
    )
