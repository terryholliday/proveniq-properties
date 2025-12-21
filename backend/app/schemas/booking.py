"""Booking schemas for STR support."""

from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import Field, model_validator

from app.schemas.base import BaseSchema, IDMixin, TimestampMixin
from app.models.enums import BookingStatus


class BookingCreate(BaseSchema):
    """Create a new STR booking."""

    unit_id: UUID
    guest_name: Optional[str] = Field(None, max_length=255)
    guest_count: int = Field(default=1, ge=1, le=50)
    check_in_date: date
    check_out_date: date
    external_id: Optional[str] = Field(None, max_length=100)
    source: str = Field(default="manual", max_length=50)
    notes: Optional[str] = None

    @model_validator(mode="after")
    def validate_dates(self):
        """Check-out must be after check-in."""
        if self.check_out_date <= self.check_in_date:
            raise ValueError("check_out_date must be after check_in_date")
        return self


class BookingUpdate(BaseSchema):
    """Update a booking."""

    guest_name: Optional[str] = Field(None, max_length=255)
    guest_count: Optional[int] = Field(None, ge=1, le=50)
    check_in_date: Optional[date] = None
    check_out_date: Optional[date] = None
    status: Optional[BookingStatus] = None
    notes: Optional[str] = None


class BookingResponse(BaseSchema, IDMixin, TimestampMixin):
    """Booking response."""

    unit_id: UUID
    external_id: Optional[str] = None
    source: str
    guest_name: Optional[str] = None
    guest_count: int
    check_in_date: date
    check_out_date: date
    actual_check_in: Optional[datetime] = None
    actual_check_out: Optional[datetime] = None
    status: BookingStatus
    notes: Optional[str] = None
    # Linked inspection IDs
    pre_stay_inspection_id: Optional[UUID] = None
    post_stay_inspection_id: Optional[UUID] = None


class BookingCheckInRequest(BaseSchema):
    """Request to check in a booking."""

    actual_check_in: Optional[datetime] = None  # Defaults to now


class BookingCheckOutRequest(BaseSchema):
    """Request to check out a booking."""

    actual_check_out: Optional[datetime] = None  # Defaults to now


class ClaimPacketRequest(BaseSchema):
    """Request to generate STR claim packet."""

    include_evidence_urls: bool = True
    include_mason_estimate: bool = True


class ClaimPacketResponse(BaseSchema):
    """STR claim packet for platform disputes."""

    booking_id: UUID
    unit_id: UUID
    guest_name: Optional[str] = None
    check_in_date: date
    check_out_date: date
    
    # Inspection hashes
    pre_stay_inspection_id: UUID
    pre_stay_content_hash: str
    pre_stay_signed_at: datetime
    
    post_stay_inspection_id: UUID
    post_stay_content_hash: str
    post_stay_signed_at: datetime
    
    # Diff summary
    diff_summary: list[dict]
    total_items: int
    damaged_items: int
    
    # Mason estimate (advisory)
    total_estimated_repair_cents: int
    
    # Evidence hashes for verification
    evidence_hash_list: list[dict]
    
    # Narrative for platform submission
    narrative: str
    
    # Disclaimer (always present)
    disclaimer: str = "This is a non-binding advisory estimate. Actual costs may vary. Evidence hashes provided for verification."
    
    generated_at: datetime
