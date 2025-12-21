"""Lease schemas."""

from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import EmailStr, Field, model_validator

from app.schemas.base import BaseSchema, IDMixin, TimestampMixin
from app.models.enums import LeaseStatus, LeaseType


class LeaseCreate(BaseSchema):
    """Create a new lease."""

    unit_id: UUID
    lease_type: LeaseType
    
    start_date: date
    end_date: date
    
    # Money in CENTS (integers only)
    rent_amount_cents: int = Field(..., gt=0)
    deposit_amount_cents: int = Field(default=0, ge=0)
    
    # Commercial NNN fields
    pro_rata_share_bps: Optional[int] = Field(None, gt=0, le=10000)
    cam_budget_cents: Optional[int] = Field(None, ge=0)
    
    # Tenant info
    tenant_email: EmailStr
    tenant_name: Optional[str] = Field(None, max_length=255)
    tenant_phone: Optional[str] = Field(None, max_length=50)
    
    notes: Optional[str] = None

    @model_validator(mode="after")
    def validate_dates(self):
        """End date must be after start date."""
        if self.end_date <= self.start_date:
            raise ValueError("end_date must be after start_date")
        return self

    @model_validator(mode="after")
    def validate_nnn_fields(self):
        """NNN leases REQUIRE pro_rata_share_bps."""
        if self.lease_type == LeaseType.COMMERCIAL_NNN:
            if not self.pro_rata_share_bps:
                raise ValueError("pro_rata_share_bps is required for NNN leases")
        return self


class LeaseUpdate(BaseSchema):
    """Update lease (limited fields)."""

    tenant_name: Optional[str] = Field(None, max_length=255)
    tenant_phone: Optional[str] = Field(None, max_length=50)
    notes: Optional[str] = None
    cam_budget_cents: Optional[int] = Field(None, ge=0)


class LeaseResponse(BaseSchema, IDMixin, TimestampMixin):
    """Lease response."""

    unit_id: UUID
    lease_type: LeaseType
    status: LeaseStatus
    start_date: date
    end_date: date
    rent_amount_cents: int
    deposit_amount_cents: int
    pro_rata_share_bps: Optional[int] = None
    cam_budget_cents: Optional[int] = None
    tenant_email: str
    tenant_name: Optional[str] = None
    tenant_phone: Optional[str] = None
    invite_sent_at: Optional[datetime] = None
    notes: Optional[str] = None
    
    # Denormalized fields for list views
    unit_number: Optional[str] = None
    property_name: Optional[str] = None
    property_id: Optional[UUID] = None
    occupancy_model: Optional[str] = None
    has_move_in_inspection: bool = False
    has_move_out_inspection: bool = False


class LeaseListResponse(BaseSchema):
    """Response for lease list endpoint."""
    
    leases: list[LeaseResponse]
    total: int


class LeaseInviteRequest(BaseSchema):
    """Request to send tenant invite."""

    custom_message: Optional[str] = Field(None, max_length=500)


class LeaseInviteResponse(BaseSchema):
    """Response after sending tenant invite."""

    lease_id: UUID
    tenant_email: str
    invite_sent_at: datetime
    message: str = "Invite sent successfully"


class LeaseRenewalRequest(BaseSchema):
    """Request to initiate lease renewal."""

    new_end_date: date
    new_rent_amount_cents: int = Field(..., gt=0)
    new_deposit_amount_cents: Optional[int] = Field(None, ge=0)
    new_cam_budget_cents: Optional[int] = Field(None, ge=0)
    notes: Optional[str] = None

    @model_validator(mode="after")
    def validate_end_date(self):
        """New end date must be in the future."""
        if self.new_end_date <= date.today():
            raise ValueError("new_end_date must be in the future")
        return self


class LeaseRenewalResponse(BaseSchema):
    """Response after initiating lease renewal."""

    original_lease_id: UUID
    renewed_lease_id: UUID
    new_start_date: date
    new_end_date: date
    new_rent_amount_cents: int
    rent_change_cents: int
    rent_change_pct: float
    message: str = "Renewal lease created successfully"
