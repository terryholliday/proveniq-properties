"""Organization schemas."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import EmailStr, Field

from app.schemas.base import BaseSchema, IDMixin, TimestampMixin
from app.models.enums import OrgRole


class OrgCreate(BaseSchema):
    """Create a new organization."""

    name: str = Field(..., min_length=2, max_length=255)
    slug: str = Field(..., min_length=2, max_length=100, pattern=r"^[a-z0-9-]+$")
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, max_length=50)
    address: Optional[str] = None
    timezone: str = "America/New_York"


class OrgUpdate(BaseSchema):
    """Update organization."""

    name: Optional[str] = Field(None, min_length=2, max_length=255)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, max_length=50)
    address: Optional[str] = None
    timezone: Optional[str] = None


class OrgResponse(BaseSchema, IDMixin, TimestampMixin):
    """Organization response."""

    name: str
    slug: str
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    timezone: str


class OrgMembershipResponse(BaseSchema, IDMixin):
    """Org membership response."""

    org_id: UUID
    user_id: UUID
    role: OrgRole
    created_at: datetime


class OrgWithMembership(OrgResponse):
    """Org response with current user's membership."""

    current_user_role: OrgRole


class OrgMemberResponse(BaseSchema):
    """Member in organization list."""

    id: str
    email: str
    name: Optional[str] = None
    role: str
    joined_at: str
    last_active: Optional[str] = None


class OrgMemberListResponse(BaseSchema):
    """Response for organization members list."""

    members: list[OrgMemberResponse]


class OrgInviteRequest(BaseSchema):
    """Request to invite a member."""

    email: EmailStr
    role: str = "ORG_MEMBER"


class OrgInviteResponse(BaseSchema):
    """Response after sending invite."""

    email: str
    role: str
    message: str
