"""Inspections router - Core evidence pipeline."""

from datetime import datetime
from typing import List, Optional
from uuid import UUID
import uuid
import io

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

from app.core.database import get_db
from app.core.security import get_current_user, require_org_member, AuthenticatedUser, compute_content_hash
from app.models.property import Property, Unit
from app.models.lease import Lease, TenantAccess
from app.models.inspection import Inspection, InspectionItem, InspectionEvidence
from app.models.enums import (
    InspectionStatus, InspectionType, EvidenceType, InspectionScope, InspectionSignedBy,
    EvidenceSource, StorageInstanceKind,
)
from app.schemas.inspection import (
    InspectionCreate,
    InspectionUpdate,
    InspectionResponse,
    InspectionItemCreate,
    InspectionItemResponse,
    EvidencePresignRequest,
    EvidencePresignResponse,
    EvidenceConfirmRequest,
    EvidenceResponse,
    InspectionSubmitResponse,
    InspectionSignRequest,
    InspectionSignResponse,
    InspectionDiffResponse,
    InspectionDiffItem,
    MasonEstimateResponse,
    InspectionAttestRequest,
    InspectionAttestResponse,
)
from app.services.storage import get_storage_service
from app.services.audit import AuditService
from app.services.mason import MasonService
from app.services.canonical import compute_canonical_hash
from app.services.jobs import JobsService
from app.services.claim_packet import ClaimPacketService
from app.core.core_client import get_core_client

router = APIRouter(prefix="/inspections", tags=["inspections"])


async def get_inspection_with_auth(
    inspection_id: UUID,
    db: AsyncSession,
    current_user: AuthenticatedUser,
    require_draft: bool = False,
) -> Inspection:
    """Get inspection with authorization check."""
    result = await db.execute(
        select(Inspection)
        .options(selectinload(Inspection.items).selectinload(InspectionItem.evidence))
        .where(Inspection.id == inspection_id)
    )
    inspection = result.scalar_one_or_none()

    if not inspection:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Inspection not found")

    # Check authorization
    if current_user.org_id:
        # Org member - verify through property chain
        lease_result = await db.execute(
            select(Lease)
            .join(Unit)
            .join(Property)
            .where(
                Lease.id == inspection.lease_id,
                Property.org_id == current_user.org_id,
            )
        )
        if not lease_result.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    else:
        # Tenant - verify through tenant_access
        if not current_user.db_user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        
        access_result = await db.execute(
            select(TenantAccess).where(
                TenantAccess.lease_id == inspection.lease_id,
                TenantAccess.user_id == current_user.db_user_id,
            )
        )
        if not access_result.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    if require_draft and inspection.status != InspectionStatus.DRAFT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inspection is not in draft status",
        )

    return inspection


