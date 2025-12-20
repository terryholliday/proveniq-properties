"""Inspection schemas."""

from datetime import datetime
from typing import Optional, Any
from uuid import UUID

from pydantic import Field

from app.schemas.base import BaseSchema, IDMixin, TimestampMixin
from app.models.enums import InspectionType, InspectionStatus, EvidenceType


class InspectionCreate(BaseSchema):
    """Create a new inspection."""

    lease_id: UUID
    inspection_type: InspectionType
    inspection_date: datetime
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
    inspection_date: datetime
    content_hash: Optional[str] = None
    schema_version: int
    tenant_signed_at: Optional[datetime] = None
    landlord_signed_at: Optional[datetime] = None
    notes: Optional[str] = None
    item_count: int = 0


class InspectionItemCreate(BaseSchema):
    """Create/upsert inspection item."""

    room_name: str = Field(..., min_length=1, max_length=100)
    item_name: str = Field(..., min_length=1, max_length=100)
    condition_rating: Optional[int] = Field(None, ge=1, le=5)
    condition_notes: Optional[str] = None
    is_damaged: bool = False
    damage_description: Optional[str] = None


class InspectionItemUpdate(BaseSchema):
    """Update inspection item."""

    condition_rating: Optional[int] = Field(None, ge=1, le=5)
    condition_notes: Optional[str] = None
    is_damaged: Optional[bool] = None
    damage_description: Optional[str] = None


class InspectionItemResponse(BaseSchema, IDMixin, TimestampMixin):
    """Inspection item response."""

    inspection_id: UUID
    room_name: str
    item_name: str
    condition_rating: Optional[int] = None
    condition_notes: Optional[str] = None
    is_damaged: bool
    damage_description: Optional[str] = None
    mason_estimated_repair_cents: Optional[int] = None
    evidence_count: int = 0


class EvidencePresignRequest(BaseSchema):
    """Request presigned URL for evidence upload."""

    item_id: UUID
    file_name: str = Field(..., min_length=1, max_length=255)
    mime_type: str = Field(..., pattern=r"^(image|video|audio|application)/.+$")
    file_size_bytes: int = Field(..., gt=0, le=52428800)  # 50MB max


class EvidencePresignResponse(BaseSchema):
    """Presigned URL response."""

    upload_url: str
    object_path: str
    expires_at: datetime
    max_size_bytes: int


class EvidenceConfirmRequest(BaseSchema):
    """Confirm evidence upload."""

    item_id: UUID
    object_path: str
    file_hash: str = Field(..., min_length=64, max_length=64)  # SHA-256
    file_size_bytes: int = Field(..., gt=0)
    mime_type: str


class EvidenceResponse(BaseSchema, IDMixin):
    """Evidence response."""

    item_id: UUID
    evidence_type: EvidenceType
    object_path: str
    file_name: str
    mime_type: str
    file_size_bytes: int
    file_hash: str
    is_confirmed: bool
    confirmed_at: Optional[datetime] = None
    metadata: Optional[dict[str, Any]] = None
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
