"""Maintenance schemas."""

from datetime import datetime
from typing import Optional, Any
from uuid import UUID

from pydantic import Field

from app.schemas.base import BaseSchema, IDMixin, TimestampMixin
from app.models.enums import MaintenanceStatus, VendorSpecialty


class MaintenanceCreate(BaseSchema):
    """Create a maintenance ticket."""

    unit_id: UUID
    title: str = Field(..., min_length=5, max_length=255)
    description: str = Field(..., min_length=10)
    category: Optional[VendorSpecialty] = None
    priority: int = Field(default=3, ge=1, le=5)
    is_tenant_visible: bool = True


class MaintenanceUpdate(BaseSchema):
    """Update maintenance ticket."""

    title: Optional[str] = Field(None, min_length=5, max_length=255)
    description: Optional[str] = Field(None, min_length=10)
    status: Optional[MaintenanceStatus] = None
    category: Optional[VendorSpecialty] = None
    priority: Optional[int] = Field(None, ge=1, le=5)
    scheduled_date: Optional[datetime] = None
    maintenance_cost_estimate_cents: Optional[int] = Field(None, ge=0)
    is_tenant_visible: Optional[bool] = None
    tenant_notes: Optional[str] = None


class MaintenanceAssignRequest(BaseSchema):
    """Assign maintenance ticket to vendor or org member."""

    assigned_vendor_id: Optional[UUID] = None
    assigned_org_member_user_id: Optional[UUID] = None

    def model_post_init(self, __context):
        """Validate that exactly one assignee is provided."""
        if self.assigned_vendor_id and self.assigned_org_member_user_id:
            raise ValueError("Cannot assign to both vendor and org member")
        if not self.assigned_vendor_id and not self.assigned_org_member_user_id:
            raise ValueError("Must assign to either vendor or org member")


class MaintenanceResponse(BaseSchema, IDMixin, TimestampMixin):
    """Maintenance ticket response."""

    unit_id: UUID
    created_by_id: Optional[UUID] = None
    assigned_vendor_id: Optional[UUID] = None
    assigned_org_member_user_id: Optional[UUID] = None
    title: str
    description: str
    status: MaintenanceStatus
    category: Optional[VendorSpecialty] = None
    priority: int
    maintenance_cost_estimate_cents: Optional[int] = None
    mason_triage_result: Optional[dict[str, Any]] = None
    mason_triaged_at: Optional[datetime] = None
    scheduled_date: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    is_tenant_visible: bool
    tenant_notes: Optional[str] = None


class MaintenanceTriageRequest(BaseSchema):
    """Request Mason AI triage."""

    include_vendor_suggestions: bool = True


class MaintenanceTriageResponse(BaseSchema):
    """Mason AI triage response."""

    ticket_id: UUID
    suggested_category: VendorSpecialty
    suggested_priority: int
    estimated_cost_cents: Optional[int] = None
    suggested_vendor_ids: list[UUID] = []
    reasoning: str
    disclaimer: str = "This is a non-binding advisory assessment. Actual requirements may vary."
    triaged_at: datetime