@router.post("", response_model=InspectionResponse, status_code=status.HTTP_201_CREATED)
async def create_inspection(
    data: InspectionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """Create a new inspection (draft status)."""
    # Verify lease access
    if current_user.org_id:
        result = await db.execute(
            select(Lease)
            .join(Unit)
            .join(Property)
            .where(
                Lease.id == data.lease_id,
                Property.org_id == current_user.org_id,
            )
        )
    else:
        result = await db.execute(
            select(Lease)
            .join(TenantAccess)
            .where(
                Lease.id == data.lease_id,
                TenantAccess.user_id == current_user.db_user_id,
            )
        )

    lease = result.scalar_one_or_none()
    if not lease:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lease not found")

    inspection = Inspection(
        lease_id=data.lease_id,
        created_by_id=current_user.db_user_id,
        inspection_type=data.inspection_type,
        inspection_date=data.inspection_date,
        notes=data.notes,
    )
    db.add(inspection)
    await db.commit()
    await db.refresh(inspection)

    return InspectionResponse(
        **inspection.__dict__,
        item_count=0,
    )


@router.get("", response_model=List[InspectionResponse])
async def list_inspections(
    lease_id: Optional[UUID] = None,
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """List inspections (scoped by org or tenant access)."""
    if current_user.org_id:
        query = (
            select(Inspection)
            .join(Lease)
            .join(Unit)
            .join(Property)
            .where(Property.org_id == current_user.org_id)
        )
    else:
        query = (
            select(Inspection)
            .join(Lease)
            .join(TenantAccess)
            .where(TenantAccess.user_id == current_user.db_user_id)
        )

    if lease_id:
        query = query.where(Inspection.lease_id == lease_id)
    if status:
        query = query.where(Inspection.status == status)

    query = query.order_by(Inspection.created_at.desc())

    result = await db.execute(query)
    inspections = result.scalars().all()

    return [
        InspectionResponse(
            **i.__dict__,
            item_count=len(i.items) if hasattr(i, 'items') else 0,
        )
        for i in inspections
    ]


@router.get("/{inspection_id}", response_model=InspectionResponse)
async def get_inspection(
    inspection_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """Get inspection by ID."""
    inspection = await get_inspection_with_auth(inspection_id, db, current_user)

    return InspectionResponse(
        **inspection.__dict__,
        item_count=len(inspection.items),
    )


@router.post("/{inspection_id}/items", response_model=InspectionItemResponse)
async def upsert_inspection_item(
    inspection_id: UUID,
    data: InspectionItemCreate,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """Create or update an inspection item (draft only)."""
    inspection = await get_inspection_with_auth(inspection_id, db, current_user, require_draft=True)

    # Check if item exists
    result = await db.execute(
        select(InspectionItem).where(
            InspectionItem.inspection_id == inspection_id,
            InspectionItem.room_name == data.room_name,
            InspectionItem.item_name == data.item_name,
        )
    )
    item = result.scalar_one_or_none()

    if item:
        # Update existing
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(item, field, value)
    else:
        # Create new
        item = InspectionItem(
            inspection_id=inspection_id,
            **data.model_dump(),
        )
        db.add(item)

        # P0: Register fixture with Core to get PAID
        if current_user.org_id:
            try:
                core_client = get_core_client()
                # Get property/unit info from inspection
                lease_result = await db.execute(
                    select(Lease).options(selectinload(Lease.unit)).where(Lease.id == inspection.lease_id)
                )
                lease = lease_result.scalar_one_or_none()
                if lease and lease.unit:
                    registration = await core_client.register_fixture(
                        landlord_id=str(current_user.org_id),
                        fixture_name=data.item_name,
                        category=data.room_name,  # Use room as category proxy
                        unit_id=str(lease.unit_id),
                        property_id=str(lease.unit.property_id),
                        condition=data.condition or "good",
                    )
                    if registration and registration.get("paid"):
                        item.paid = registration["paid"]
                        print(f"[Core] Fixture registered with PAID: {registration['paid']}")
                        
                        # P0: Get fixture valuation from Core
                        valuation = await core_client.get_fixture_valuation(
                            paid=registration["paid"],
                            category=data.room_name,
                            condition=data.condition or "good",
                        )
                        if valuation:
                            item.estimated_value = valuation.get("estimated_value")
                            print(f"[Core] Fixture valued at: ${valuation.get('estimated_value')}")
            except Exception as e:
                print(f"[Core] Fixture registration unavailable: {e}")

    await db.commit()
    await db.refresh(item)

    # Get evidence count
    evidence_result = await db.execute(
        select(InspectionEvidence).where(
            InspectionEvidence.item_id == item.id,
            InspectionEvidence.is_confirmed == True,
        )
    )
    evidence_count = len(evidence_result.scalars().all())

    return InspectionItemResponse(
        **item.__dict__,
        evidence_count=evidence_count,
    )


@router.get("/{inspection_id}/items", response_model=List[InspectionItemResponse])
async def list_inspection_items(
    inspection_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """List all items for an inspection."""
    inspection = await get_inspection_with_auth(inspection_id, db, current_user)

    # Privacy: landlords cannot view tenant draft evidence
    is_org_member = current_user.org_id is not None
    is_draft = inspection.status == InspectionStatus.DRAFT

    items = []
    for item in inspection.items:
        evidence_count = 0
        if not (is_org_member and is_draft):
            # Can see evidence
            evidence_count = len([e for e in item.evidence if e.is_confirmed])
        
        items.append(InspectionItemResponse(
            **item.__dict__,
            evidence_count=evidence_count,
        ))

    return items


@router.post("/{inspection_id}/evidence/presign", response_model=EvidencePresignResponse)
async def presign_evidence_upload(
    inspection_id: UUID,
    data: EvidencePresignRequest,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """Get presigned URL for evidence upload (Golden Master v2.3.1).
    
    MUST bind exact Content-Type and size. Returns evidence_id for confirm.
    """
    inspection = await get_inspection_with_auth(inspection_id, db, current_user, require_draft=True)

    # Verify item exists and belongs to this inspection
    result = await db.execute(
        select(InspectionItem).where(
            InspectionItem.id == data.inspection_item_id,
            InspectionItem.inspection_id == inspection_id,
        )
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")

    # Get org_id for storage path
    lease_result = await db.execute(
        select(Lease).join(Unit).join(Property).where(Lease.id == inspection.lease_id)
    )
    lease = lease_result.scalar_one()
    
    prop_result = await db.execute(
        select(Property).join(Unit).where(Unit.id == lease.unit_id)
    )
    prop = prop_result.scalar_one()

    storage = get_storage_service()
    evidence_id = uuid.uuid4()
    
    try:
        upload_url, object_path, expires_at = await storage.create_presigned_upload(
            org_id=prop.org_id,
            inspection_id=inspection_id,
            item_id=data.inspection_item_id,
            file_name=f"{evidence_id}",
            mime_type=data.mime_type,
            file_size_bytes=data.size_bytes,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return EvidencePresignResponse(
        evidence_id=evidence_id,
        upload_url=upload_url,
        object_path=object_path,
        expires_at=expires_at,
        bound_mime_type=data.mime_type,
        bound_size_bytes=data.size_bytes,
    )


@router.post("/{inspection_id}/evidence/confirm", response_model=EvidenceResponse)
async def confirm_evidence_upload(
    inspection_id: UUID,
    data: EvidenceConfirmRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """Confirm evidence upload (Golden Master v2.3.1).
    
    IDEMPOTENT: Uses confirm_idempotency_key for de-duplication.
    Server performs HEAD check and records storage_instance_id.
    SHA-256 verification queued via jobs_outbox (async).
    """
    inspection = await get_inspection_with_auth(inspection_id, db, current_user, require_draft=True)

    # Verify item exists
    result = await db.execute(
        select(InspectionItem).where(
            InspectionItem.id == data.inspection_item_id,
            InspectionItem.inspection_id == inspection_id,
        )
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")

    # Idempotency check - return existing evidence if already confirmed
    existing = await db.execute(
        select(InspectionEvidence).where(
            InspectionEvidence.inspection_item_id == data.inspection_item_id,
            InspectionEvidence.confirm_idempotency_key == data.confirm_idempotency_key,
        )
    )
    existing_evidence = existing.scalar_one_or_none()
    if existing_evidence:
        # Idempotent return - same request already processed
        return EvidenceResponse(
            id=existing_evidence.id,
            inspection_item_id=existing_evidence.inspection_item_id,
            object_path=existing_evidence.object_path,
            mime_type=existing_evidence.mime_type,
            size_bytes=existing_evidence.size_bytes,
            file_sha256_claimed=existing_evidence.file_sha256_claimed,
            file_sha256_verified=existing_evidence.file_sha256_verified,
            confirmed_at=existing_evidence.confirmed_at,
            evidence_source=existing_evidence.evidence_source,
            storage_instance_kind=existing_evidence.storage_instance_kind,
            storage_instance_id=existing_evidence.storage_instance_id,
            confirm_idempotency_key=existing_evidence.confirm_idempotency_key,
            created_at=existing_evidence.created_at,
        )

    # Server-side HEAD check against storage provider
    storage = get_storage_service()
    head_result = await storage.head_object(data.object_path)
    if not head_result:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File not found in storage. Upload may have failed.",
        )
    
    # Extract storage instance ID (GCS generation or S3 ETag)
    storage_instance_kind = StorageInstanceKind.GCS_GENERATION
    storage_instance_id = head_result.get("generation", head_result.get("etag", "unknown"))
    if "etag" in head_result and "generation" not in head_result:
        storage_instance_kind = StorageInstanceKind.S3_ETAG

    # Determine evidence source
    evidence_source = EvidenceSource.TENANT
    if current_user.org_id:
        evidence_source = EvidenceSource.LANDLORD

    now = datetime.utcnow()
    evidence = InspectionEvidence(
        inspection_item_id=data.inspection_item_id,
        object_path=data.object_path,
        mime_type=data.mime_type,
        size_bytes=data.size_bytes,
        file_sha256_claimed=data.file_sha256_claimed,
        file_sha256_verified=None,  # Async verification via jobs_outbox
        confirmed_at=now,
        evidence_source=evidence_source,
        storage_instance_kind=storage_instance_kind,
        storage_instance_id=storage_instance_id,
        confirm_idempotency_key=data.confirm_idempotency_key,
    )
    db.add(evidence)
    await db.flush()  # Get evidence.id

    # Enqueue async SHA-256 verification via jobs_outbox
    jobs = JobsService(db)
    await jobs.enqueue_verify_hash(
        evidence_id=evidence.id,
        object_path=data.object_path,
        claimed_hash=data.file_sha256_claimed,
    )

    # Audit log
    audit = AuditService(db)
    await audit.log_evidence_confirmed(
        evidence_id=evidence.id,
        inspection_id=inspection_id,
        user_id=current_user.db_user_id,
        file_hash=data.file_sha256_claimed,
        ip_address=request.client.host if request.client else None,
    )

    await db.commit()

    return EvidenceResponse(
        id=evidence.id,
        inspection_item_id=evidence.inspection_item_id,
        object_path=evidence.object_path,
        mime_type=evidence.mime_type,
        size_bytes=evidence.size_bytes,
        file_sha256_claimed=evidence.file_sha256_claimed,
        file_sha256_verified=evidence.file_sha256_verified,
        confirmed_at=evidence.confirmed_at,
        evidence_source=evidence.evidence_source,
        storage_instance_kind=evidence.storage_instance_kind,
        storage_instance_id=evidence.storage_instance_id,
        confirm_idempotency_key=evidence.confirm_idempotency_key,
        created_at=evidence.created_at,
    )


@router.post("/{inspection_id}/submit", response_model=InspectionSubmitResponse)
async def submit_inspection(
    inspection_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """Submit inspection (Golden Master v2.3.1).
    
    Locks the inspection, computes canonical JSON hash, stores frozen blob,
    and enqueues certificate generation job.
    """
    inspection = await get_inspection_with_auth(inspection_id, db, current_user, require_draft=True)

    now = datetime.utcnow()
    
    # Compute canonical hash using whitelist-based serializer
    canonical_payload, canonical_json, sha256_hash = compute_canonical_hash(inspection)

    # Lock and store canonical data
    inspection.locked_at = now
    inspection.canonical_json_blob = canonical_payload
    inspection.canonical_json_sha256 = sha256_hash
    inspection.content_hash = sha256_hash
    inspection.status = InspectionStatus.SUBMITTED

    # Enqueue certificate PDF generation via jobs_outbox
    jobs = JobsService(db)
    await jobs.enqueue_generate_certificate(
        inspection_id=inspection.id,
        content_hash=sha256_hash,
    )

    # Audit log
    audit = AuditService(db)
    await audit.log_inspection_submitted(
        inspection_id=inspection_id,
        org_id=current_user.org_id,
        user_id=current_user.db_user_id,
        content_hash=sha256_hash,
        ip_address=request.client.host if request.client else None,
    )

    await db.commit()

    return InspectionSubmitResponse(
        inspection_id=inspection.id,
        status=inspection.status,
        content_hash=sha256_hash,
    )


@router.post("/{inspection_id}/sign", response_model=InspectionSignResponse)
async def sign_inspection(
    inspection_id: UUID,
    data: InspectionSignRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """Sign inspection (tenant or landlord). Once both sign, status -> SIGNED (immutable)."""
    inspection = await get_inspection_with_auth(inspection_id, db, current_user)

    if inspection.status not in (InspectionStatus.SUBMITTED, InspectionStatus.REVIEWED):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inspection must be submitted before signing",
        )

    now = datetime.utcnow()

    if data.signature_type == "tenant":
        if inspection.tenant_signed_at:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Already signed by tenant")
        inspection.tenant_signed_at = now
    else:
        if not current_user.org_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only org members can sign as landlord")
        if inspection.landlord_signed_at:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Already signed by landlord")
        inspection.landlord_signed_at = now

    # Check if both signed
    if inspection.tenant_signed_at and inspection.landlord_signed_at:
        inspection.status = InspectionStatus.SIGNED

    # Audit log
    audit = AuditService(db)
    await audit.log_inspection_signed(
        inspection_id=inspection_id,
        org_id=current_user.org_id,
        user_id=current_user.db_user_id,
        signature_type=data.signature_type,
        ip_address=request.client.host if request.client else None,
    )

    await db.commit()
    await db.refresh(inspection)

    return InspectionSignResponse(
        inspection_id=inspection.id,
        status=inspection.status,
        tenant_signed_at=inspection.tenant_signed_at,
        landlord_signed_at=inspection.landlord_signed_at,
        message=f"Signed by {data.signature_type}" + (". Inspection is now immutable." if inspection.status == InspectionStatus.SIGNED else ""),
    )


# --- STR Host Attestation ---

@router.post("/{inspection_id}/attest", response_model=InspectionAttestResponse)
async def attest_inspection(
    inspection_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_org_member),
):
    """STR host attestation signing.
    
    For booking-scoped inspections only. Locks the inspection and computes
    content_hash if not already computed. Sets signed_by='HOST_SYSTEM',
    signed_at=now(), status->SIGNED.
    
    STR inspections do NOT require tenant/guest signature.
    """
    inspection = await get_inspection_with_auth(inspection_id, db, current_user)

    # Verify this is a booking-scoped inspection
    if inspection.scope != InspectionScope.BOOKING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Attestation is only available for booking-scoped (STR) inspections. Use /sign for lease-scoped inspections.",
        )

    # Cannot attest already signed
    if inspection.status == InspectionStatus.SIGNED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inspection is already signed and immutable",
        )

    # Compute content_hash if not already computed (submit step may have been skipped)
    if not inspection.content_hash:
        # Build canonical data for hashing
        items_data = []
        for item in sorted(inspection.items, key=lambda x: (x.room_name, x.item_name)):
            evidence_data = []
            for ev in sorted(item.evidence, key=lambda x: x.created_at):
                if ev.is_confirmed:
                    evidence_data.append({
                        "file_hash": ev.file_hash,
                        "mime_type": ev.mime_type,
                    })
            
            items_data.append({
                "room_name": item.room_name,
                "item_name": item.item_name,
                "condition_rating": item.condition_rating,
                "is_damaged": item.is_damaged,
                "damage_description": item.damage_description,
                "evidence": evidence_data,
            })

        canonical_data = {
            "inspection_id": str(inspection.id),
            "lease_id": str(inspection.lease_id),
            "booking_id": inspection.booking_id,
            "inspection_type": inspection.inspection_type.value,
            "inspection_date": inspection.inspection_date.isoformat(),
            "items": items_data,
        }

        inspection.content_hash = compute_content_hash(canonical_data, schema_version=1)

    now = datetime.utcnow()

    # Set attestation fields
    inspection.signed_by = InspectionSignedBy.HOST_SYSTEM
    inspection.signed_actor_id = current_user.db_user_id
    inspection.signed_at = now
    inspection.status = InspectionStatus.SIGNED

    # Audit log
    audit = AuditService(db)
    await audit.log(
        action="inspection_attested",
        resource_type="inspection",
        resource_id=inspection_id,
        org_id=current_user.org_id,
        user_id=current_user.db_user_id,
        details={
            "content_hash": inspection.content_hash,
            "booking_id": inspection.booking_id,
            "inspection_type": inspection.inspection_type.value,
        },
        ip_address=request.client.host if request.client else None,
    )

    await db.commit()
    await db.refresh(inspection)

    return InspectionAttestResponse(
        inspection_id=inspection.id,
        status=inspection.status,
        content_hash=inspection.content_hash,
        signed_by=inspection.signed_by,
        signed_actor_id=inspection.signed_actor_id,
        signed_at=inspection.signed_at,
    )


# --- Diff endpoints ---

@router.get("/leases/{lease_id}/inspection-diff", response_model=InspectionDiffResponse)
async def get_inspection_diff(
    lease_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_org_member),
):
    """Get diff between SIGNED move-in and move-out inspections."""
    # Get move-in inspection
    move_in_result = await db.execute(
        select(Inspection)
        .options(selectinload(Inspection.items))
        .where(
            Inspection.lease_id == lease_id,
            Inspection.inspection_type == InspectionType.MOVE_IN,
            Inspection.status == InspectionStatus.SIGNED,
        )
        .order_by(Inspection.inspection_date.desc())
        .limit(1)
    )
    move_in = move_in_result.scalar_one_or_none()

    if not move_in:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No signed move-in inspection found")

    # Get move-out inspection
    move_out_result = await db.execute(
        select(Inspection)
        .options(selectinload(Inspection.items))
        .where(
            Inspection.lease_id == lease_id,
            Inspection.inspection_type == InspectionType.MOVE_OUT,
            Inspection.status == InspectionStatus.SIGNED,
        )
        .order_by(Inspection.inspection_date.desc())
        .limit(1)
    )
    move_out = move_out_result.scalar_one_or_none()

    if not move_out:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No signed move-out inspection found")

    # Build diff
    move_in_items = {(i.room_name, i.item_name): i for i in move_in.items}
    diff_items = []
    total_estimate = 0

    for item in move_out.items:
        key = (item.room_name, item.item_name)
        move_in_item = move_in_items.get(key)

        move_in_condition = move_in_item.condition_rating if move_in_item else None
        move_out_condition = item.condition_rating
        
        condition_change = 0
        if move_in_condition and move_out_condition:
            condition_change = move_out_condition - move_in_condition

        diff_item = InspectionDiffItem(
            room_name=item.room_name,
            item_name=item.item_name,
            move_in_condition=move_in_condition,
            move_out_condition=move_out_condition,
            condition_change=condition_change,
            is_new_damage=item.is_damaged and (not move_in_item or not move_in_item.is_damaged),
            damage_description=item.damage_description,
            mason_estimated_repair_cents=item.mason_estimated_repair_cents,
        )
        diff_items.append(diff_item)

        if diff_item.mason_estimated_repair_cents:
            total_estimate += diff_item.mason_estimated_repair_cents

    damaged_count = sum(1 for d in diff_items if d.is_new_damage or d.condition_change < 0)

    return InspectionDiffResponse(
        lease_id=lease_id,
        move_in_inspection_id=move_in.id,
        move_out_inspection_id=move_out.id,
        items=diff_items,
        total_items=len(diff_items),
        damaged_items=damaged_count,
        total_estimated_repair_cents=total_estimate,
    )


@router.get("/leases/{lease_id}/inspection-diff/estimate", response_model=MasonEstimateResponse)
async def get_mason_estimate(
    lease_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_org_member),
):
    """Get Mason AI cost estimate for inspection diff."""
    # Get lease for deposit amount
    lease_result = await db.execute(
        select(Lease).join(Unit).join(Property).where(
            Lease.id == lease_id,
            Property.org_id == current_user.org_id,
        )
    )
    lease = lease_result.scalar_one_or_none()
    if not lease:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lease not found")

    # Get diff first
    diff_response = await get_inspection_diff(lease_id, db, current_user)

    # Run Mason estimation
    mason = MasonService(db)
    
    diff_data = [
        {
            "room_name": item.room_name,
            "item_name": item.item_name,
            "condition_change": item.condition_change,
        }
        for item in diff_response.items
        if item.condition_change < 0 or item.is_new_damage
    ]

    estimate = await mason.estimate_diff_costs(diff_data, org_id=current_user.org_id)

    total_repair = estimate["total_estimated_repair_cents"]
    deposit = lease.deposit_amount_cents
    deduction = min(total_repair, deposit)
    refund = max(0, deposit - deduction)

    await db.commit()

    return MasonEstimateResponse(
        lease_id=lease_id,
        diff_items=[
            InspectionDiffItem(
                room_name=item["room_name"],
                item_name=item["item_name"],
                move_in_condition=None,
                move_out_condition=None,
                condition_change=item.get("condition_change", 0),
                is_new_damage=False,
                mason_estimated_repair_cents=item.get("estimated_repair_cents", 0),
            )
            for item in estimate["items"]
        ],
        total_estimated_repair_cents=total_repair,
        deposit_amount_cents=deposit,
        estimated_deduction_cents=deduction,
        estimated_refund_cents=refund,
        generated_at=datetime.utcnow(),
    )


# --- Certificate PDF (Golden Master v2.3.1) ---

@router.get("/{inspection_id}/certificate.pdf")
async def get_inspection_certificate(
    inspection_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """Get inspection certificate PDF (Golden Master v2.3.1).
    
    Returns the certificate PDF if available. Certificate is generated
    asynchronously via jobs_outbox after inspection submission.
    """
    inspection = await get_inspection_with_auth(inspection_id, db, current_user)

    # Must be submitted or signed
    if inspection.status not in (InspectionStatus.SUBMITTED, InspectionStatus.REVIEWED, InspectionStatus.SIGNED):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inspection must be submitted before certificate is available",
        )

    # If certificate already generated and stored, redirect to it
    if inspection.certificate_pdf_path:
        storage = get_storage_service()
        download_url = await storage.get_download_url(
            inspection.certificate_pdf_path,
            ttl_seconds=300,  # 5 minute expiry
        )
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url=download_url, status_code=302)

    # Otherwise generate on-demand PDF with content hash
    if not inspection.content_hash:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing content hash for certificate")

    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(72, 720, "PROVENIQ Properties - Inspection Certificate")
    pdf.setFont("Helvetica", 11)
    lines = [
        f"Inspection ID: {inspection_id}",
        f"Lease ID: {inspection.lease_id}",
        f"Content Hash (SHA-256): {inspection.content_hash}",
        f"Status: {inspection.status}",
        f"Submitted At: {inspection.submitted_at}",
        f"Signed At: {inspection.signed_at or inspection.tenant_signed_at or inspection.landlord_signed_at}",
        f"Generated At: {datetime.utcnow().isoformat()}",
    ]
    y = 690
    for line in lines:
        pdf.drawString(72, y, line)
        y -= 18
    pdf.showPage()
    pdf.save()
    buffer.seek(0)
    headers = {"Content-Disposition": f'inline; filename="inspection_{inspection_id}_certificate.pdf"'}
    return StreamingResponse(buffer, media_type="application/pdf", headers=headers)


# --- Claim Packet Export ---

@router.get("/leases/{lease_id}/claim-packet")
async def download_claim_packet(
    lease_id: UUID,
    include_evidence: bool = True,
    submit_claim: bool = True,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_org_member),
):
    """Download claim packet ZIP for deposit disputes.
    
    Generates a ZIP file containing:
    - claim_summary.json: Machine-readable claim data with hashes
    - README.txt: Human-readable summary
    - evidence/: All photos with integrity verification
    
    If submit_claim=true (default), also pushes the claim to ClaimsIQ
    for automated processing through the recovery pipeline.
    
    Use this for:
    - Airbnb/VRBO Resolution Center submissions
    - Insurance claim filings
    - Deposit dispute documentation
    """
    service = ClaimPacketService(db)
    
    try:
        zip_bytes, filename, claimsiq_result = await service.generate_and_submit(
            lease_id=lease_id,
            org_id=current_user.org_id,
            include_evidence=include_evidence,
            submit_to_claimsiq=submit_claim,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    
    # Add ClaimsIQ result to headers if submitted
    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"',
        "Content-Length": str(len(zip_bytes)),
    }
    if claimsiq_result:
        headers["X-ClaimsIQ-Submitted"] = "true" if claimsiq_result.success else "false"
        if claimsiq_result.claim_id:
            headers["X-ClaimsIQ-Claim-ID"] = claimsiq_result.claim_id
        if claimsiq_result.decision:
            headers["X-ClaimsIQ-Decision"] = claimsiq_result.decision
    
    # Return as streaming response
    return StreamingResponse(
        io.BytesIO(zip_bytes),
        media_type="application/zip",
        headers=headers,
    )
