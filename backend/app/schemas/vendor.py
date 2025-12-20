"""Vendor schemas."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import EmailStr, Field

from app.schemas.base import BaseSchema, IDMixin, TimestampMixin
from app.models.enums import VendorSpecialty


class VendorCreate(BaseSchema):
    """Create a new vendor."""

    name: str = Field(..., min_length=2, max_length=255)
    specialty: VendorSpecialty = VendorSpecialty.GENERAL
    contact_name: Optional[str] = Field(None, max_length=255)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, max_length=50)
    address: Optional[str] = None
    is_preferred: bool = False
    notes: Optional[str] = None


class VendorUpdate(BaseSchema):
    """Update vendor."""

    name: Optional[str] = Field(None, min_length=2, max_length=255)
    specialty: Optional[VendorSpecialty] = None
    contact_name: Optional[str] = Field(None, max_length=255)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, max_length=50)
    address: Optional[str] = None
    is_active: Optional[bool] = None
    is_preferred: Optional[bool] = None
    notes: Optional[str] = None


class VendorResponse(BaseSchema, IDMixin, TimestampMixin):
    """Vendor response."""

    org_id: UUID
    name: str
    specialty: VendorSpecialty
    contact_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    is_active: bool
    is_preferred: bool
    notes: Optional[str] = None
