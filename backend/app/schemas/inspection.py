"""Inspection schemas."""

from datetime import datetime
from typing import Optional, Any
from uuid import UUID

from pydantic import Field

from app.schemas.base import BaseSchema, IDMixin, TimestampMixin
from app.models.enums import (
    InspectionType, InspectionStatus, EvidenceType, InspectionScope, InspectionSignedBy,
    InspectionCondition, EvidenceSource, StorageInstanceKind,
)


class InspectionCreate(BaseSchema):
    """Create a new inspection."""

    lease_id: UUID
    inspection_type: InspectionType
    inspection_date: datetime
    # STR support
    scope: InspectionScope = InspectionScope.LEASE
    booking_id: Optional[str] = Field(None, max_length=255)
    notes: Optional[str] = None


class InspectionUpdate(BaseSchema):
    """Update inspection (draft only)."""

    inspection_date: Optional[datetime] = None
    notes: Optional[str] = None


class InspectionResponse(BaseSchema, IDMixin, TimestampMixin):
    """Inspection response."""

    lease_id: UUID
    created_by_id: Optional[UUID] = None
    supplemental_to_inspection_id: Optional[UUID] = None
    inspection_type: InspectionType
    status: InspectionStatus
    # STR support
    scope: InspectionScope
    booking_id: Optional[str] = None
    # Dates
    inspection_date: datetime
    content_hash: Optional[str] = None
    schema_version: int
    # Lease-scoped signatures
    tenant_signed_at: Optional[datetime] = None
    landlord_signed_at: Optional[datetime] = None
    # STR host attestation
    signed_by: Optional[InspectionSignedBy] = None
    signed_actor_id: Optional[UUID] = None
    signed_at: Optional[datetime] = None
    notes: Optional[str] = None
    item_count: int = 0


class InspectionItemCreate(BaseSchema):
    """Create/upsert inspection item (Golden Master v2.3.1)."""

    room_key: str = Field(..., min_length=1, max_length=100)
    item_key: str = Field(..., min_length=1, max_length=100)
    ordinal: int = Field(default=0, ge=0)
    condition: InspectionCondition = InspectionCondition.GOOD
    notes: Optional[str] = None


class InspectionItemUpdate(BaseSchema):
    """Update inspection item (Golden Master v2.3.1)."""

    condition: Optional[InspectionCondition] = None
    notes: Optional[str] = None


class InspectionItemResponse(BaseSchema, IDMixin, TimestampMixin):
    """Inspection item response (Golden Master v2.3.1)."""

    inspection_id: UUID
    room_key: str
    item_key: str
    ordinal: int
    condition: InspectionCondition
    notes: Optional[str] = None
    mason_estimated_repair_cents: Optional[int] = None
    evidence_count: int = 0


class EvidencePresignRequest(BaseSchema):
    """Request presigned URL for evidence upload (Golden Master v2.3.1).
    
    MUST bind exact Content-Type and size range.
    """

    inspection_item_id: UUID
    mime_type: str = Field(..., pattern=r"^(image|video|audio|application)/.+$")
    size_bytes: int = Field(..., gt=0, le=52428800)  # 50MB max
    evidence_source: EvidenceSource = EvidenceSource.TENANT


class EvidencePresignResponse(BaseSchema):
    """Presigned URL response (Golden Master v2.3.1)."""

    evidence_id: UUID
    upload_url: str
    object_path: str
    expires_at: datetime
    bound_mime_type: str
    bound_size_bytes: int


class EvidenceConfirmRequest(BaseSchema):
    """Confirm evidence upload (Golden Master v2.3.1).
    
    Idempotent confirm. Server performs HEAD check, records storage_instance_id.
    """

    inspection_item_id: UUID
    object_path: str
    confirm_idempotency_key: str = Field(..., min_length=1, max_length=255)
    mime_type: str
    size_bytes: int = Field(..., gt=0)
    file_sha256_claimed: str = Field(..., min_length=64, max_length=64)


class EvidenceResponse(BaseSchema, IDMixin):
    """Evidence response (Golden Master v2.3.1)."""

    inspection_item_id: UUID
    object_path: str
    mime_type: str
    size_bytes: int
    file_sha256_claimed: str
    file_sha256_verified: Optional[str] = None
    confirmed_at: datetime
    evidence_source: EvidenceSource
    storage_instance_kind: StorageInstanceKind
    storage_instance_id: str
    confirm_idempotency_key: str
    created_at: datetime


class InspectionSubmitResponse(BaseSchema):
    """Response after submitting inspection."""

    inspection_id: UUID
    status: InspectionStatus
    content_hash: str
    message: str = "Inspection submitted successfully"


class InspectionSignRequest(BaseSchema):
    """Request to sign inspection."""

    signature_type: str = Field(..., pattern=r"^(tenant|landlord)$")


class InspectionSignResponse(BaseSchema):
    """Response after signing inspection."""

    inspection_id: UUID
    status: InspectionStatus
    tenant_signed_at: Optional[datetime] = None
    landlord_signed_at: Optional[datetime] = None
    message: str


class InspectionDiffItem(BaseSchema):
    """A single item in the inspection diff."""

    room_name: str
    item_name: str
    move_in_condition: Optional[int] = None
    move_out_condition: Optional[int] = None
    condition_change: int = 0  # negative = degraded
    is_new_damage: bool = False
    damage_description: Optional[str] = None
    mason_estimated_repair_cents: Optional[int] = None


class InspectionDiffResponse(BaseSchema):
    """Inspection diff between move-in and move-out."""

    lease_id: UUID
    move_in_inspection_id: UUID
    move_out_inspection_id: UUID
    items: list[InspectionDiffItem]
    total_items: int
    damaged_items: int
    total_estimated_repair_cents: int
    disclaimer: str = "These are non-binding advisory estimates. Actual costs may vary."


class MasonEstimateResponse(BaseSchema):
    """Mason AI cost estimate response."""

    lease_id: UUID
    diff_items: list[InspectionDiffItem]
    total_estimated_repair_cents: int
    deposit_amount_cents: int
    estimated_deduction_cents: int
    estimated_refund_cents: int
    disclaimer: str = "This is a non-binding advisory estimate. Actual costs may vary."
    generated_at: datetime


# --- STR Attestation ---

class InspectionAttestRequest(BaseSchema):
    """STR host attestation request."""

    pass  # No additional fields needed - attestation uses current user


class InspectionAttestResponse(BaseSchema):
    """Response after STR host attestation."""

    inspection_id: UUID
    status: InspectionStatus
    content_hash: str
    signed_by: InspectionSignedBy
    signed_actor_id: UUID
    signed_at: datetime
    message: str = "Inspection attested and locked. Evidence is now immutable."
